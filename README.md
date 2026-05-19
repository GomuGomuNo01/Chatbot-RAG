<div align="center">

# DocAssist — Assistant IA sur documents internes

**Posez une question. Obtenez une réponse claire, avec le fichier et la page exacte où l'information a été trouvée.**

<br>

[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/IA-LangChain-1C3C3C?logo=langchain&logoColor=white&style=flat-square)](https://langchain.com)
[![Claude Haiku](https://img.shields.io/badge/LLM-Claude%20Haiku-CC785C?logo=anthropic&logoColor=white&style=flat-square)](https://console.anthropic.com)
[![FAISS](https://img.shields.io/badge/Recherche-FAISS%20%2B%20BM25-0078D4?logo=meta&logoColor=white&style=flat-square)](https://github.com/facebookresearch/faiss)
[![CI](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml)
[![HF Spaces](https://img.shields.io/badge/Déployé-HuggingFace%20Spaces-FFD21E?logo=huggingface&logoColor=black&style=flat-square)](https://huggingface.co/spaces/GomuGomuNo01/chatbot-rag)

<br>

### [🚀 Démo en ligne](https://huggingface.co/spaces/GomuGomuNo01/chatbot-rag) &nbsp;·&nbsp; [📖 Documentation API](https://gomugomuNo01-chatbot-rag.hf.space/docs)

</div>

---

## Le problème

Dans une organisation, l'information est éparpillée dans des dizaines de fichiers : contrats, guides techniques, règlements, fiches de poste, conventions. Retrouver une réponse précise prend du temps — et souvent on ne sait même pas dans quel fichier chercher.

**DocAssist résout ça en quelques secondes :** l'assistant a mémorisé vos documents et cite ses sources à chaque réponse.

> L'IA refuse d'inventer : si l'information n'est pas dans vos documents, elle le dit explicitement.

---

## Fonctionnalités

| | Ce que fait l'application |
|---|---|
| 🎯 | **Réponses sourcées** — chaque réponse indique le fichier, la page et un extrait du passage utilisé |
| 📂 | **Multi-formats** — lit les PDF, Word (.docx) et texte brut (.txt) |
| 🗂️ | **Workspaces libres** — organisez vos documents par thème, projet ou équipe, sans schéma imposé |
| 🔍 | **Recherche hybride** — sémantique (FAISS) + lexicale (BM25) + reranking cross-encoder |
| 🧠 | **Mémoire conversationnelle** — l'assistant se souvient des derniers échanges de la session |
| ⚡ | **Cache sémantique** — les questions similaires retournent une réponse instantanée (0 token LLM) |
| 💰 | **Économie de crédits** — limite journalière configurable, les cache hits ne comptent pas |
| 🔄 | **Indexation intelligente** — seuls les fichiers modifiés sont réindexés (manifeste MD5) |
| ☁️ | **Stockage cloud** — documents sur Cloudflare R2, index FAISS sauvegardé sur HuggingFace Hub |

---

## Comment ça fonctionne

### En langage simple

**1. Préparation (une seule fois par document)**
Chaque fichier est découpé en passages d'environ 900 caractères. Chaque passage est transformé en vecteur numérique par un modèle d'embedding (`BAAI/bge-small-en-v1.5` via fastembed/ONNX) et stocké dans FAISS. En parallèle, un index BM25 est construit pour la recherche lexicale exacte.

**2. À chaque question**
La question est enrichie (expansion d'acronymes, détection d'articles juridiques, réécriture contextuelle), puis les deux index sont interrogés. Les résultats sont fusionnés par RRF pondéré dynamiquement selon le type de requête, reranqués par un cross-encoder, et les 6 meilleurs passages sont transmis à Claude qui formule la réponse finale.

### Pipeline complet

```
Votre question
      │
      ▼
┌─────────────────────┐
│  Cache sémantique   │──── HIT → réponse instantanée (0 token consommé)
└──────────┬──────────┘
           │ MISS
           ▼
┌─────────────────────────────────────────────────────────┐
│  Enrichissement de la requête                           │
│  expansion acronymes · détection articles · réécriture  │
│  → jusqu'à 3 reformulations avec décroissance de poids  │
└──────────┬──────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  Recherche hybride (par reformulation)                   │
│  FAISS bge-small (sémantique)                            │
│  + BM25 Okapi (lexical, stemming Snowball + bigrammes)   │
│  poids dynamique : BM25↑ acronymes/noms · FAISS↑ concepts│
│  → fusion RRF pondérée → reranking cross-encoder BGE     │
└──────────┬───────────────────────────────────────────────┘
           │ Top 6 passages
           ▼
┌─────────────────────┐
│  Claude Haiku       │  génère la réponse à partir des extraits uniquement
└──────────┬──────────┘
           ▼
    Réponse + sources (fichier · page · score)
```

### Architecture cloud

```
HuggingFace Spaces (Docker · CPU Basic · 16 GB RAM)
      │
      ├── Au démarrage
      │     ├── Cloudflare R2 ──────── restaure les documents (PDF, DOCX, TXT)
      │     └── HuggingFace Hub ────── restaure l'index FAISS + manifeste MD5
      │
      ├── À l'upload d'un document
      │     ├── Fichier → Cloudflare R2 (persistance)
      │     ├── Indexation FAISS + BM25 (mémoire, batch de 64)
      │     └── Index FAISS → HuggingFace Hub (survie aux redémarrages)
      │
      └── FastAPI sert le frontend ET l'API sur le même domaine (/api)
```

---

## Stack technique

| Rôle | Outil | Pourquoi |
|---|---|---|
| **Modèle de langage** | Anthropic Claude Haiku | Excellent suivi d'instructions, très bon en français, ~$0.006/question |
| **Vectorisation** | `BAAI/bge-small-en-v1.5` via fastembed/ONNX | ~130 MB en mémoire, inférence ONNX optimisée CPU, pas de GPU requis |
| **Recherche sémantique** | FAISS + embeddings normalisés | Standard industriel, cosine similarity en µs, filtrage par workspace |
| **Recherche lexicale** | BM25 Okapi custom | Stemming Snowball FR/EN + bigrammes, complémente FAISS sur les termes exacts et acronymes |
| **Fusion des résultats** | RRF pondérée dynamiquement | Poids BM25/FAISS ajusté au type de requête (acronyme → BM25, conceptuel → FAISS) |
| **Reranking** | BGE-reranker-base (HuggingFace Inference) | Cross-encoder pour classer les candidats par pertinence réelle |
| **Cache** | Cache sémantique JSON | Questions similaires → réponse directe, 0 token LLM consommé |
| **Orchestration IA** | LangChain | Framework RAG de référence |
| **Backend** | FastAPI + Pydantic v2 | API moderne, docs Swagger auto-générées, sert aussi le frontend statique |
| **Parsing documents** | PyMuPDF + python-docx | PDF fidèle + Word natif, troncature automatique à 150 pages pour les très gros fichiers |
| **Stockage fichiers** | Cloudflare R2 | S3-compatible, gratuit jusqu'à 10 Go, restauration automatique au démarrage |
| **Persistance index** | HuggingFace Hub (Dataset) | Sauvegarde/restauration de l'index FAISS entre les redémarrages du Space |
| **Frontend** | HTML5 / CSS3 / JS vanilla | Zéro dépendance, interface bilingue FR/EN |
| **Tests** | pytest | LLM et FAISS mockés, zéro appel réseau |
| **CI/CD** | GitHub Actions | Lint + tests sur Python 3.11 et 3.12 |
| **Déploiement** | HuggingFace Spaces (Docker) | 16 GB RAM gratuit, build Docker automatique, URL publique |

---

## Structure du projet

```
chatbot-rag/
│
├── src/                      ← Pipeline IA (cœur de l'application)
│   ├── loader.py             ← Lecture et découpage des documents (PDF, DOCX, TXT)
│   │                            MAX_PDF_PAGES = 150 (troncature avec notification)
│   ├── embedder.py           ← Vectorisation fastembed/ONNX (batch=16, threads=1)
│   ├── indexer.py            ← Construction FAISS par batches de 64 + gc.collect()
│   ├── bm25_store.py         ← BM25 Okapi custom (stemming Snowball, bigrammes, K1=1.8)
│   ├── retriever.py          ← Recherche hybride FAISS+BM25 · RRF dynamique · reranking
│   │                            Boost BM25 (0.65) pour les acronymes (PHP, SQL, API...)
│   ├── reranker.py           ← Cross-encoder BGE via HuggingFace InferenceClient
│   ├── chain.py              ← Orchestration : question → passages → réponse Claude
│   ├── cache.py              ← Cache sémantique des réponses
│   ├── memory.py             ← Historique conversationnel compressé (4 échanges)
│   ├── rate_limiter.py       ← Limite journalière de requêtes LLM
│   ├── query_processor.py    ← Enrichissement des requêtes (acronymes, articles, réécriture)
│   ├── storage.py            ← Cloudflare R2 (documents) + HuggingFace Hub (index FAISS)
│   └── utils.py              ← Helpers partagés
│
├── api/                      ← API REST (FastAPI)
│   ├── main.py               ← Point d'entrée, frontend statique, restauration au démarrage
│   ├── schemas.py            ← Modèles de données (ChatRequest, ChatResponse…)
│   └── routes/
│       ├── chat.py           ← POST /api/chat
│       ├── documents.py      ← GET/POST/DELETE /api/documents · POST /api/reindex
│       └── health.py         ← GET /api/health
│
├── frontend/                 ← Interface web (HTML/CSS/JS vanilla)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── config.js         ← API_BASE = '/api' (même origine partout)
│       ├── api.js            ← Appels REST vers le backend
│       ├── chat.js           ← Rendu des messages et des sources
│       ├── app.js            ← Logique principale (workspaces, upload, indexation)
│       └── i18n.js           ← Traductions FR / EN
│
├── tests/                    ← Tests unitaires (pytest, 100% hors-ligne)
│   ├── conftest.py
│   ├── test_loader.py
│   ├── test_retriever.py
│   └── test_chain.py
│
├── data/                     ← Données générées localement (non versionnées)
│   ├── faiss_index/          ← Index vectoriel FAISS (persisté sur HF Hub)
│   └── workspaces.json       ← Registre des workspaces (persisté sur R2)
│
├── docs/                     ← Documents à indexer, organisés par workspace
│   └── <workspace>/          ← ex : docs/technique/   docs/rh/
│
├── config.py                 ← Paramètres centralisés (modèle, chunking, seuils…)
├── Dockerfile                ← Image Docker multi-stage, port 7860, fastembed pré-téléchargé
├── .env.example              ← Template de configuration
├── requirements.txt          ← Dépendances complètes (dev + prod)
└── requirements-prod.txt     ← Dépendances allégées pour le build Docker
```

---

## Lancer le projet en local

<details>
<summary><strong>Instructions d'installation</strong></summary>

**Prérequis :** Python 3.11+ · [Clé API Anthropic](https://console.anthropic.com)

```bash
# 1. Récupérer le code
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG

# 2. Environnement Python
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
# → Renseigner ANTHROPIC_API_KEY dans .env (obligatoire)
# → Renseigner HF_TOKEN pour le reranker BGE (optionnel mais recommandé)

# 5. Démarrer
uvicorn api.main:app --host 0.0.0.0 --port 7860 --reload
# → Ouvrir http://localhost:7860
```

En local, les documents sont stockés dans `docs/<workspace>/` et l'index FAISS dans `data/faiss_index/`.
Si `R2_*` et `HF_REPO_ID` ne sont pas configurés, tout fonctionne en mode local pur.

> **Windows uniquement :** le cache HuggingFace peut afficher un avertissement sur les symlinks.
> Ajoutez `HF_HUB_DISABLE_SYMLINKS_WARNING=1` dans `.env` pour le supprimer.

</details>

---

## Déploiement sur HuggingFace Spaces

Le projet est déployé via Docker sur HuggingFace Spaces (CPU Basic, 16 GB RAM, gratuit).

**Secrets à configurer dans Space Settings → Variables and secrets :**

| Variable | Type | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | Secret | Clé API Anthropic (obligatoire) |
| `HF_TOKEN` | Secret | Token HuggingFace write (reranker + persistance index) |
| `HF_REPO_ID` | Variable | `username/chatbot-rag-index` — dépôt Dataset pour l'index FAISS |
| `R2_ACCOUNT_ID` | Secret | Cloudflare R2 (stockage documents) |
| `R2_ACCESS_KEY_ID` | Secret | — |
| `R2_SECRET_ACCESS_KEY` | Secret | — |
| `R2_BUCKET_NAME` | Variable | Nom du bucket R2 |
| `ANTHROPIC_MODEL` | Variable | Modèle Claude (défaut : `claude-haiku-4-5-20251001`) |
| `DAILY_REQUEST_LIMIT` | Variable | Requêtes LLM max/jour (0 = illimité) |
| `RERANKER_ENABLED` | Variable | `true` pour activer le reranking BGE |

**Pour pousser une mise à jour :**
```bash
git remote add hf https://huggingface.co/spaces/GomuGomuNo01/chatbot-rag
git push hf main
```

---

## Configuration

Les paramètres fins sont dans [`config.py`](config.py) :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `CHUNK_SIZE` | `900` | Taille des passages en caractères |
| `CHUNK_OVERLAP` | `220` | Chevauchement entre passages |
| `MAX_PDF_PAGES` | `150` | Limite de pages par PDF (troncature avec notification) |
| `TOP_K_RESULTS` | `6` | Passages envoyés au LLM par requête |
| `TOP_K_RETRIEVAL` | `20` | Pool initial par index (avant RRF) |
| `HYBRID_BM25_WEIGHT` | `0.45` | Poids BM25 dans la fusion (0 = full vectoriel, 1 = full BM25) |
| `MEMORY_MAX_EXCHANGES` | `4` | Échanges conservés en mémoire conversationnelle |
| `RESPONSE_CACHE_TTL_SECONDS` | `604800` | Durée de vie du cache (7 jours) |

**Changer de modèle Claude** (dans `.env` ou les secrets HF) :
```
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # rapide, économique (~$0.006/question)
ANTHROPIC_MODEL=claude-sonnet-4-5           # meilleure qualité (~$0.05/question)
```

> **Note :** si vous modifiez `EMBEDDING_MODEL` dans `config.py`, supprimez `data/faiss_index/` et relancez l'indexation. Les vecteurs sont incompatibles entre modèles.

---

## Tests

```bash
pytest                                       # suite complète
pytest --cov=src --cov-report=term-missing   # avec couverture de code
```

> Les tests tournent **entièrement hors-ligne** : le LLM et FAISS sont simulés. Aucune clé API requise.

---

<div align="center">
  <sub>Projet personnel — FastAPI · LangChain · Claude Haiku · FAISS · BM25 · fastembed · BGE-reranker · HuggingFace Spaces</sub>
</div>
