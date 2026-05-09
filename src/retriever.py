"""
Retriever : recherche sémantique + keyword dans l'index FAISS
"""

import logging
import re
from typing import cast

from config import SIMILARITY_THRESHOLD, TOP_K_RESULTS
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.indexer import load_index

logger = logging.getLogger(__name__)

# Instance globale — évite de recharger l'index à chaque requête
_vectorstore_instance: FAISS | None = None


def get_vectorstore() -> FAISS:
    """Retourne l'instance vectorstore (singleton)."""
    global _vectorstore_instance
    if _vectorstore_instance is None:
        _vectorstore_instance = load_index()
    return cast(FAISS, _vectorstore_instance)


def reset_vectorstore() -> None:
    """Invalide le singleton pour forcer le rechargement au prochain appel.
    À appeler après un upload ou une ré-indexation."""
    global _vectorstore_instance
    _vectorstore_instance = None
    logger.info("Vectorstore réinitialisé — sera rechargé au prochain appel.")


def multi_search(
    queries: list[str],
    categorie: str | None = None,
    k: int = TOP_K_RESULTS,
) -> list[Document]:
    """
    Recherche avec plusieurs formulations de la même question.
    Fusionne les résultats et garde le meilleur score par chunk unique.
    Retourne au plus k documents classés par score décroissant.

    Utilisé pour maximiser le rappel quand la requête est ambiguë :
    - requête originale + requête étendue (acronymes)
    - requête originale + reformulation contextuelle
    """
    if not queries:
        return []

    seen_ids: dict[str, float] = {}  # page_key → meilleur score
    doc_map: dict[str, Document] = {}  # page_key → document

    for query in queries:
        results = search(query=query, categorie=categorie, k=k)
        for doc in results:
            key = (
                f"{doc.metadata.get('source', '')}|"
                f"{doc.metadata.get('page', '')}|"
                f"{doc.page_content[:80]}"  # sous-clé pour distinguer chunks sur même page
            )
            score = float(doc.metadata.get("similarity_score", 0))
            if key not in seen_ids or score > seen_ids[key]:
                seen_ids[key] = score
                doc.metadata["similarity_score"] = score
                doc_map[key] = doc

    merged = sorted(
        doc_map.values(), key=lambda d: d.metadata.get("similarity_score", 0), reverse=True
    )
    logger.info(f"multi_search({len(queries)} requêtes) → {len(merged)} chunks uniques (top {k})")
    return merged[:k]


def search(query: str, categorie: str | None = None, k: int = TOP_K_RESULTS) -> list[Document]:
    """
    Recherche les chunks les plus pertinents pour une question.

    Stratégie :
    - Récupère k*3 candidats avec score FAISS
    - Filtre par seuil de similarité et catégorie
    - Applique une déduplication par page (max 2 chunks par page/document)
      pour maximiser la diversité des sources
    - Retourne au plus k chunks triés par pertinence décroissante

    Args:
        query     : question de l'utilisateur
        categorie : filtre optionnel ("technique", "rh", "juridique")
        k         : nombre de résultats à retourner
    """
    vectorstore = get_vectorstore()

    results_with_scores = vectorstore.similarity_search_with_score(
        query=query,
        k=k * 5,  # pool élargi (était k*3) — améliore le rappel sur grands corpus
    )

    filtered: list[Document] = []
    # page_hits : nb de chunks déjà retenus par clé (source, page)
    page_hits: dict = {}

    for doc, score in results_with_scores:
        # FAISS distance L2 → similarité normalisée 0-1
        similarity = 1 / (1 + score)

        if similarity < SIMILARITY_THRESHOLD:
            continue

        if categorie and doc.metadata.get("categorie") != categorie:
            continue

        # Déduplication douce : max 3 chunks par page d'un même fichier
        # (était 2 — trop restrictif sur les grands PDF juridiques avec
        #  plusieurs articles pertinents par page)
        page_key = (doc.metadata.get("source", ""), doc.metadata.get("page", ""))
        if page_hits.get(page_key, 0) >= 3:
            continue

        doc.metadata["similarity_score"] = round(float(similarity), 3)
        filtered.append(doc)
        page_hits[page_key] = page_hits.get(page_key, 0) + 1

        if len(filtered) >= k:
            break

    q_display = query[:50] + "..." if len(query) > 50 else query
    logger.info(f"Recherche '{q_display}' → {len(filtered)} chunks pertinents trouvés")

    return filtered


