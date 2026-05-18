"""
retriever.py — Recherche hybride (sémantique + BM25) + reranking.

Pipeline :
  1. Multi-requêtes → recherche FAISS (TOP_K_RETRIEVAL par requête)
  2. Multi-requêtes → recherche BM25 (TOP_K_RETRIEVAL par requête)
  3. Fusion par Reciprocal Rank Fusion (RRF), pondérée
  4. Reranking par cross-encoder (top RERANK_TOP_N → TOP_K_RESULTS)
  5. Filtrage workspace si demandé
"""

import logging
import re as _re
from typing import cast

from config import (
    HYBRID_BM25_WEIGHT,
    HYBRID_RRF_K,
    RERANK_TOP_N,
    SIMILARITY_THRESHOLD,
    TOP_K_RESULTS,
    TOP_K_RETRIEVAL,
)
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.bm25_store import get_bm25_index
from src.indexer import load_index
from src.reranker import rerank

logger = logging.getLogger(__name__)

_vectorstore_instance: FAISS | None = None


def get_vectorstore() -> FAISS:
    global _vectorstore_instance
    if _vectorstore_instance is None:
        _vectorstore_instance = load_index()
    return cast(FAISS, _vectorstore_instance)


def reset_vectorstore() -> None:
    global _vectorstore_instance
    _vectorstore_instance = None
    logger.info("Vectorstore réinitialisé — rechargement au prochain appel.")


# ──────────────────────────────────────────────────────────────
# Recherche sémantique brute (FAISS) — utilisée par hybrid_search
# ──────────────────────────────────────────────────────────────


def _semantic_search(
    query: str,
    workspace: str | None,
    k: int,
) -> list[tuple[Document, float]]:
    """Retourne (Document, score normalisé) pour une requête."""
    vs = get_vectorstore()
    # Avec embeddings normalisés (L2 sur vecteurs unitaires ≈ cosine), la distance
    # FAISS est déjà bornée [0, 2] — la conversion 1/(1+dist) est cohérente.
    raw = vs.similarity_search_with_score(query=query, k=k * 4)
    out: list[tuple[Document, float]] = []
    page_hits: dict[tuple, int] = {}
    for doc, dist in raw:
        sim = 1 / (1 + dist)
        # Les résultats FAISS sont triés par distance croissante : dès qu'on passe
        # sous le seuil, tous les suivants le seront aussi → sortie anticipée.
        if sim < SIMILARITY_THRESHOLD:
            break
        if workspace and doc.metadata.get("workspace") != workspace:
            continue
        page_key = (doc.metadata.get("source", ""), doc.metadata.get("page", ""))
        # Max 2 chunks par page : évite de saturer le contexte avec des passages
        # adjacents issus du même endroit du document.
        if page_hits.get(page_key, 0) >= 2:
            continue
        page_hits[page_key] = page_hits.get(page_key, 0) + 1
        meta = dict(doc.metadata)
        meta["similarity_score"] = round(float(sim), 3)
        out.append((Document(page_content=doc.page_content, metadata=meta), sim))
    return out[:k]


# ──────────────────────────────────────────────────────────────
# Fusion Reciprocal Rank Fusion (RRF)
# ──────────────────────────────────────────────────────────────


def _doc_key(doc: Document) -> str:
    return (
        f"{doc.metadata.get('source', '')}|"
        f"{doc.metadata.get('page', '')}|"
        f"{doc.metadata.get('chunk_index', '')}|"
        f"{doc.page_content[:80]}"
    )


def _rrf_fuse(
    ranked_lists: list[tuple[list[Document], float]],
    k: int = HYBRID_RRF_K,
) -> list[Document]:
    """
    Reciprocal Rank Fusion pondérée.
    `ranked_lists` : [(documents_classés, poids), …]
    Retourne une liste fusionnée triée par score RRF cumulé.
    """
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}

    for documents, weight in ranked_lists:
        for rank, doc in enumerate(documents):
            key = _doc_key(doc)
            contrib = weight / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + contrib
            if key not in docs:
                docs[key] = doc
            else:
                # Conserver le meilleur similarity_score connu
                existing = docs[key].metadata.get("similarity_score", 0)
                incoming = doc.metadata.get("similarity_score", 0)
                if incoming > existing:
                    docs[key] = doc

    ordered_keys = sorted(scores.keys(), key=lambda k_: scores[k_], reverse=True)
    fused: list[Document] = []
    for key in ordered_keys:
        doc = docs[key]
        meta = dict(doc.metadata)
        meta["rrf_score"] = round(scores[key], 5)
        fused.append(Document(page_content=doc.page_content, metadata=meta))
    return fused


# ──────────────────────────────────────────────────────────────
# Recherche hybride (publique)
# ──────────────────────────────────────────────────────────────


_QUERY_DECAY = (1.0, 0.7, 0.5)  # poids par position de requête (original > reformulations)


def _detect_query_type(query: str) -> float:
    """
    Retourne le poids BM25 adapté au type de requête.

    - Noms propres (majuscules) ou références d'articles  → BM25 fort (0.60)
    - Questions conceptuelles / explicatives               → FAISS fort (BM25 0.30)
    - Requêtes mixtes                                      → défaut config (0.45)
    """
    if _re.search(r"\bL?\d{3,}[-–]\d+\b", query) or _re.search(r"\b[A-Z][a-zéèêëàâùûü]{2,}\b", query):
        return 0.60
    if any(w in query.lower() for w in ("comment", "pourquoi", "qu'est", "différence", "expliqu", "définition")):
        return 0.30
    return HYBRID_BM25_WEIGHT


