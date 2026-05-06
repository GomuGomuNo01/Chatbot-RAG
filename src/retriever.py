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

def search(
    query: str,
    categorie: Optional[str] = None,
    k: int = TOP_K_RESULTS
) -> List[Document]:
    """
    Recherche les chunks les plus pertinents pour une question.

    Args:
        query     : question de l'utilisateur
        categorie : filtre optionnel ("technique", "rh", "juridique")
        k         : nombre de résultats à retourner

    Returns:
        Liste de Documents triés par pertinence décroissante
    """
    vectorstore = get_vectorstore()

    # Recherche avec score de similarité
    results_with_scores = vectorstore.similarity_search_with_score(
        query=query,
        k=k * 2  # On récupère plus pour filtrer ensuite
    )

    # Filtrer par seuil de similarité et catégorie
    filtered = []
    for doc, score in results_with_scores:

        # FAISS retourne une distance L2 — plus c'est bas, plus c'est proche
        # On convertit en score de similarité 0-1
        similarity = 1 / (1 + score)

        if similarity < SIMILARITY_THRESHOLD:
            continue

        if categorie and doc.metadata.get("categorie") != categorie:
            continue

        doc.metadata["similarity_score"] = round(similarity, 3)
        filtered.append(doc)

        if len(filtered) >= k:
            break

    logger.info(
        f"Recherche '{query[:50]}...' "
        f"→ {len(filtered)} chunks pertinents trouvés"
        if len(query) > 50 else
        f"Recherche '{query}' "
        f"→ {len(filtered)} chunks pertinents trouvés"
    )

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
                "fichier":   meta.get("source", "Inconnu"),
                "page":      meta.get("page", "?"),
                "categorie": meta.get("categorie", "Inconnu"),
                "score":     meta.get("similarity_score", 0),
                "extrait":   doc.page_content[:150] + "..."
            })

    return sources