<div align="center">

# DocAssist

### Assistant IA sur documents — posez une question, obtenez une réponse sourcée

<br>

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white&style=flat-square)](https://langchain.com)
[![Claude Haiku](https://img.shields.io/badge/Claude%20Haiku-CC785C?logo=anthropic&logoColor=white&style=flat-square)](https://console.anthropic.com)
[![FAISS](https://img.shields.io/badge/FAISS%20%2B%20BM25-0078D4?logo=meta&logoColor=white&style=flat-square)](https://github.com/facebookresearch/faiss)
[![CI](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml)
[![HF Spaces](https://img.shields.io/badge/Live%20Demo-HuggingFace-FFD21E?logo=huggingface&logoColor=black&style=flat-square)](https://huggingface.co/spaces/GomuGomuNo01/chatbot-rag)

<br>

**[🚀 Démo en ligne](https://huggingface.co/spaces/GomuGomuNo01/chatbot-rag)** &nbsp;·&nbsp; **[📖 API Swagger](https://gomugomuNo01-chatbot-rag.hf.space/docs)**

<br>

</div>

---

## Le problème

Dans une organisation, l'information est éparpillée dans des dizaines de fichiers : contrats, guides techniques, règlements, fiches de poste, conventions collectives. Retrouver une réponse précise prend du temps — et souvent, on ne sait même pas dans quel fichier chercher.

**DocAssist résout ça en quelques secondes.** Importez vos documents, posez votre question : l'assistant répond avec précision et indique exactement dans quel fichier, à quelle page, il a trouvé l'information.

> **L'IA refuse d'inventer** : si la réponse n'est pas dans vos documents, elle le dit explicitement plutôt que de halluciner.

---

## Fonctionnalités

| | |
|:---:|:---|
| 🎯 | **Réponses sourcées** — chaque réponse cite le fichier, la page et l'extrait exact utilisé |
| 📂 | **Multi-formats** — PDF (jusqu'à 500 pages), Word (.docx), texte brut (.txt), Markdown (.md) |
| 🗂️ | **Workspaces libres** — créez autant de thèmes que vous voulez (RH, juridique, technique…) sans schéma imposé |
| 🔍 | **Recherche hybride** — combine recherche sémantique (FAISS) et lexicale (BM25) pour ne rien rater |
| 🏆 | **Reranking cross-encoder** — classe les résultats par pertinence réelle avant de les envoyer au LLM |
| 🧠 | **Mémoire conversationnelle** — l'assistant se souvient du contexte des échanges précédents |
| ⚡ | **Cache sémantique** — les questions similaires retournent une réponse instantanée, sans consommer de tokens |
| 💰 | **Budget maîtrisé** — limite journalière configurable ; les réponses cachées ne comptent pas |
| 🔄 | **Indexation incrémentale** — seuls les fichiers modifiés sont réindexés (manifeste MD5) |
| ☁️ | **100% persistant** — documents sur Cloudflare R2, index FAISS sur HuggingFace Hub |

---

## Comment ça fonctionne

### Vue d'ensemble (non-technique)

1. **Vous importez vos documents** via l'interface. Chaque fichier est découpé en passages (~900 caractères), vectorisé et indexé automatiquement.
2. **Vous posez une question** en langage naturel, en français ou en anglais.
3. **DocAssist retrouve les passages les plus pertinents** parmi tous vos documents, en combinant deux moteurs de recherche complémentaires.
4. **Claude formule une réponse** basée uniquement sur ces passages, avec les sources en bas de page.

### Pipeline technique

```
Votre question
      │
      ▼
┌───────────────────────┐
│   Cache sémantique    │──── HIT ──► réponse instantanée  (0 token LLM)
└──────────┬────────────┘
           │ MISS
           ▼
┌──────────────────────────────────────────────────────────┐
│  Enrichissement de la requête                            │
│  · Expansion d'acronymes  (PHP → "PHP Hypertext...")     │
│  · Détection d'articles juridiques  (L1234-5…)           │
│  · Réécriture contextuelle  (jusqu'à 3 reformulations)   │
└──────────┬───────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  Recherche hybride                                       │
│  ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │  FAISS           │   │  BM25 Okapi custom           │ │
│  │  (sémantique)    │   │  stemming Snowball + bigrams │ │
│  └────────┬─────────┘   └──────────────┬───────────────┘ │
│           └──────── RRF pondérée ───────┘                 │
│           poids dynamique selon le type de requête :      │
│           acronymes/termes exacts → BM25 prioritaire      │
│           questions conceptuelles  → FAISS prioritaire    │
└──────────┬───────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  Reranking  (BGE cross-encoder)                          │
│  classe les 20 candidats par pertinence réelle           │
└──────────┬───────────────────────────────────────────────┘
           │  Top 6 passages
           ▼
┌──────────────────────────────────────────────────────────┐
│  Claude Haiku                                            │
│  répond à partir des extraits uniquement                 │
└──────────┬───────────────────────────────────────────────┘
           ▼
    Réponse  +  sources (fichier · page · score)
```

### Architecture cloud

```
┌─────────────────────────────────────────────────────────────┐
│  HuggingFace Spaces  (Docker · CPU Basic · 16 GB RAM)       │
│                                                             │
│  FastAPI  ──►  /            (frontend HTML/CSS/JS)          │
│            ──►  /api        (REST API)                      │
│                                                             │
│  Au démarrage :                                             │
│    Cloudflare R2   ──►  restaure les documents localement   │
│    HuggingFace Hub ──►  restaure l'index FAISS              │
│                                                             │
│  À l'upload :                                               │
│    Fichier  ──►  R2  (persistance)                          │
│    FAISS + BM25 reconstruits  ──►  HF Hub (persistance)     │
└─────────────────────────────────────────────────────────────┘
```

> FastAPI sert à la fois le frontend et l'API REST sur le **même domaine** (`/` et `/api`), ce qui élimine tout problème de CORS quelle que soit la plateforme.

---

## Stack technique

### Intelligence artificielle

| Composant | Choix | Justification |
|---|---|---|
| **LLM** | Claude Haiku (Anthropic) | Excellente compréhension du français, suivi d'instructions rigoureux, coût ~$0.006/question |
| **Embeddings** | `BAAI/bge-small-en-v1.5` (fastembed/ONNX) | ~37 MB, inférence CPU optimisée, pas de PyTorch ni de GPU |
| **Recherche sémantique** | FAISS (cosine similarity) | Standard industriel, recherche vectorielle en µs, filtrage par workspace |
| **Recherche lexicale** | BM25 Okapi custom | Stemming Snowball FR/EN + bigrammes — complémente FAISS sur les termes exacts et les acronymes |
| **Fusion** | RRF pondérée dynamiquement | Le poids BM25/FAISS s'adapte au type de requête détecté |
| **Reranking** | BGE-reranker-base (HF Inference) | Cross-encoder : re-classe les candidats par pertinence réelle |
| **Orchestration** | LangChain | Chaînage LLM + retrieval |

### Infrastructure

| Composant | Choix | Justification |
|---|---|---|
| **Backend** | FastAPI + Pydantic v2 | API REST moderne, Swagger auto-généré, async natif |
| **Parsing** | PyMuPDF + python-docx | PDF (XHTML pour les accents) + Word natif |
| **Cache** | JSON sémantique (cosine + lexical) | 0 token LLM pour les questions similaires, TTL 7 jours |
| **Stockage fichiers** | Cloudflare R2 | S3-compatible, gratuit jusqu'à 10 Go |
| **Persistance index** | HuggingFace Hub (Dataset) | Survie aux redémarrages — pull au boot, push après indexation |
| **Frontend** | HTML5 / CSS3 / JS vanilla | Zéro dépendance, bilingue FR/EN |
| **Tests** | pytest (100% hors-ligne) | LLM et FAISS mockés, aucune clé API requise |
| **CI/CD** | GitHub Actions | Tests sur Python 3.11 et 3.12 à chaque push |
| **Déploiement** | HuggingFace Spaces (Docker) | 16 GB RAM gratuit, build automatique depuis Git |

---

## Structure du projet

```
chatbot-rag/
│
├── src/                       ← Pipeline IA
│   ├── loader.py              ← Extraction + chunking (PDF/DOCX/TXT/MD · max 500 pages)
│   ├── embedder.py            ← fastembed/ONNX · batch=64 · threads auto
│   ├── indexer.py             ← Construction FAISS + BM25 jumelés · manifeste MD5
│   ├── bm25_store.py          ← BM25 Okapi custom (Snowball · bigrammes · K1=1.8)
│   ├── retriever.py           ← Recherche hybride · RRF dynamique · boost BM25 acronymes
│   ├── reranker.py            ← Cross-encoder BGE via HuggingFace Inference API
│   ├── chain.py               ← question → passages → réponse Claude
│   ├── cache.py               ← Cache sémantique (cosine + lexical · TTL 7j)
│   ├── memory.py              ← Historique conversationnel (4 échanges)
│   ├── rate_limiter.py        ← Compteur journalier de requêtes LLM
│   ├── query_processor.py     ← Enrichissement : acronymes · articles · réécriture
│   ├── hf_store.py            ← Push/pull index FAISS ↔ HuggingFace Hub
│   ├── storage.py             ← Upload/download fichiers ↔ Cloudflare R2
│   └── utils.py               ← Helpers partagés
│
├── api/                       ← API REST
│   ├── main.py                ← Lifespan (restauration R2 + HF Hub au boot)
│   ├── schemas.py             ← Modèles Pydantic
│   └── routes/
│       ├── chat.py            ← POST /api/chat
│       ├── documents.py       ← Workspaces · upload · reindex · suppression
│       └── health.py          ← GET /api/health
│
├── frontend/                  ← Interface web (vanilla, bilingue FR/EN)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── config.js          ← API_BASE = '/api'
│       ├── api.js · chat.js · app.js · i18n.js
│
├── tests/                     ← Tests unitaires hors-ligne
│   ├── conftest.py · test_loader.py · test_retriever.py · test_chain.py
│
├── data/                      ← Généré à l'exécution (non versionné)
│   ├── faiss_index/           ← Persisté sur HuggingFace Hub
│   └── workspaces.json        ← Persisté sur Cloudflare R2
│
├── docs/                      ← Vos documents (non versionnés)
│   └── <workspace>/
│
├── config.py                  ← Tous les paramètres centralisés
├── Dockerfile                 ← Multi-stage · port 7860 · fastembed pré-téléchargé
├── .env.example               ← Template de configuration
├── requirements.txt           ← Dev
└── requirements-prod.txt      ← Production (image Docker allégée)
```

---

## Démarrage rapide

### En local

**Prérequis :** Python 3.11+ · [Clé API Anthropic](https://console.anthropic.com)

```bash
# Cloner et installer
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG
python -m venv .venv && source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt

# Configurer
cp .env.example .env
# Éditer .env : renseigner ANTHROPIC_API_KEY (obligatoire)
#               renseigner HF_TOKEN pour activer le reranker (recommandé)

# Lancer
uvicorn api.main:app --port 7860 --reload
# → http://localhost:7860
```

Sans `R2_*` ni `HF_REPO_ID`, tout fonctionne en **mode local pur** : les documents restent dans `docs/<workspace>/` et l'index dans `data/faiss_index/`.

> **Windows** : ajoutez `HF_HUB_DISABLE_SYMLINKS_WARNING=1` dans `.env` pour supprimer l'avertissement HuggingFace sur les symlinks.

### Sur HuggingFace Spaces

<details>
<summary><strong>Guide de déploiement complet</strong></summary>

**1. Créer le Space**

Sur [huggingface.co/new-space](https://huggingface.co/new-space) :
- SDK → **Docker** · Template → **Blank** · Hardware → **CPU Basic (free)**

**2. Créer le dépôt pour l'index FAISS**

Sur [huggingface.co/new](https://huggingface.co/new) :
- Type → **Dataset** · Nom → `chatbot-rag-index` · Visibility → **Private**

**3. Pousser le code**

```bash
git remote add hf https://huggingface.co/spaces/VOTRE_USERNAME/chatbot-rag

# Créer une branche sans historique (évite les fichiers binaires anciens > 10 MB)
git checkout --orphan hf-deploy
git add -A
git commit -m "deploy"
git push hf hf-deploy:main --force
git checkout main && git branch -D hf-deploy
```

**4. Configurer les secrets** (Space Settings → Variables and secrets)

| Variable | Type | Valeur |
|---|---|---|
| `ANTHROPIC_API_KEY` | 🔒 Secret | Votre clé Anthropic |
| `HF_TOKEN` | 🔒 Secret | Token HuggingFace (write) |
| `HF_REPO_ID` | Variable | `username/chatbot-rag-index` |
| `R2_ACCOUNT_ID` | 🔒 Secret | Compte Cloudflare R2 |
| `R2_ACCESS_KEY_ID` | 🔒 Secret | Clé d'accès R2 |
| `R2_SECRET_ACCESS_KEY` | 🔒 Secret | Clé secrète R2 |
| `R2_BUCKET_NAME` | Variable | Nom du bucket |
| `ANTHROPIC_MODEL` | Variable | `claude-haiku-4-5-20251001` |
| `DAILY_REQUEST_LIMIT` | Variable | `20` (0 = illimité) |
| `RERANKER_ENABLED` | Variable | `true` |

Le build Docker démarre automatiquement après la configuration (~5–10 min la première fois).

</details>

---

## Configuration avancée

Paramètres disponibles dans [`config.py`](config.py) et via variables d'environnement :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Modèle LLM utilisé |
| `DAILY_REQUEST_LIMIT` | `10` | Requêtes LLM max/jour (0 = illimité) |
| `CHUNK_SIZE` | `900` | Taille des passages en caractères |
| `CHUNK_OVERLAP` | `220` | Chevauchement entre passages consécutifs |
| `MAX_PDF_PAGES` | `500` | Limite de pages par PDF (troncature avec notification) |
| `TOP_K_RESULTS` | `6` | Passages transmis au LLM |
| `TOP_K_RETRIEVAL` | `20` | Pool initial par moteur de recherche (avant fusion) |
| `HYBRID_BM25_WEIGHT` | `0.45` | Poids BM25 dans la fusion hybride |
| `RERANKER_ENABLED` | `false` | Active le reranking BGE cross-encoder |
| `MEMORY_MAX_EXCHANGES` | `4` | Échanges gardés en mémoire de session |
| `RESPONSE_CACHE_TTL_SECONDS` | `604800` | Durée du cache de réponses (7 jours) |

**Changer de modèle Claude :**
```bash
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # rapide · ~$0.006/question
ANTHROPIC_MODEL=claude-sonnet-4-5           # plus précis · ~$0.05/question
```

> ⚠️ Si vous modifiez `EMBEDDING_MODEL`, supprimez `data/faiss_index/` avant de relancer l'indexation — les vecteurs sont incompatibles entre modèles.

---

## Tests

```bash
pytest                                        # suite complète
pytest --cov=src --cov-report=term-missing    # avec couverture de code
```

Les tests tournent **entièrement hors-ligne** — LLM et FAISS sont mockés, aucune clé API requise.

---

<div align="center">

Projet personnel · FastAPI · LangChain · Claude Haiku · FAISS · BM25 · fastembed/ONNX · BGE-reranker · HuggingFace Spaces · Cloudflare R2

</div>
