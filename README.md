---
title: DocAssist
emoji: 📚
colorFrom: teal
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Assistant documentaire RAG — posez vos questions sur vos PDF
---

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
[![Déployé sur Render](https://img.shields.io/badge/Déployé-Render-46E3B7?logo=render&logoColor=white&style=flat-square)](https://chatbot-rag-xodz.onrender.com)

<br>

### [🚀 Démo en ligne](https://chatbot-rag-xodz.onrender.com) &nbsp;·&nbsp; [📖 Documentation API](https://chatbot-rag-xodz.onrender.com/docs)

</div>

---

## Le problème

Dans une organisation, l'information est éparpillée dans des dizaines de fichiers : contrats, guides techniques, règlements, fiches de poste, conventions. Retrouver une réponse précise prend du temps — et souvent on ne sait même pas dans quel fichier chercher.

**DocAssist résout ça en quelques secondes :** l'assistant a mémorisé vos documents et cite ses sources à chaque réponse.

> L'IA refuse d'inventer : si l'information n'est pas dans vos documents, elle le dit explicitement.

---

## Comment ça fonctionne

### En langage simple

**1. Préparation (une seule fois par document)** — Chaque fichier est découpé en passages (~900 caractères). Chaque passage est transformé en vecteur de 768 dimensions par `multilingual-e5-base` (avec le préfixe `passage:` requis par ce modèle) et stocké dans FAISS. En parallèle, un index BM25 est construit avec stemming Snowball et bigrammes pour la recherche lexicale.

**2. À chaque question** — La question est enrichie (expansion d'acronymes, détection d'articles juridiques, réécriture contextuelle), puis les deux index sont interrogés en parallèle avec décroissance de poids selon les reformulations. Les résultats sont fusionnés par RRF pondéré dynamiquement (BM25 favorisé sur les noms propres, FAISS sur les questions conceptuelles), reranqués par un cross-encoder, et les 6 meilleurs passages sont transmis à Claude qui formule la réponse.

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
│  FAISS e5-base (sémantique, préfixe "query:")            │
│  + BM25 Okapi (lexical, stemming Snowball + bigrammes)   │
│  poids dynamique : BM25↑ noms propres · FAISS↑ concepts  │
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

---

## Fonctionnalités

| | Ce que fait l'application |
|---|---|
| 🎯 | **Réponses sourcées** — chaque réponse indique le fichier, la page et un extrait du passage utilisé |
| 📂 | **Multi-formats** — lit les PDF, Word (.docx) et texte brut (.txt) |
| 🗂️ | **Workspaces libres** — organisez vos documents par thème, projet ou équipe |
| 🔍 | **Recherche hybride** — sémantique (FAISS) + lexicale (BM25) + reranking cross-encoder |
| 🧠 | **Mémoire conversationnelle** — l'assistant se souvient des derniers échanges |
| ⚡ | **Cache sémantique** — les questions similaires retournent la réponse sans appel LLM |
| 💰 | **Économie de crédits** — limite journalière configurable (`DAILY_REQUEST_LIMIT`) |
| 🔄 | **Indexation intelligente** — seuls les fichiers modifiés sont réindexés (manifeste MD5) |
| ☁️ | **Stockage cloud** — documents sur Cloudflare R2, index FAISS sur HuggingFace Hub |

---

## Stack technique

| Rôle | Outil | Pourquoi |
|---|---|---|
| **Modèle de langage** | Anthropic Claude Haiku | Meilleur suivi d'instructions, excellent en français, ~$0.006/question |
| **Vectorisation** | `intfloat/multilingual-e5-base` (local CPU) | Dédié retrieval (≠ paraphrase), 768 dim, préfixes `query:`/`passage:`, FR/EN · ~1.1 Go téléchargé une fois |
| **Recherche sémantique** | FAISS + embeddings normalisés | Standard industriel, cosine similarity en µs, filtrage workspace |
| **Recherche lexicale** | BM25 Okapi custom | Stemming Snowball FR/EN + bigrammes + K1=1.8, complémente FAISS sur les termes exacts |
| **Fusion des résultats** | RRF pondérée dynamiquement | Poids BM25/FAISS ajusté au type de requête · décroissance par reformulation |
| **Reranking** | BGE-reranker-base (HuggingFace) | Cross-encoder pour classer les candidats par pertinence réelle |
| **Cache** | Cache sémantique JSON | Questions similaires → réponse directe, 0 token LLM consommé |
| **Orchestration IA** | LangChain | Framework RAG de référence |
| **Backend** | FastAPI + Pydantic v2 | API moderne, docs Swagger auto-générées |
| **Parsing documents** | PyMuPDF + python-docx | PDF fidèle (XHTML) + Word natif |
| **Stockage fichiers** | Cloudflare R2 | S3-compatible, gratuit jusqu'à 10 Go |
| **Persistance index** | HuggingFace Hub | Sauvegarde/restauration automatique entre redémarrages |
| **Frontend** | HTML5 / CSS3 / JS vanilla | Zéro dépendance, livrable immédiatement |
| **Tests** | pytest | LLM et FAISS mockés, zéro appel réseau |
| **CI/CD** | GitHub Actions | Lint + tests sur Python 3.11 et 3.12 |
| **Déploiement** | Render | Free tier, déploiement depuis Git |

---

## Structure du projet

```
chatbot-rag/
│
├── src/                      ← Pipeline IA (cœur de l'application)
│   ├── loader.py             ← Lecture et découpage des documents (PDF, DOCX, TXT, MD)
│   ├── embedder.py           ← Vectorisation e5 avec préfixes query/passage + batch HF API
│   ├── indexer.py            ← Création et mise à jour de l'index FAISS + BM25 jumelés
│   ├── bm25_store.py         ← BM25 Okapi custom (stemming Snowball, bigrammes, K1=1.8)
│   ├── retriever.py          ← Recherche hybride FAISS+BM25 · RRF dynamique · reranking
│   ├── reranker.py           ← Cross-encoder BGE via HuggingFace InferenceClient
│   ├── chain.py              ← Orchestration : question → passages → réponse Claude
│   ├── cache.py              ← Cache sémantique des réponses (économie de crédits)
│   ├── memory.py             ← Historique conversationnel compressé
│   ├── rate_limiter.py       ← Limite journalière de requêtes LLM
│   ├── query_processor.py    ← Enrichissement des requêtes (acronymes, articles, réécriture)
│   ├── storage.py            ← Stockage Cloudflare R2 + HuggingFace Hub
│   └── utils.py              ← Helpers partagés (logging, formatage contexte)
│
├── api/                      ← API REST (FastAPI)
│   ├── main.py               ← Point d'entrée, CORS, frontend statique
│   ├── schemas.py            ← Modèles de données (ChatRequest, ChatResponse…)
│   └── routes/
│       ├── chat.py           ← POST /api/chat · /api/chat/stream
│       ├── documents.py      ← GET/POST/DELETE /api/documents
│       └── health.py         ← GET /api/health
│
├── frontend/                 ← Interface web (HTML/CSS/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/                   ← api.js · chat.js · app.js · i18n.js
│
├── tests/                    ← Tests unitaires (pytest)
│   ├── conftest.py           ← Fixtures (PDF et TXT générés à la volée)
│   ├── test_loader.py
│   ├── test_retriever.py
│   └── test_chain.py
│
├── docs/                     ← Vos documents à indexer (organisés en workspaces)
│   └── <workspace>/          ← ex: docs/juridique/ · docs/technique/ · docs/rh/
│
├── data/                     ← Données générées (index, cache, metadata)
│   ├── faiss_index/          ← Index vectoriel FAISS + manifeste MD5
│   ├── bm25_index.pkl        ← Index BM25 sérialisé
│   ├── response_cache.json   ← Cache des réponses LLM
│   ├── daily_limits.json     ← Compteur journalier de requêtes
│   └── workspaces.json       ← Registre des workspaces
│
├── ingest.py                 ← CLI d'indexation des documents
├── config.py                 ← Paramètres centralisés (modèle, chunking, seuils…)
├── Dockerfile                ← Image Docker multi-stage
├── render.yaml               ← Configuration Render (Infrastructure as Code)
├── .env.example              ← Template de configuration (sans les secrets)
└── requirements.txt
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

# 5. Créer un workspace et indexer vos documents
#    Déposer vos fichiers dans docs/<nom-du-workspace>/
#    ex : docs/juridique/   docs/technique/   docs/rh/
python ingest.py
# ⚠️ Première exécution : télécharge le modèle d'embedding (~1.1 Go depuis HuggingFace).
#    Les exécutions suivantes utilisent le cache local — durée normale.

# 6. Démarrer
python api/main.py
# → Ouvrir http://localhost:8000
```

> **Windows uniquement :** le cache HuggingFace affiche un avertissement sur les symlinks.
> Pour le supprimer, ajouter `HF_HUB_DISABLE_SYMLINKS_WARNING=1` dans `.env`.
> Fonctionnellement, cela ne change rien.

</details>

---

## Configuration

Les paramètres clés sont dans [`.env`](.env.example) et [`config.py`](config.py) :

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Clé API Anthropic (obligatoire) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Modèle Claude utilisé |
| `DAILY_REQUEST_LIMIT` | `10` | Requêtes LLM max par jour (0 = illimité, cache hits ne comptent pas) |
| `TOP_K_RESULTS` | `6` | Chunks envoyés au LLM par requête |
| `MEMORY_MAX_EXCHANGES` | `4` | Échanges conservés en mémoire conversationnelle |
| `HF_TOKEN` | — | Token HuggingFace (reranker BGE + persistance index) |
| `RERANKER_ENABLED` | `true` | Active/désactive le reranking cross-encoder |
| `R2_ACCOUNT_ID` | — | Cloudflare R2 (stockage documents, optionnel) |
| `HF_REPO_ID` | — | Dépôt HuggingFace pour la persistance de l'index FAISS (optionnel) |
| `HF_HUB_DISABLE_SYMLINKS_WARNING` | `1` | Supprime l'avertissement symlinks sur Windows |

**Changer de modèle** (dans `.env`) :
```
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # rapide, économique (~$0.006/question)
ANTHROPIC_MODEL=claude-sonnet-4-6           # meilleure qualité (~$0.05/question)
```

> **Note importante après changement de modèle d'embedding :** si tu modifies `EMBEDDING_MODEL` dans `config.py`, supprime `data/faiss_index/` et `data/bm25_index.pkl`, puis relance `python ingest.py`. Les vecteurs en cache sont incompatibles entre modèles.

---

## Tests

```bash
pytest                                       # suite complète
pytest --cov=src --cov-report=term-missing   # avec couverture de code
```

> Les tests tournent **entièrement hors-ligne** : le LLM et FAISS sont simulés. Aucune clé API requise.

---

<div align="center">
  <sub>Projet personnel — FastAPI · LangChain · Claude Haiku · FAISS · BM25 · multilingual-e5-base · BGE-reranker · Render</sub>
</div>
