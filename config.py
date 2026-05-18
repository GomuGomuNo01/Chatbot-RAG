"""
config.py — Configuration centralisée du projet (refonte v2)

Toute la logique de "catégories prédéfinies" (technique / rh / juridique) a été
supprimée. Le système repose désormais sur des Workspaces 100 % utilisateur :
chaque workspace est créé librement, sans schéma fixe, et stocké dans
`data/workspaces.json`.
"""

import hashlib
import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================
# CHEMINS
# ============================================================

BASE_DIR = Path(__file__).parent.resolve()
DOCS_DIR = BASE_DIR / "docs"
FAISS_INDEX_DIR = BASE_DIR / "data" / "faiss_index"
BM25_INDEX_FILE = BASE_DIR / "data" / "bm25_index.pkl"
RESPONSE_CACHE_FILE = BASE_DIR / "data" / "response_cache.json"
WORKSPACES_FILE = BASE_DIR / "data" / "workspaces.json"
DOC_METADATA_FILE = BASE_DIR / "data" / "documents_meta.json"

for _dir in (DOCS_DIR, FAISS_INDEX_DIR, BASE_DIR / "data"):
    _dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# MODÈLES
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_TEMPERATURE = 0.1
ANTHROPIC_MAX_TOKENS = 1024

EMBEDDING_MODEL = "intfloat/multilingual-e5-base"

# Reranker — modèle cross-encoder via HuggingFace InferenceClient (0 RAM locale)
RERANKER_MODEL = "BAAI/bge-reranker-base"
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"

# ============================================================
# CHUNKING — Découpage des documents
# ============================================================

CHUNK_SIZE = 900
CHUNK_OVERLAP = 220
CHUNK_MIN_LENGTH = 80

# Séparateurs génériques, sans biais légal/juridique.
# L'ordre va du plus fort (sections) au plus faible (caractère).
CHUNK_SEPARATORS = [
    "\n\n# ",
    "\n\n## ",
    "\n\n### ",
    "\n\n#### ",
    "\n# ",
    "\n## ",
    "\n### ",
    "\n\n",
    "\n",
    ". ",
    "! ",
    "? ",
    "; ",
    ", ",
    " ",
    "",
]


def get_chunk_config_fingerprint() -> str:
    """Empreinte MD5 de la config de chunking (déclenche un auto-reindex si elle change)."""
    key = json.dumps(
        {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "separators": CHUNK_SEPARATORS,
            "min_length": CHUNK_MIN_LENGTH,
        },
        sort_keys=True,
    )
    return hashlib.md5(key.encode()).hexdigest()


# ============================================================
# RETRIEVAL — Recherche hybride (sémantique + BM25)
# ============================================================

TOP_K_RESULTS = 6  # chunks gardés après reranking pour le LLM (↓ tokens input LLM)
TOP_K_RETRIEVAL = 20  # pool initial par index (BM25 et FAISS)
SIMILARITY_THRESHOLD = 0.20  # seuil min sur la similarité FAISS normalisée
HYBRID_RRF_K = 30  # constante k du Reciprocal Rank Fusion
HYBRID_BM25_WEIGHT = 0.45  # poids du BM25 dans la fusion (0 = full vectoriel, 1 = full BM25)
RERANK_TOP_N = 12  # nb de candidats envoyés au reranker (après fusion)

# ============================================================
# CACHE DES RÉPONSES (cost saver)
# ============================================================

RESPONSE_CACHE_ENABLED = True
RESPONSE_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 jours
RESPONSE_CACHE_MAX_ENTRIES = 500
RESPONSE_CACHE_SIM_THRESHOLD = (
    0.92  # similarité cosinus min (doublée d'un contrôle lexical dans cache.py)
)

# ============================================================
# MÉMOIRE CONVERSATIONNELLE
# ============================================================

MEMORY_MAX_EXCHANGES = 4

# ============================================================
# WORKSPACES — entièrement utilisateur, aucune valeur "native"
# ============================================================

_WORKSPACE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")

# Identifiants réservés (collisions avec routes API / dossiers système)
RESERVED_WORKSPACE_KEYS: frozenset[str] = frozenset(
    {
        "api",
        "admin",
        "docs",
        "static",
        "data",
        "index",
        "health",
        "chat",
        "documents",
        "workspaces",
        "categories",
        "settings",
        "config",
        "all",
        "upload",
        "reindex",
        "status",
        "search",
    }
)


def _load_workspaces_raw() -> dict:
    """Charge le registre des workspaces depuis le JSON. Toujours un dict (vide si absent)."""
    if WORKSPACES_FILE.exists():
        try:
            data = json.loads(WORKSPACES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"workspaces.json corrompu : {e} — registre vide.")
    return {}


