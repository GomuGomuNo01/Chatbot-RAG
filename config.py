"""
config.py — Configuration centralisée du projet
Tous les paramètres modifiables sont ici.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CHEMINS
# ============================================================

BASE_DIR   = Path(__file__).parent.resolve()

# Documents PDF par catégorie
DOCS_DIR            = BASE_DIR / "docs"
DOCS_TECHNIQUE_DIR  = DOCS_DIR / "technique"
DOCS_RH_DIR         = DOCS_DIR / "rh"
DOCS_JURIDIQUE_DIR  = DOCS_DIR / "juridique"

# Index FAISS persisté
FAISS_INDEX_DIR = BASE_DIR / "data" / "faiss_index"

# Création automatique des dossiers nécessaires
for _dir in [
    DOCS_TECHNIQUE_DIR,
    DOCS_RH_DIR,
    DOCS_JURIDIQUE_DIR,
    FAISS_INDEX_DIR
]:
    _dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# MODÈLES
# ============================================================

# LLM via Groq (gratuit)
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.1        # Faible = réponses précises et stables
GROQ_MAX_TOKENS  = 1024

# Embeddings locaux (gratuit, multilingue FR/EN)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ============================================================
# CHUNKING — Découpage des documents
# ============================================================

CHUNK_SIZE    = 1000   # Nb de caractères par chunk
CHUNK_OVERLAP = 200    # Chevauchement pour conserver le contexte
                       # entre deux chunks consécutifs

# ============================================================
# RETRIEVAL — Recherche sémantique
# ============================================================

TOP_K_RESULTS       = 4     # Nb de chunks remontés par requête
SIMILARITY_THRESHOLD = 0.3  # Score minimum pour considérer un chunk
                             # pertinent (entre 0 et 1)

# ============================================================
# MÉMOIRE CONVERSATIONNELLE
# ============================================================

MEMORY_MAX_EXCHANGES = 5    # Nb d'échanges conservés en mémoire

# ============================================================
# CATÉGORIES DE DOCUMENTS
# ============================================================

CATEGORIES = {
    "technique":  {
        "label":    "Documentation Technique",
        "dir":      DOCS_TECHNIQUE_DIR,
        "emoji":    "💻",
        "couleur":  "#2E86AB"
    },
    "rh": {
        "label":    "Ressources Humaines",
        "dir":      DOCS_RH_DIR,
        "emoji":    "👥",
        "couleur":  "#28A745"
    },
    "juridique": {
        "label":    "Documents Juridiques",
        "dir":      DOCS_JURIDIQUE_DIR,
        "emoji":    "⚖️",
        "couleur":  "#6F42C1"
    }
}

# ============================================================
# API FastAPI
# ============================================================

API_HOST    = os.getenv("API_HOST", "0.0.0.0")
API_PORT    = int(os.getenv("PORT", 8000))
API_TITLE   = "Chatbot RAG — Assistant Documentaire"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "API REST d'un assistant conversationnel basé sur RAG. "
    "Répond aux questions sur des documents PDF internes "
    "en citant ses sources."
)

# ============================================================
# PROMPT SYSTÈME
# ============================================================

SYSTEM_PROMPT = """Tu es un assistant documentaire interne pour une entreprise.
Tu réponds aux questions des collaborateurs en te basant UNIQUEMENT
sur les documents fournis dans le contexte.

Règles strictes :
- Si la réponse est dans le contexte : réponds de manière claire et concise
- Si la réponse N'EST PAS dans le contexte : réponds exactement
  "Je n'ai pas trouvé cette information dans les documents disponibles."
- Ne jamais inventer ou extrapoler d'informations
- Réponds toujours en français
- Cite toujours la source à la fin de ta réponse

Format de réponse :
[Ta réponse]

Source : [nom du document] — Page [numéro]
"""