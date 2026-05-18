"""utils.py — Helpers partagés (logging, formatage de contexte/sources)."""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "chatbot-rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


def format_sources_for_display(sources: list) -> str:
    """Sources en texte lisible (CLI)."""
    if not sources:
        return "Aucune source trouvée."
    lines = ["\n--- Sources ---"]
    for i, src in enumerate(sources, 1):
        score_pct = int(src.get("score", 0) * 100)
        ws = src.get("workspace") or "?"
        lines.append(
            f"{i}. [{ws}] {src.get('fichier', '?')} — Page {src.get('page', '?')} "
            f"(pertinence : {score_pct}%)"
        )
        if src.get("extrait"):
            lines.append(f"   > {src['extrait'][:120]}…")
    return "\n".join(lines)


_MAX_CHUNK_CHARS = 600  # tronque chaque chunk pour limiter les tokens envoyés au LLM


def format_context_from_docs(documents: list) -> str:
    """Assemble les chunks en bloc structuré pour le prompt LLM."""
    if not documents:
        return "Aucun contexte disponible."
    parts = []
    for i, doc in enumerate(documents, 1):
        meta = doc.metadata
        fichier = Path(meta.get("source", "Inconnu")).name
        page = meta.get("page", "?")
        ws = meta.get("workspace", "")
        header = f"[{i}] {fichier} · p.{page}" + (f" · {ws}" if ws else "")
        content = doc.page_content.strip()
        if len(content) > _MAX_CHUNK_CHARS:
            content = content[:_MAX_CHUNK_CHARS] + "…"
        parts.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(parts)