def hybrid_search(
    queries: list[str],
    workspace: str | None = None,
    *,
    top_k: int = TOP_K_RESULTS,
    rerank_pool: int = RERANK_TOP_N,
) -> list[Document]:
    """
    Pipeline complet : FAISS + BM25 → RRF → reranking → top_k.

    `queries` : liste de reformulations (originale + acronyms + décomposition…).
                La requête originale (index 0) reçoit un poids plus élevé que
                les reformulations suivantes (décroissance _QUERY_DECAY).
    """
    if not queries:
        return []

    bm25_w = _detect_query_type(queries[0])
    sem_w = 1.0 - bm25_w
    pool_size = max(TOP_K_RETRIEVAL, rerank_pool)

    ranked_lists: list[tuple[list[Document], float]] = []

    # Sémantique + BM25 avec décroissance de poids selon la position de la requête.
    # La requête originale compte plus que ses reformulations.
    bm25 = get_bm25_index()
    for i, q in enumerate(queries):
        decay = _QUERY_DECAY[i] if i < len(_QUERY_DECAY) else 0.4

        sem_pairs = _semantic_search(q, workspace, pool_size)
        ranked_lists.append(([d for d, _ in sem_pairs], sem_w * decay))

        if bm25 is not None:
            pairs = bm25.search(q, k=pool_size, workspace=workspace)
            ranked_lists.append(([d for d, _ in pairs], bm25_w * decay))

    if bm25 is None:
        logger.debug("[hybrid] Index BM25 absent — recherche sémantique uniquement.")

    fused = _rrf_fuse(ranked_lists)
    if not fused:
        return []

    # Pool de base (RRF top-N)
    pool_set: dict[str, Document] = {_doc_key(d): d for d in fused[:rerank_pool]}

    # Garantie BM25 : le top-1 BM25 de la requête principale est toujours candidat.
    # Cas typique : un nom propre unique identifie un CV que la recherche
    # sémantique rate (elle retourne du Code du Travail à la place).
    if bm25 is not None:
        top_bm25 = bm25.search(queries[0], k=1, workspace=workspace)
        if top_bm25:
            doc, _ = top_bm25[0]
            k = _doc_key(doc)
            if k not in pool_set:
                pool_set[k] = doc
                logger.debug(f"[hybrid] BM25 safeguard : ajout forcé de {doc.metadata.get('source')}")

    candidates = list(pool_set.values())
    primary_query = queries[0]
    reranked = rerank(primary_query, candidates, top_k)
    logger.info(
        f"[hybrid] {len(queries)} requête(s) | fused={len(fused)} → "
        f"pool={len(candidates)} → final={len(reranked)}"
    )
    return reranked


def search(query: str, workspace: str | None = None, k: int = TOP_K_RESULTS) -> list[Document]:
    """Alias mono-requête de hybrid_search (compat tests)."""
    return hybrid_search([query], workspace, top_k=k)


# ──────────────────────────────────────────────────────────────
# Formatage des sources
# ──────────────────────────────────────────────────────────────


def format_sources(documents: list[Document], *, max_sources: int = 3) -> list[dict]:
    """
    Sérialise les chunks en sources affichables côté frontend.

    - Déduplique par (fichier, page)
    - Priorité : rerank_score > rrf_score (fusion hybride) > similarity_score
    - Normalise les scores : la source la plus pertinente = 1.0
    - Limite à max_sources résultats
    """
    seen: set[str] = set()
    candidates: list[dict] = []

    for doc in documents:
        meta = doc.metadata
        key = f"{meta.get('source')}|{meta.get('page')}"
        if key in seen:
            continue
        seen.add(key)

        rerank_score = meta.get("rerank_score")
        raw = (
            rerank_score
            if rerank_score is not None and rerank_score > 0
            else meta.get("rrf_score")
            if meta.get("rrf_score") is not None
            else meta.get("similarity_score", 0.0)
        )

        candidates.append(
            {
                "fichier": str(meta.get("source", "Inconnu")),
                "page": meta.get("page", "?"),
                "workspace": str(meta.get("workspace", "")),
                "_raw": float(raw or 0.0),
                "extrait": doc.page_content[:200] + ("…" if len(doc.page_content) > 200 else ""),
            }
        )

    if not candidates:
        return []

    candidates.sort(key=lambda x: x["_raw"], reverse=True)
    top = candidates[:max_sources]

    # Min-max normalization avec plancher à 0.35 : toutes les sources récupérées
    # ont un score visible (35 %–100 %). Sans plancher, la dernière source
    # aurait toujours 0 % et afficherait "—" dans l'interface.
    _FLOOR = 0.35
    max_raw = top[0]["_raw"]
    min_raw = min(c["_raw"] for c in top)
    span = max_raw - min_raw
    for c in top:
        if span > 0:
            c["score"] = round(_FLOOR + (1.0 - _FLOOR) * (c["_raw"] - min_raw) / span, 3)
        else:
            c["score"] = 1.0 if max_raw != 0 else _FLOOR
        del c["_raw"]

    return top