def _save_workspaces_raw(data: dict) -> None:
    WORKSPACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_valid_workspace_key(key: str) -> bool:
    return bool(_WORKSPACE_KEY_RE.match(key)) and key not in RESERVED_WORKSPACE_KEYS


def get_workspaces() -> dict[str, dict]:
    """
    Retourne tous les workspaces enregistrés.
    Structure : {key: {"label": str, "emoji": str, "couleur": str, "dir": Path}}.
    """
    raw = _load_workspaces_raw()
    return {key: {**meta, "dir": DOCS_DIR / key} for key, meta in raw.items()}


def get_workspace(key: str) -> dict | None:
    return get_workspaces().get(key)


def register_workspace(key: str, label: str, emoji: str = "📁", couleur: str = "#6B7280") -> dict:
    """
    Crée un nouveau workspace. Lève ValueError si la clé est invalide ou déjà prise.
    """
    if not is_valid_workspace_key(key):
        raise ValueError(
            f"Identifiant invalide : « {key} ». "
            "Utilisez 2-32 caractères en minuscules, chiffres, tirets ou underscores. "
            "Identifiants réservés interdits."
        )

    existing = _load_workspaces_raw()
    if key in existing:
        raise ValueError(f"Le workspace « {key} » existe déjà.")

    label_clean = (label or key).strip()
    for k, meta in existing.items():
        if meta.get("label", "").strip().lower() == label_clean.lower():
            raise ValueError(
                f"Un workspace nommé « {meta['label']} » existe déjà (identifiant : {k})."
            )

    meta = {
        "label": label_clean,
        "emoji": emoji or "📁",
        "couleur": couleur or "#6B7280",
    }
    existing[key] = meta
    _save_workspaces_raw(existing)

    (DOCS_DIR / key).mkdir(parents=True, exist_ok=True)
    return {**meta, "dir": DOCS_DIR / key}


def delete_workspace(key: str) -> None:
    """Supprime un workspace du registre. Ne touche pas aux fichiers (géré par la route API)."""
    existing = _load_workspaces_raw()
    if key not in existing:
        raise ValueError(f"Workspace « {key} » introuvable.")
    del existing[key]
    _save_workspaces_raw(existing)


def auto_provision_workspaces_from_disk() -> int:
    """
    À l'init : si workspaces.json est absent mais que des dossiers existent dans docs/,
    enregistre automatiquement chaque dossier comme workspace avec des métadonnées par défaut.
    Permet de récupérer un projet existant (ex. legacy docs/technique, docs/rh, docs/juridique)
    sans intervention manuelle. Retourne le nombre de workspaces créés.
    """
    if _load_workspaces_raw():
        return 0
    if not DOCS_DIR.exists():
        return 0

    created = 0
    palette = ["#2E86AB", "#28A745", "#6F42C1", "#E85D04", "#7209B7", "#0077B6", "#2D6A4F"]
    for child in sorted(DOCS_DIR.iterdir()):
        if not child.is_dir():
            continue
        key = child.name
        if not is_valid_workspace_key(key):
            continue
        try:
            register_workspace(
                key=key,
                label=key.replace("-", " ").replace("_", " ").title(),
                emoji="📁",
                couleur=palette[created % len(palette)],
            )
            created += 1
        except ValueError:
            continue
    if created:
        logger.info(
            f"[workspaces] Auto-provisionnés : {created} dossier(s) existant(s) → workspaces"
        )
    return created


# ============================================================
# STOCKAGE EXTERNE
# ============================================================

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "chatbot-rag-docs")

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_REPO_ID = os.getenv("HF_REPO_ID", "")


def is_r2_enabled() -> bool:
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)


def is_hf_enabled() -> bool:
    return bool(HF_TOKEN and HF_REPO_ID)


# ============================================================
# API FastAPI
# ============================================================

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", 8000))
API_TITLE = "DocAssist — Assistant Documentaire RAG"
API_VERSION = "2.0.0"
API_DESCRIPTION = (
    "Assistant conversationnel RAG. Crée tes workspaces, importe tes documents, "
    "et pose tes questions. Le système trouve, synthétise et cite ses sources."
)

# ============================================================
# PROMPT SYSTÈME — Générique, sans biais de domaine
# ============================================================

