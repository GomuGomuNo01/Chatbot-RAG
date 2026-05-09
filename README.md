<div align="center">

# DocAssist — Assistant IA sur documents internes

**Posez une question. Obtenez une réponse claire, avec la page exacte où l'information a été trouvée.**

<br>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/IA-LangChain-1C3C3C?logo=langchain&logoColor=white&style=flat-square)](https://langchain.com)
[![Groq · Llama 3.3 70B](https://img.shields.io/badge/LLM-Llama%203.3%2070B-F55036?logo=meta&logoColor=white&style=flat-square)](https://console.groq.com)
[![FAISS](https://img.shields.io/badge/Recherche-FAISS-0078D4?logo=meta&logoColor=white&style=flat-square)](https://github.com/facebookresearch/faiss)
[![46 tests](https://img.shields.io/badge/Tests-46%20✓-22c55e?logo=pytest&logoColor=white&style=flat-square)](tests/)
[![CI](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml)
[![Déployé sur Render](https://img.shields.io/badge/Déployé-Render-46E3B7?logo=render&logoColor=white&style=flat-square)](https://chatbot-rag-xodz.onrender.com)

<br>

### [🚀 Démo en ligne](https://chatbot-rag-xodz.onrender.com) &nbsp;·&nbsp; [📖 Documentation API](https://chatbot-rag-xodz.onrender.com/docs) &nbsp;·&nbsp; [🌐 Frontend](https://gomugomuNo01.github.io/Chatbot-RAG/)

</div>

---

## Le problème

Dans une entreprise, l'information est éparpillée dans des dizaines de fichiers : contrats, guides techniques, règlements intérieurs, CGU. Retrouver une réponse précise prend du temps — et souvent on ne sait même pas dans quel fichier chercher.

**DocAssist résout ça en quelques secondes :** l'assistant a mémorisé l'intégralité de vos documents et cite ses sources à chaque réponse.

> ⚠️ L'IA refuse d'inventer : si l'information n'est pas dans vos documents, elle le dit explicitement.

---

## Démonstration

| Vous demandez | DocAssist répond |
|---|---|
| *"Quels sont mes droits en cas de licenciement ?"* | Réponse détaillée + **Code du travail, page 47** |
| *"Comment configurer une connexion Spring Boot ?"* | Procédure étape par étape + **Guide technique, page 12** |
| *"Quelle est la durée de la période d'essai pour un CDI ?"* | Durée exacte + **Règlement intérieur, page 3** |

Les sources s'affichent dans l'interface avec le nom du fichier, le numéro de page et un extrait du passage utilisé.

---

## Comment ça fonctionne

### En langage simple

L'application fonctionne en deux temps :

**1. Préparation (une seule fois)** — Chaque document est découpé en petits passages (~1 000 caractères), puis chaque passage est transformé en une "empreinte numérique" qui capture son sens. Toutes ces empreintes sont stockées dans une base de recherche ultra-rapide.

**2. À chaque question** — La question est elle aussi transformée en empreinte, puis comparée à toutes celles des documents. Les passages les plus proches sémantiquement sont sélectionnés et transmis au modèle d'IA, qui formule une réponse claire en s'appuyant uniquement sur eux.

Cette technique s'appelle le **RAG** *(Retrieval-Augmented Generation)* — elle est utilisée par les assistants IA d'entreprise (Copilot, Gemini for Workspace, etc.).

### Schéma

```
Votre question
      │
      ▼
┌─────────────────┐     ┌──────────────────────────┐
│  Transformation │     │  Base de 15 917 passages  │
│  en empreinte   │────▶│  indexés (FAISS)          │
│  numérique      │     │  ← vos documents PDF/Word │
└─────────────────┘     └──────────┬───────────────┘
                                   │ Top 10 passages pertinents
                                   ▼
                        ┌──────────────────────────┐
                        │  Llama 3.3 70B (via Groq) │
                        │  génère la réponse        │
                        └──────────┬───────────────┘
                                   │
                                   ▼
                     Réponse + sources (fichier + page)
```

---

## Fonctionnalités

| | Ce que fait l'application |
|---|---|
| 🎯 | **Réponses sourcées** — chaque réponse indique le fichier et la page utilisés |
| 📂 | **Multi-formats** — lit les PDF, fichiers Word (.docx) et texte brut (.txt) |
| 🏷️ | **Catégories** — recherche filtrée par domaine : Technique / RH / Juridique |
| 🧠 | **Mémoire** — l'assistant se souvient des 7 derniers échanges de la conversation |
| ⚡ | **Indexation intelligente** — l'ajout d'un fichier ne recalcule que ce fichier |
| 💸 | **Coût zéro** — LLM via Groq (free tier), embeddings calculés localement |
| 📊 | **15 917 passages** indexés dans la démo (Code civil + Code du travail + guides) |

---

## Compétences démontrées

Ce projet couvre l'ensemble du cycle d'une application IA : du traitement des données jusqu'au déploiement automatisé.

### Intelligence artificielle

- Architecture **RAG** complète : ingestion → vectorisation → recherche → génération
- **Prompt engineering** : instructions système, gestion du cas "je ne sais pas", réponses structurées
- Recherche sémantique avec **FAISS** : seuil de pertinence, déduplication, score de confiance
- Mémoire conversationnelle glissante injectée dans le contexte du LLM

### Backend & API

- **API REST** FastAPI avec validation Pydantic v2, gestion d'erreurs, CORS
- Architecture en couches découplées : `loader → embedder → indexer → retriever → chain`
- Parsing multi-formats : **PDF** (PyMuPDF), **Word** (python-docx), **texte brut**
- Indexation incrémentale via manifeste MD5 — seuls les fichiers modifiés sont retraités

### Qualité & tests

- **46 tests unitaires** avec pytest — zéro appel réseau (LLM et FAISS simulés)
- Fixtures dynamiques : les fichiers de test (PDF, TXT) sont générés à la volée
- Couverture des cas limites : fichier vide, format non supporté, réponse vide du LLM

### DevOps & déploiement

- **CI/CD GitHub Actions** : lint (Ruff), tests Python 3.11 et 3.12 à chaque push
- Déploiement automatique sur **Render** via `render.yaml` (Infrastructure as Code)
- **Dockerfile** multi-stage : image de production allégée (sans PyTorch)
- Persistance de l'index FAISS via **HuggingFace Hub** entre les redémarrages Render

### Frontend

- Interface de chat en **HTML/CSS/JS vanilla** — sans framework, aucune dépendance externe
- Bulles de messages, indicateur de frappe, scroll automatique, design responsive
- Affichage des sources avec score de pertinence et extrait dépliable

---

## Stack technique

| Rôle | Outil | Pourquoi |
|---|---|---|
| **Modèle de langage** | Groq + Llama 3.3 70B | Gratuit, 300 tokens/s, performant en français |
| **Vectorisation** | sentence-transformers MiniLM-L12 | Local, gratuit, multilingue FR/EN, 120 Mo |
| **Base vectorielle** | FAISS (Meta AI) | Standard industriel, recherche en mémoire en µs |
| **Orchestration IA** | LangChain 1.2 | Framework RAG de référence |
| **Backend** | FastAPI + Pydantic v2 | API moderne, docs Swagger auto-générées |
| **Parsing PDF** | PyMuPDF | Extraction fidèle texte + numéros de page |
| **Frontend** | HTML5 / CSS3 / JS vanilla | Zéro dépendance, livrable immédiatement |
| **Tests** | pytest | LLM et FAISS mockés, zéro appel réseau |
| **CI/CD** | GitHub Actions | Lint + tests sur Python 3.11 et 3.12 |
| **Déploiement backend** | Render | Free tier, déploiement depuis Git |
| **Déploiement frontend** | GitHub Pages | Auto-déployé à chaque push |
| **Persistance index** | HuggingFace Hub | Sauvegarde/restauration automatique entre redémarrages |

---

## Structure du projet

```
Chatbot-RAG/
│
├── src/                  ← Pipeline IA (cœur de l'application)
│   ├── loader.py         ← Lecture et découpage des documents en passages
│   ├── embedder.py       ← Transformation du texte en vecteurs numériques
│   ├── indexer.py        ← Création et mise à jour de la base vectorielle FAISS
│   ├── retriever.py      ← Recherche des passages les plus pertinents
│   ├── chain.py          ← Orchestration : question → passages → réponse LLM
│   ├── memory.py         ← Historique conversationnel (7 derniers échanges)
│   └── query_processor.py← Expansion des acronymes, détection de références légales
│
├── api/                  ← API REST (FastAPI)
│   ├── main.py           ← Point d'entrée, CORS, frontend statique
│   ├── schemas.py        ← Modèles de données (ChatRequest, ChatResponse...)
│   └── routes/           ← /api/chat · /api/documents · /api/health
│
├── frontend/             ← Interface web (HTML/CSS/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/               ← api.js · chat.js · app.js · config.js
│
├── tests/                ← 46 tests unitaires (pytest)
│   ├── conftest.py       ← Fixtures dynamiques (PDF et TXT générés à la volée)
│   ├── test_loader.py
│   ├── test_retriever.py
│   └── test_chain.py
│
├── docs/                 ← Vos documents à indexer (PDF, DOCX, TXT)
│   ├── technique/
│   ├── rh/
│   └── juridique/
│
├── ingest.py             ← CLI d'indexation des documents
├── config.py             ← Paramètres centralisés (modèle, chunk size, seuils...)
├── Dockerfile            ← Image Docker multi-stage pour la production
├── render.yaml           ← Configuration Render (Infrastructure as Code)
└── .env.example          ← Template de configuration (sans les secrets)
```

---

## Lancer le projet en local

<details>
<summary><strong>Instructions d'installation</strong></summary>

**Prérequis :** Python 3.11+ · [Clé API Groq gratuite](https://console.groq.com)

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
# → Renseigner GROQ_API_KEY dans .env

# 5. Indexer vos documents
#    Déposer vos fichiers dans docs/technique/, docs/rh/ ou docs/juridique/
python ingest.py

# 6. Démarrer
uvicorn api.main:app --reload --port 8000
# → Ouvrir http://localhost:8000
```

**Options d'indexation :**
```bash
python ingest.py                          # Incrémental (ignore les fichiers inchangés)
python ingest.py --reset                  # Reconstruire l'index depuis zéro
python ingest.py --categorie rh           # Une seule catégorie
python ingest.py --file docs/rh/note.pdf  # Un seul fichier
```

</details>

---

## Tests

```bash
pytest                                       # 46 tests
pytest --cov=src --cov-report=term-missing   # Avec couverture de code
```

> Les tests tournent **entièrement hors-ligne** : le LLM et la base vectorielle sont simulés. Aucune clé API requise.

---

<div align="center">
  <sub>Projet personnel — FastAPI · LangChain · Groq · FAISS · sentence-transformers · Render</sub>
  <br><br>
  <a href="https://chatbot-rag-xodz.onrender.com">🚀 Démo live</a>
  &nbsp;·&nbsp;
  <a href="https://chatbot-rag-xodz.onrender.com/docs">📖 API Swagger</a>
  &nbsp;·&nbsp;
  <a href="https://gomugomuNo01.github.io/Chatbot-RAG/">🌐 GitHub Pages</a>
</div>