def search_by_keyword(
    article_query: str,
    categorie: str | None = None,
    max_results: int = 5,
) -> list[Document]:
    """
    Recherche exacte d'un article de loi dans le docstore FAISS.

    Pourquoi : le modèle d'embedding traite les numéros d'articles comme
    des identifiants opaques. "Article L1272-4" ou "Article 6" n'ont aucun
    sens sémantique — la recherche vectorielle peut rater le bon chunk même
    quand il existe exactement dans l'index.

    Ce scan linéaire du docstore garantit un hit exact indépendamment du
    score sémantique.

    Pattern : lookahead négatif (?![0-9\\-.]) pour éviter que "Article 6"
    remonte aussi "Article 6-1" ou "Article 60".

    Args:
        article_query : ex. "Article L1272-4", "Article 6", "Article 111-1"
        categorie     : filtre optionnel sur la catégorie
        max_results   : nombre max de chunks retournés par article
    """
    vectorstore = get_vectorstore()

    # Lookahead négatif : "Article 6" ne matche PAS "Article 6-1" ni "Article 60"
    pattern = re.compile(
        re.escape(article_query) + r"(?![0-9\-\.])",
        re.IGNORECASE,
    )

    results: list[Document] = []
    for doc in vectorstore.docstore._dict.values():
        if not pattern.search(doc.page_content):
            continue
        if categorie and doc.metadata.get("categorie") != categorie:
            continue
        # Copie avec score 0.99 (match exact → priorité maximale dans le contexte)
        enriched = Document(
            page_content=doc.page_content,
            metadata={**doc.metadata, "similarity_score": 0.99},
        )
        results.append(enriched)
        if len(results) >= max_results:
            break

    if results:
        logger.info(f"[keyword] '{article_query}' → {len(results)} chunk(s) exact(s)")
    else:
        logger.warning(f"[keyword] '{article_query}' → 0 chunk trouvé dans le docstore")
    return results


def merge_with_keyword_results(
    semantic_docs: list[Document],
    keyword_docs: list[Document],
    k: int = TOP_K_RESULTS,
) -> list[Document]:
    """
    Fusionne résultats sémantiques et résultats keyword.

    Les chunks keyword (score 0.99 = match exact) sont placés EN PREMIER
    dans le contexte envoyé au LLM — il les voit en priorité et peut
    répondre précisément sur l'article demandé.

    Les résultats sémantiques complètent le contexte avec des chunks connexes.
    La déduplication évite les doublons.
    """

    def _key(doc: Document) -> str:
        return f"{doc.metadata.get('source')}|{doc.metadata.get('page')}|{doc.page_content[:80]}"

    seen: set[str] = set()
    merged: list[Document] = []

    # 1. Keyword results en tête (réponse exacte à la question sur l'article)
    for doc in keyword_docs:
        dk = _key(doc)
        if dk not in seen:
            seen.add(dk)
            merged.append(doc)

    # 2. Résultats sémantiques en complément
    for doc in semantic_docs:
        dk = _key(doc)
        if dk not in seen:
            seen.add(dk)
            merged.append(doc)

    logger.info(
        f"[merge] {len(keyword_docs)} keyword + {len(semantic_docs)} sémantique "
        f"→ {min(len(merged), k)} chunks finaux"
    )
    return merged[:k]


def format_sources(documents: list[Document]) -> list[dict]:
    """
    Formate les sources pour l'affichage dans le frontend.

    Returns:
        Liste de dicts avec source, page, catégorie, score
    """
    sources = []
    seen = set()

    for doc in documents:
        meta = doc.metadata
        key = f"{meta.get('source')}_{meta.get('page')}"

        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "fichier": str(meta.get("source", "Inconnu")),
                    "page": meta.get("page", "?"),
                    "categorie": str(meta.get("categorie", "Inconnu")),
                    "score": float(meta.get("similarity_score", 0)),
                    "extrait": doc.page_content[:150] + "...",
                }
            )

    return sources
