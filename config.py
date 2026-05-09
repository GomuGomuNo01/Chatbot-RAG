"""
config.py — Configuration centralisée du projet
Tous les paramètres modifiables sont ici.
"""

import json
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

# Métadonnées des catégories personnalisées (créées via l'API)
CUSTOM_CATEGORIES_FILE = BASE_DIR / "data" / "custom_categories.json"

# Création automatique des dossiers nécessaires
for _dir in [
    DOCS_TECHNIQUE_DIR,
    DOCS_RH_DIR,
    DOCS_JURIDIQUE_DIR,
    FAISS_INDEX_DIR,
    BASE_DIR / "data",
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

TOP_K_RESULTS       = 10    # Nb de chunks dans le contexte final (multi_search fusionne N requêtes)
SIMILARITY_THRESHOLD = 0.12 # Score minimum (1/(1+L2_dist)) — 0.12 ≈ distance L2 ≤ 7.3
                            # Seuil abaissé pour les questions comparatives multi-requêtes

# ============================================================
# MÉMOIRE CONVERSATIONNELLE
# ============================================================

MEMORY_MAX_EXCHANGES = 7    # Nb d'échanges conservés en mémoire (étendu à 7)

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

# Palette par défaut pour les catégories personnalisées
_CUSTOM_EMOJIS  = ["📁", "🗂️", "📋", "🔖", "📊", "🗃️", "📌", "🏷️"]
_CUSTOM_COLORS  = ["#E85D04", "#7209B7", "#0077B6", "#2D6A4F", "#9B2226", "#AE2012"]


def _load_custom_categories() -> dict:
    """Charge les catégories personnalisées depuis le fichier JSON."""
    if CUSTOM_CATEGORIES_FILE.exists():
        try:
            data = json.loads(CUSTOM_CATEGORIES_FILE.read_text(encoding="utf-8"))
            return {k: {**v, "dir": DOCS_DIR / k} for k, v in data.items()}
        except Exception:
            pass
    return {}


def get_all_categories() -> dict:
    """
    Retourne toutes les catégories : hardcodées + personnalisées.
    À utiliser à la place de CATEGORIES quand le contexte de requête l'exige.
    """
    merged = dict(CATEGORIES)
    merged.update(_load_custom_categories())
    return merged


def delete_custom_category(key: str) -> None:
    """
    Supprime une catégorie personnalisée du fichier JSON.
    Ne touche pas au répertoire docs/{key}/ ni aux fichiers qu'il contient
    (géré par la route API qui appelle cette fonction).
    Lève ValueError si la catégorie est native ou introuvable.
    """
    if key in CATEGORIES:
        raise ValueError(f"La catégorie '{key}' est native et ne peut pas être supprimée.")

    existing: dict = {}
    if CUSTOM_CATEGORIES_FILE.exists():
        try:
            existing = json.loads(CUSTOM_CATEGORIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if key not in existing:
        raise ValueError(f"Catégorie personnalisée '{key}' introuvable.")

    del existing[key]
    CUSTOM_CATEGORIES_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def register_custom_category(key: str, label: str, emoji: str, couleur: str) -> None:
    """
    Persiste une nouvelle catégorie personnalisée sur disque.
    Crée aussi le répertoire docs/{key}/.
    """
    cat_dir = DOCS_DIR / key
    cat_dir.mkdir(parents=True, exist_ok=True)

    # Lire le fichier existant
    existing: dict = {}
    if CUSTOM_CATEGORIES_FILE.exists():
        try:
            existing = json.loads(CUSTOM_CATEGORIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Ne pas écraser les 3 catégories natives
    if key in CATEGORIES:
        raise ValueError(f"La catégorie '{key}' est réservée.")

    existing[key] = {"label": label, "emoji": emoji, "couleur": couleur}
    CUSTOM_CATEGORIES_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# ============================================================
# STOCKAGE EXTERNE
# ============================================================

# Cloudflare R2 — stockage des fichiers sources (PDF, DOCX, TXT)
# Laisser vide en local : le mode filesystem local est utilisé à la place.
R2_ACCOUNT_ID        = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID     = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME       = os.getenv("R2_BUCKET_NAME", "chatbot-rag-docs")

# HuggingFace Hub — persistance de l'index FAISS entre les redémarrages
# Créer un dépôt privé de type "dataset" sur huggingface.co
HF_TOKEN   = os.getenv("HF_TOKEN", "")
HF_REPO_ID = os.getenv("HF_REPO_ID", "")  # ex: "monpseudo/chatbot-rag-index"


def is_r2_enabled() -> bool:
    """R2 actif uniquement si toutes les variables sont renseignées."""
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)


def is_hf_enabled() -> bool:
    """HuggingFace Hub actif uniquement si token et repo sont renseignés."""
    return bool(HF_TOKEN and HF_REPO_ID)


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

SYSTEM_PROMPT = """Tu es DocAssist, un assistant documentaire expert. \
Tu exploites la documentation interne (technique, RH, juridique) pour aider \
les collaborateurs à trouver, comprendre et synthétiser des informations précises.

## Règles fondamentales

1. **Sources exclusives** — Réponds uniquement à partir des extraits fournis dans le contexte. \
Ne jamais inventer, supposer ou compléter avec des connaissances non présentes dans les extraits.
2. **Exhaustivité** — Si plusieurs extraits apportent des éléments complémentaires, \
synthétise-les tous. Ne laisse pas d'information pertinente de côté.
3. **Honnêteté** — Si l'information est absente, partielle ou ambiguë dans les extraits, \
dis-le explicitement : *« Les documents disponibles ne précisent pas… »* \
Ne dis PAS que l'information est absente si tu peux la déduire des extraits fournis.
4. **Synthèse comparative** — Si la question compare deux concepts (ex. : « différence entre CDI et CDD ») \
et que les extraits définissent chaque concept séparément (sans paragraphe de comparaison explicite), \
construis toi-même la comparaison à partir des définitions et caractéristiques disponibles. \
Commence par résumer chaque concept, puis présente les différences clés dans un tableau ou une liste contrastive.
5. **Pas de référence aux sources** — Ne cite pas les numéros d'extraits (ex. [1], [2], \
Extrait 3…) — elles sont affichées séparément dans l'interface.
6. **Langue** — Réponds impérativement dans la même langue que la question.

## Format de réponse

Choisis le format adapté à la complexité de la réponse :

| Situation | Format |
|-----------|--------|
| Procédure / étapes ordonnées | Liste numérotée `1. 2. 3.` |
| Points clés / énumération | Liste à puces `- item` |
| Comparaison de 3+ éléments | Tableau Markdown |
| Valeur importante / terme clé | **gras** |
| Commande / code / chemin de fichier | `bloc de code` |
| Réponse > 3 points | Phrase de synthèse en tête, puis développement |
| Réponse ≤ 2 lignes | Réponse directe, sans structure superflue |

## Exigences qualité

- **Précis et actionnable** : préfère *« Exécutez la commande X »* à *« X peut être exécuté »*
- **Structuré** : 3 points clairs valent mieux qu'un paragraphe dense
- **Complet** : si une procédure comporte des prérequis ou des mises en garde, mentionne-les
- **Synthétique** : commence par l'essentiel, détaille ensuite
"""