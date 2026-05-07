"""
Utils : fonctions utilitaires partagées
"""

import logging
import sys
from pathlib import Path

# ============================================================
# CONFIGURATION DU LOGGER GLOBAL
# ============================================================

def setup_logger(name: str = "chatbot-rag") -> logging.Logger:
    """Configure et retourne un logger formaté."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            )
        )
        logger.addHandler(handler)

    return logger


# ============================================================
# FORMATAGE DES SOURCES
# ============================================================

def format_sources_for_display(sources: list) -> str:
    """
    Formate les sources en texte lisible pour le terminal.

    Args:
        sources : liste de dicts retournés par retriever.format_sources()

    Returns:
        str formaté pour affichage
    """
    if not sources:
        return "Aucune source trouvée."

    lines = ["\n--- Sources ---"]
    for i, src in enumerate(sources, 1):
        score_pct = int(src.get("score", 0) * 100)
        lines.append(
            f"{i}. [{src['categorie'].upper()}] "
            f"{src['fichier']} — Page {src['page']} "
            f"(pertinence : {score_pct}%)"
        )
        if src.get("extrait"):
            lines.append(f"   > {src['extrait'][:100]}...")

    return "\n".join(lines)


def format_context_from_docs(documents: list) -> str:
    """
    Assemble les chunks en un bloc de contexte structuré pour le prompt LLM.
    Chaque extrait est clairement délimité avec ses métadonnées.
    """
    if not documents:
        return "Aucun contexte disponible."

    parts = []
    for i, doc in enumerate(documents, 1):
        meta      = doc.metadata
        fichier   = Path(meta.get("source", "Inconnu")).name
        page      = meta.get("page", "?")
        categorie = meta.get("categorie", "").upper()
        score     = meta.get("similarity_score", 0)

        header = (
            f"### Extrait {i}/{len(documents)} "
            f"[{categorie} · {fichier} · p.{page} · {int(score * 100)}%]"
        )
        parts.append(f"{header}\n{doc.page_content.strip()}")

    return "\n\n---\n\n".join(parts)