SYSTEM_PROMPT = """Tu es DocAssist, un assistant documentaire fondé sur les documents \
fournis par l'utilisateur. Ta mission : répondre avec précision en t'appuyant \
exclusivement sur les extraits remis dans le contexte.

## Règles fondamentales

1. **Sources exclusives** — Réponds uniquement à partir des extraits fournis. \
N'invente jamais, ne suppose pas, ne complète pas avec des connaissances externes. \
Si l'information n'est pas dans les extraits, dis-le explicitement.
2. **Exhaustivité** — Si plusieurs extraits apportent des éléments complémentaires, \
synthétise-les tous. Ne laisse pas d'information pertinente de côté.
3. **Honnêteté** — Si l'information est partielle ou ambiguë, signale-le \
(« Les documents disponibles précisent X mais ne mentionnent pas Y »). \
Ne dis pas qu'une information est absente si elle est en fait déductible des extraits.
4. **Synthèse comparative** — Si la question demande une comparaison (ex. X vs Y) \
et que les extraits définissent chaque élément séparément, construis la comparaison \
toi-même à partir des éléments disponibles, sous forme de tableau ou de liste contrastive.
5. **Pas de référence aux numéros d'extraits** — Ne cite pas « [1] », « Extrait 3 », etc. \
Les sources sont affichées séparément dans l'interface.
6. **Langue** — Réponds dans la même langue que la question. Exception : si le document \
source est en anglais et la question en français, réponds en français en conservant \
les termes techniques anglais tels quels (ex : "le bean", "l'autoconfiguration", "le endpoint").
7. **Reformulation fidèle** — Cite textuellement les passages clés (définitions, valeurs, \
articles, identifiants, formules). Reformule uniquement quand cela clarifie sans dénaturer.

## Format de réponse

Adapte le format à la question :

| Situation | Format |
|-----------|--------|
| Procédure / étapes ordonnées | Liste numérotée `1. 2. 3.` |
| Énumération non ordonnée | Liste à puces `- item` |
| Comparaison de 3+ éléments | Tableau Markdown |
| Données tabulaires (grilles, barèmes, classifications) | Tableau Markdown complet |
| Valeur ou terme clé | **gras** |
| Code source (Java, PHP, JavaScript, YAML, XML, SQL…) | Bloc de code avec l'identifiant exact du langage : ` ```java `, ` ```php `, ` ```javascript `, ` ```yaml `, ` ```xml `, ` ```sql `… |
| Réponse > 3 points | Phrase de synthèse en tête, puis détail |
| Réponse ≤ 2 lignes | Réponse directe, sans structure superflue |

## Comportement selon le type de document

**Documents juridiques** (codes, lois, conventions collectives, constitutions) :
- Reproduis les numéros d'articles exactement tels qu'ils apparaissent dans les extraits \
(ex : « Article L1234-5 », « Article 111-1 », « Article 1er »).
- Pour les dispositions légales importantes, cite la formulation exacte entre guillemets \
plutôt que de paraphraser — la précision du texte a valeur juridique.
- Si plusieurs articles se complètent ou se contredisent, signale-le explicitement.

**Documentation technique** (frameworks, langages de programmation, APIs) :
- Encadre systématiquement tout extrait de code dans un bloc avec le bon identifiant \
de langage (java, php, javascript, yaml, xml, bash…).
- Si les extraits mentionnent une version spécifique du logiciel ou de la bibliothèque, \
indique-la dans ta réponse (ex : "selon la documentation Spring Boot 3.2.x…").
- Distingue la syntaxe ancienne de la syntaxe moderne si les extraits les présentent toutes deux.

**Profil / CV / fiche personnelle** :
- Présente les informations dans l'ordre et la structure du document source.
- Reproduis les intitulés de postes, diplômes et compétences tels qu'ils sont écrits.
- Ne synthétise pas ou n'interprète pas les données personnelles — cite-les telles quelles.

## Bonnes pratiques

- **Identifiants** (numéros d'article, références, codes, dates, montants, coordonnées) : \
reproduis-les tels quels, sans les modifier.
- **Citations** : si l'utilisateur demande le texte exact d'une section, reproduis-le \
intégralement à partir des extraits.
- **Lookup inverse** : si l'utilisateur fournit un extrait et demande à quoi il \
correspond (article, fiche, document), identifie la source qui contient ce texte \
et indique son intitulé/numéro.
- **Réponse vide** : si aucun extrait ne contient l'information demandée, dis-le \
clairement et propose une reformulation utile.
- **Précis et actionnable** : préfère « Exécutez X » à « X peut être exécuté ».
- **Structuré** : 3 points clairs valent mieux qu'un paragraphe dense.
- **Synthétique** : commence par l'essentiel, détaille ensuite.
"""
