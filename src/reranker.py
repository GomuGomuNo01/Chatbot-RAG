"""
reranker.py — Reranking des candidats par cross-encoder.

Stratégie :
- Production : HuggingFace InferenceClient sur BAAI/bge-reranker-base (0 RAM locale).
- Fallback : si le reranker ne répond pas, on conserve l'ordre fusionné (RRF).
  Aucun crash, juste un avertissement.
- Optionnel : activable/désactivable via RERANKER_ENABLED.
"""

import logging
import os
from typing import cast

from config import RERANKER_ENABLED, RERANKER_MODEL
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_reranker_client = None
_reranker_unavailable = False


def _get_client():
    """Singleton HuggingFace InferenceClient pour le reranker."""
    global _reranker_client, _reranker_unavailable
    if _reranker_unavailable:
        return None
    if _reranker_client is not None:
        return _reranker_client

    token = os.getenv("HF_TOKEN", "")
    if not token:
        logger.info("[reranker] HF_TOKEN absent — reranker désactivé.")
        _reranker_unavailable = True
        return None

    try:
        from huggingface_hub import InferenceClient

        _reranker_client = InferenceClient(model=RERANKER_MODEL, token=token)
        logger.info(f"[reranker] Client initialisé : {RERANKER_MODEL}")
        return _reranker_client
    except Exception as e:
        logger.warning(f"[reranker] Initialisation échouée : {e}")
        _reranker_unavailable = True
        return None


def rerank(
    query: str,
    documents: list[Document],
    top_k: int,
) -> list[Document]:
    """
    Réordonne `documents` selon leur pertinence au regard de `query`.
    Si le reranker n'est pas disponible, retourne les `top_k` premiers documents inchangés.
    """
    if not documents:
        return []
    if not RERANKER_ENABLED or len(documents) <= top_k:
        return documents[:top_k]

    client = _get_client()
    if client is None:
        return documents[:top_k]

    # Tronque chaque chunk pour rester sous la limite tokens du cross-encoder
    pairs = [(query, doc.page_content[:1200]) for doc in documents]

    try:
        # InferenceClient.sentence_similarity prend (source, sentences) mais on a besoin
        # d'un cross-encoder. On utilise donc l'API generic text-classification du reranker.
        scores = _call_reranker(client, pairs)
    except Exception as e:
        logger.warning(f"[reranker] Appel échoué — ordre RRF conservé : {e}")
        return documents[:top_k]

    if scores is None or len(scores) != len(documents):
        return documents[:top_k]

    # Si tous les scores sont 0.0, l'API a échoué silencieusement → ordre RRF conservé
    # (évite que format_sources affiche _FLOOR=35% pour toutes les sources)
    if not any(s != 0.0 for s in scores):
        logger.warning("[reranker] Tous les scores sont 0.0 — API indisponible, ordre RRF conservé")
        return documents[:top_k]

    enriched = list(zip(documents, scores))
    enriched.sort(key=lambda x: x[1], reverse=True)
    ordered: list[Document] = []
    for doc, score in enriched[:top_k]:
        meta = dict(doc.metadata)
        meta["rerank_score"] = float(score)
        ordered.append(Document(page_content=doc.page_content, metadata=meta))
    logger.info(f"[reranker] {len(documents)} candidats → top {top_k} (cross-encoder)")
    return ordered


def _call_reranker(client, pairs: list[tuple[str, str]]) -> list[float] | None:
    """
    POST direct à l'API HF Inference pour le cross-encoder (sans InferenceClient).

    InferenceClient.sentence_similarity() émet un GET de métadonnées avant chaque
    appel — soit N+1 requêtes pour N passages. On bypasse ça avec requests brut
    pour n'avoir qu'un seul POST batch.
    """
    import requests

    token = os.getenv("HF_TOKEN", "")
    url = f"https://api-inference.huggingface.co/models/{RERANKER_MODEL}"
    hdrs = {"Authorization": f"Bearer {token}"}

    queries  = [p[0] for p in pairs]
    passages = [p[1] for p in pairs]

    # Appel batch : un seul POST pour tous les passages.
    if all(q == queries[0] for q in queries):
        try:
            resp = requests.post(
                url, headers=hdrs,
                json={"inputs": {"source_sentence": queries[0], "sentences": passages}},
                timeout=12,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"[reranker] batch response type={type(data).__name__} len={len(data) if isinstance(data, list) else 'N/A'}")
                if isinstance(data, list) and all(isinstance(s, (int, float)) for s in data):
                    logger.info(f"[reranker] batch scores: {[round(s,4) for s in data]}")
                    return [float(s) for s in data]
                # Certains modèles retournent [{"score": x, "label": "..."}, ...]
                if isinstance(data, list) and all(isinstance(s, dict) for s in data):
                    scores_from_dicts = [float(s.get("score", 0.0)) for s in data]
                    logger.info(f"[reranker] batch scores (dict): {[round(s,4) for s in scores_from_dicts]}")
                    return scores_from_dicts
                logger.warning(f"[reranker] batch format inattendu : {str(data)[:200]}")
            else:
                logger.warning(f"[reranker] batch HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"[reranker] batch exception : {e}")

    # Fallback : appels individuels si le batch échoue.
    results: list[float] = []
    for q, p in pairs:
        try:
            resp = requests.post(
                url, headers=hdrs,
                json={"inputs": {"source_sentence": q, "sentences": [p]}},
                timeout=6,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    val = data[0]
                    results.append(float(val.get("score", val) if isinstance(val, dict) else val))
                else:
                    logger.warning(f"[reranker] indiv format inattendu : {str(data)[:100]}")
                    results.append(0.0)
            else:
                logger.warning(f"[reranker] indiv HTTP {resp.status_code}: {resp.text[:100]}")
                results.append(0.0)
        except Exception as e:
            logger.warning(f"[reranker] indiv exception : {e}")
            results.append(0.0)
    return results
