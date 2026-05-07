"""
Retriever : recherche sémantique dans l'index FAISS
"""

import logging
from typing import List, Optional, cast
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from src.indexer import load_index
from config import TOP_K_RESULTS, SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

# Instance globale — évite de recharger l'index à chaque requête
_vectorstore_instance: Optional[FAISS] = None

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
    queries: List[str],
    categorie: Optional[str] = None,
    k: int = TOP_K_RESULTS,
) -> List[Document]:
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

    seen_ids: dict[str, float] = {}   # page_key → meilleur score
    doc_map: dict[str, Document] = {} # page_key → document

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

    merged = sorted(doc_map.values(), key=lambda d: d.metadata.get("similarity_score", 0), reverse=True)
    logger.info(f"multi_search({len(queries)} requêtes) → {len(merged)} chunks uniques (top {k})")
    return merged[:k]


def search(
    query: str,
    categorie: Optional[str] = None,
    k: int = TOP_K_RESULTS
) -> List[Document]:
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
        k=k * 3
    )

    filtered: List[Document] = []
    # page_hits : nb de chunks déjà retenus par clé (source, page)
    page_hits: dict = {}

    for doc, score in results_with_scores:
        # FAISS distance L2 → similarité normalisée 0-1
        similarity = 1 / (1 + score)

        if similarity < SIMILARITY_THRESHOLD:
            continue

        if categorie and doc.metadata.get("categorie") != categorie:
            continue

        # Déduplication douce : max 2 chunks par page d'un même fichier
        page_key = (
            doc.metadata.get("source", ""),
            doc.metadata.get("page", "")
        )
        if page_hits.get(page_key, 0) >= 2:
            continue

        doc.metadata["similarity_score"] = round(float(similarity), 3)
        filtered.append(doc)
        page_hits[page_key] = page_hits.get(page_key, 0) + 1

        if len(filtered) >= k:
            break

    q_display = query[:50] + "..." if len(query) > 50 else query
    logger.info(f"Recherche '{q_display}' → {len(filtered)} chunks pertinents trouvés")

    return filtered


def format_sources(documents: List[Document]) -> List[dict]:
    """
    Formate les sources pour l'affichage dans le frontend.

    Returns:
        Liste de dicts avec source, page, catégorie, score
    """
    sources = []
    seen    = set()

    for doc in documents:
        meta = doc.metadata
        key  = f"{meta.get('source')}_{meta.get('page')}"

        if key not in seen:
            seen.add(key)
            sources.append({
                "fichier":   str(meta.get("source", "Inconnu")),
                "page":      meta.get("page", "?"),
                "categorie": str(meta.get("categorie", "Inconnu")),
                "score":     float(meta.get("similarity_score", 0)),
                "extrait":   doc.page_content[:150] + "..."
            })

    return sources