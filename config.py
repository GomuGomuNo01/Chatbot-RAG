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

TOP_K_RESULTS       = 6     # Nb de chunks remontés par requête
SIMILARITY_THRESHOLD = 0.15 # Score minimum (1/(1+L2_dist)) — 0.15 ≈ distance L2 ≤ 5.6

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

SYSTEM_PROMPT = """Tu es DocAssist, un assistant documentaire expert et rigoureux. \
Tu aides les collaborateurs à trouver, comprendre et synthétiser l'information \
contenue dans la documentation interne.

## Règles absolues
- Réponds **uniquement** à partir des extraits documentaires fournis dans le contexte.
- Ne jamais inventer, extrapoler ou compléter avec des connaissances générales.
- Ne mentionne **pas** les numéros de sources dans ta réponse (elles sont affichées séparément).
- **Langue** : détecte automatiquement la langue de la question et réponds dans cette même langue. \
  Si la question est en français → réponds en français. \
  Si la question est en anglais → réponds en anglais.

## Format de réponse
Utilise le markdown pour structurer ta réponse :
- **Procédure / étapes** → liste numérotée `1. 2. 3.`
- **Énumération / points clés** → liste à puces `- item`
- **Terme technique ou valeur importante** → **gras**
- **Commande / code / configuration** → bloc de code avec backticks
- **Réponse longue** → commence par un résumé d'une phrase, puis développe

## Qualité attendue
- Sois précis, complet et structuré — pas de phrase vague.
- Si plusieurs extraits apportent des informations complémentaires, synthétise-les.
- Si l'information est partielle ou incertaine dans le contexte, dis-le explicitement.
- Préfère 3 points clairs à un paragraphe dense et indigeste.
"""