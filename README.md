---
title: DocAssist
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Assistant documentaire RAG, posez vos questions sur vos PDF
---

<div align="center">

# DocAssist

### L'assistant qui lit vos documents à votre place et répond avec les sources à l'appui

<br>

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white&style=flat-square)](https://langchain.com)
[![Claude Haiku](https://img.shields.io/badge/Claude%20Haiku-CC785C?logo=anthropic&logoColor=white&style=flat-square)](https://console.anthropic.com)
[![FAISS](https://img.shields.io/badge/FAISS%20%2B%20BM25-0078D4?logo=meta&logoColor=white&style=flat-square)](https://github.com/facebookresearch/faiss)
[![CI](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/GomuGomuNo01/Chatbot-RAG/actions/workflows/ci.yml)
[![HF Spaces](https://img.shields.io/badge/Live%20Demo-HuggingFace-FFD21E?logo=huggingface&logoColor=black&style=flat-square)](https://gomugomuNo01-chatbot-rag.hf.space)

<br>

**[🚀 Essayer la démo en ligne](https://gomugomuNo01-chatbot-rag.hf.space)** &nbsp;·&nbsp; **[📖 Documentation de l'API](https://gomugomuNo01-chatbot-rag.hf.space/docs)**

<br>

</div>

---

## En bref

**DocAssist transforme vos documents en assistant capable d'y répondre à votre place.**

Vous déposez vos fichiers (contrats, guides, procédures, fiches de poste...), vous posez une question en français ou en anglais, et l'assistant vous répond en citant précisément le document, la page et le passage d'où vient l'information. Si la réponse ne se trouve nulle part dans vos documents, il le dit clairement au lieu d'inventer une réponse approximative.

C'est l'équivalent d'un collègue qui aurait lu tous vos documents et qui saurait toujours vous dire où il a trouvé l'information.

---

## Pourquoi ce projet

Dans la plupart des organisations, l'information est éclatée entre des dizaines de fichiers : contrats, guides techniques, règlements internes, fiches de poste, conventions collectives. Retrouver une réponse précise prend du temps, et souvent on ne sait même pas dans quel document chercher.

DocAssist règle ce problème en quelques secondes : il retrouve le bon passage dans le bon document et formule une réponse claire, sourcée et vérifiable.

---

## Ce que peut faire DocAssist

| | |
|:---:|:---|
| 🎯 | **Réponses sourcées** : chaque réponse indique le fichier, la page et l'extrait exact utilisé |
| 📂 | **Plusieurs formats acceptés** : PDF (jusqu'à 500 pages), Word (.docx), texte brut (.txt), Markdown (.md) |
| 🗂️ | **Espaces de travail séparés** : créez autant de thématiques que nécessaire (RH, juridique, technique...), chacune avec ses propres documents |
| 🔍 | **Recherche à deux niveaux** : l'assistant combine une recherche par sens et une recherche par mots-clés pour ne rien manquer |
| 🏆 | **Classement intelligent des résultats** : les passages les plus pertinents remontent en priorité avant d'être envoyés à l'IA |
| 🧠 | **Mémoire de la conversation** : l'assistant se souvient des échanges précédents dans la même discussion |
| ⚡ | **Réponses instantanées pour les questions déjà posées** : une question similaire à une précédente obtient une réponse immédiate, sans nouveau calcul |
| 💰 | **Budget maîtrisé** : une limite quotidienne de requêtes évite les mauvaises surprises de coût |
| 🔄 | **Mise à jour intelligente** : seuls les fichiers modifiés sont retraités lors d'un nouvel import |
| ☁️ | **Rien ne se perd** : documents et index de recherche sont sauvegardés en ligne, même après un redémarrage |

---

## Comment ça fonctionne

### En langage simple

1. **Vous importez vos documents** depuis l'interface. Chaque fichier est automatiquement découpé en petits passages, puis analysé et indexé.
2. **Vous posez une question**, en français ou en anglais, comme vous le feriez à un collègue.
3. **DocAssist retrouve les passages les plus pertinents** parmi tous vos documents, en croisant deux méthodes de recherche complémentaires.
4. **L'intelligence artificielle rédige une réponse** en s'appuyant uniquement sur ces passages, et affiche ses sources en bas de réponse.

### Le détail technique, pour les curieux

<details>
<summary><strong>Voir le schéma du pipeline</strong></summary>

```
Votre question
      │
      ▼
┌───────────────────────┐
│   Cache sémantique    │──── Question déjà vue ──► réponse instantanée
└──────────┬────────────┘
           │ Question nouvelle
           ▼
┌──────────────────────────────────────────────────────────┐
│  Enrichissement de la requête                            │
│  · Expansion d'acronymes  (PHP → "PHP Hypertext...")     │
│  · Détection d'articles juridiques  (L1234-5...)         │
│  · Réécriture contextuelle  (jusqu'à 3 reformulations)   │
└──────────┬───────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  Recherche hybride                                       │
│  ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │  FAISS           │   │  BM25 Okapi custom           │ │
│  │  (recherche par  │   │  (recherche par mots-clés,   │ │
│  │   sens)          │   │   stemming FR/EN, bigrammes) │ │
│  └────────┬─────────┘   └──────────────┬───────────────┘ │
│           └──────── Fusion pondérée ────┘                 │
│           Le poids s'adapte au type de question :         │
│           acronymes / termes exacts → mots-clés priorisés │
│           questions conceptuelles    → sens priorisé      │
└──────────┬───────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  Reranking  (modèle de classement BGE)                   │
│  reclasse les 20 meilleurs candidats par pertinence      │
└──────────┬───────────────────────────────────────────────┘
           │  Les 6 passages les plus pertinents
           ▼
┌──────────────────────────────────────────────────────────┐
│  Claude Haiku (IA)                                        │
│  rédige la réponse à partir des extraits uniquement       │
└──────────┬───────────────────────────────────────────────┘
           ▼
    Réponse rédigée  +  sources (fichier, page, score)
```

</details>

<details>
<summary><strong>Voir l'architecture cloud</strong></summary>

```
┌─────────────────────────────────────────────────────────────┐
│  HuggingFace Spaces  (hébergement Docker, 16 Go de RAM)      │
│                                                               │
│  FastAPI  ──►  /            (interface web)                  │
│            ──►  /api        (API REST)                       │
│                                                               │
│  Au démarrage :                                               │
│    Cloudflare R2   ──►  restaure les documents                │
│    HuggingFace Hub ──►  restaure l'index de recherche          │
│                                                               │
│  À chaque import de document :                                │
│    Fichier  ──►  Cloudflare R2  (sauvegarde)                  │
│    Index reconstruit  ──►  HuggingFace Hub  (sauvegarde)       │
└─────────────────────────────────────────────────────────────┘
```

FastAPI sert à la fois l'interface web et l'API, sur la même adresse, ce qui simplifie le déploiement sur n'importe quelle plateforme.

</details>

---

## Stack technique

### Intelligence artificielle

| Composant | Choix | Pourquoi |
|---|---|---|
| **Modèle de langage** | Claude Haiku (Anthropic) | Excellente compréhension du français, suit les instructions avec rigueur, coût très faible (environ 0,006 $ par question) |
| **Embeddings** | `BAAI/bge-small-en-v1.5` (fastembed/ONNX) | Léger (37 Mo), rapide sur processeur classique, aucun GPU nécessaire |
| **Recherche par sens** | FAISS (similarité cosinus) | Standard de l'industrie pour la recherche vectorielle, résultat en microsecondes |
| **Recherche par mots-clés** | BM25 Okapi (implémentation maison) | Stemming français/anglais et bigrammes, complète FAISS sur les termes exacts et les acronymes |
| **Fusion des résultats** | Pondération dynamique | Le poids entre les deux moteurs s'ajuste selon le type de question détecté |
| **Reranking** | BGE-reranker-base (API HuggingFace) | Reclasse les candidats par pertinence réelle avant envoi à l'IA |
| **Orchestration** | LangChain | Enchaîne la recherche et la génération de réponse |

### Infrastructure

| Composant | Choix | Pourquoi |
|---|---|---|
| **Backend** | FastAPI + Pydantic v2 | API REST moderne, documentation générée automatiquement |
| **Extraction de texte** | PyMuPDF + python-docx | PDF (avec gestion correcte des accents) et Word natif |
| **Cache** | Fichier JSON (similarité + mots-clés) | Réponses instantanées pour les questions similaires, conservées 7 jours |
| **Stockage des fichiers** | Cloudflare R2 | Compatible S3, gratuit jusqu'à 10 Go |
| **Sauvegarde de l'index** | HuggingFace Hub | Survit aux redémarrages du serveur |
| **Interface** | HTML5 / CSS3 / JS natif | Aucune dépendance, disponible en français et en anglais |
| **Tests** | pytest, 100 % hors ligne | Fonctionne sans clé API, rien n'est envoyé en ligne pendant les tests |
| **Intégration continue** | GitHub Actions | Tests automatiques sur Python 3.11 et 3.12 à chaque mise à jour du code |
| **Hébergement** | HuggingFace Spaces (Docker) | 16 Go de RAM gratuits, mise en production automatique |

---

## Structure du projet

```
chatbot-rag/
│
├── src/                       ← Cœur du pipeline IA
│   ├── loader.py              ← Extraction et découpage des documents (PDF/DOCX/TXT/MD, max 500 pages)
│   ├── embedder.py            ← Vectorisation des textes
│   ├── indexer.py             ← Construction des index de recherche
│   ├── bm25_store.py          ← Moteur de recherche par mots-clés
│   ├── retriever.py           ← Recherche hybride (sens + mots-clés)
│   ├── reranker.py            ← Reclassement des résultats par pertinence
│   ├── chain.py               ← Question → passages pertinents → réponse
│   ├── cache.py               ← Cache des réponses déjà données
│   ├── memory.py              ← Historique de la conversation
│   ├── rate_limiter.py        ← Compteur de requêtes journalières
│   ├── query_processor.py     ← Amélioration automatique de la question posée
│   ├── hf_store.py            ← Sauvegarde/restauration de l'index en ligne
│   ├── storage.py             ← Sauvegarde/restauration des fichiers en ligne
│   └── utils.py               ← Fonctions partagées
│
├── api/                       ← API REST
│   ├── main.py                ← Démarrage de l'application et restauration des données
│   ├── schemas.py             ← Formats de données échangées
│   └── routes/
│       ├── chat.py            ← Point d'entrée pour poser une question
│       ├── documents.py       ← Gestion des espaces de travail et des documents
│       └── health.py          ← Vérification de l'état du service
│
├── frontend/                  ← Interface web (français/anglais)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── config.js
│       └── api.js · chat.js · app.js · i18n.js
│
├── tests/                     ← Tests automatisés (hors ligne)
│   ├── conftest.py · test_loader.py · test_retriever.py · test_chain.py
│
├── data/                      ← Données générées à l'usage (non versionnées)
│   ├── faiss_index/           ← Sauvegardé sur HuggingFace Hub
│   └── workspaces.json        ← Sauvegardé sur Cloudflare R2
│
├── docs/                      ← Vos documents (non versionnés)
│   └── <workspace>/
│
├── config.py                  ← Tous les réglages du projet, centralisés
├── Dockerfile                 ← Configuration de déploiement
├── .env.example                ← Modèle de configuration
├── requirements.txt            ← Dépendances de développement
└── requirements-prod.txt       ← Dépendances de production (image allégée)
```

---

## Démarrage rapide

### En local

**Prérequis :** Python 3.11 ou plus récent, et une [clé API Anthropic](https://console.anthropic.com).

```bash
# Cloner et installer
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG
python -m venv .venv && source .venv/bin/activate  # Sous Windows : .venv\Scripts\activate
pip install -r requirements.txt

# Configurer
cp .env.example .env
# Éditer .env : renseigner ANTHROPIC_API_KEY (obligatoire)
#               renseigner HF_TOKEN pour activer le reranking (recommandé)

# Lancer
uvicorn api.main:app --port 7860 --reload
# → disponible sur http://localhost:7860
```

Sans les variables `R2_*` ni `HF_REPO_ID`, l'application fonctionne entièrement en local : les documents restent dans `docs/<workspace>/` et l'index dans `data/faiss_index/`.

> **Sous Windows** : ajoutez `HF_HUB_DISABLE_SYMLINKS_WARNING=1` dans `.env` pour supprimer un avertissement inoffensif de HuggingFace.

### Sur HuggingFace Spaces

<details>
<summary><strong>Guide de déploiement complet</strong></summary>

**1. Créer le Space**

Sur [huggingface.co/new-space](https://huggingface.co/new-space) :
- SDK : **Docker** · Modèle : **Blank** · Matériel : **CPU Basic (gratuit)**

**2. Créer le dépôt pour l'index de recherche**

Sur [huggingface.co/new](https://huggingface.co/new) :
- Type : **Dataset** · Nom : `chatbot-rag-index` · Visibilité : **Privée**

**3. Pousser le code**

```bash
git remote add hf https://huggingface.co/spaces/VOTRE_USERNAME/chatbot-rag

# Créer une branche sans historique (évite les fichiers binaires anciens de plus de 10 Mo)
git checkout --orphan hf-deploy
git add -A
git commit -m "deploy"
git push hf hf-deploy:main --force
git checkout main && git branch -D hf-deploy
```

**4. Configurer les secrets** (dans Space Settings → Variables and secrets)

| Variable | Type | Valeur |
|---|---|---|
| `ANTHROPIC_API_KEY` | 🔒 Secret | Votre clé Anthropic |
| `HF_TOKEN` | 🔒 Secret | Token HuggingFace (droits d'écriture) |
| `HF_REPO_ID` | Variable | `username/chatbot-rag-index` |
| `R2_ACCOUNT_ID` | 🔒 Secret | Identifiant du compte Cloudflare R2 |
| `R2_ACCESS_KEY_ID` | 🔒 Secret | Clé d'accès R2 |
| `R2_SECRET_ACCESS_KEY` | 🔒 Secret | Clé secrète R2 |
| `R2_BUCKET_NAME` | Variable | Nom du bucket |
| `ANTHROPIC_MODEL` | Variable | `claude-haiku-4-5-20251001` |
| `DAILY_REQUEST_LIMIT` | Variable | `20` (0 = illimité) |
| `RERANKER_ENABLED` | Variable | `true` |

Le déploiement démarre automatiquement une fois les variables configurées (environ 5 à 10 minutes la première fois).

</details>

---

## Configuration avancée

Ces réglages sont disponibles dans [`config.py`](config.py) et peuvent aussi être définis par variables d'environnement :

| Paramètre | Valeur par défaut | Rôle |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Modèle d'IA utilisé pour répondre |
| `DAILY_REQUEST_LIMIT` | `10` | Nombre maximal de questions traitées par jour (0 = illimité) |
| `CHUNK_SIZE` | `900` | Taille des passages découpés, en caractères |
| `CHUNK_OVERLAP` | `220` | Chevauchement entre deux passages consécutifs |
| `MAX_PDF_PAGES` | `500` | Nombre maximal de pages traitées par PDF |
| `TOP_K_RESULTS` | `6` | Nombre de passages transmis à l'IA pour rédiger la réponse |
| `TOP_K_RETRIEVAL` | `20` | Nombre de candidats examinés par moteur de recherche avant fusion |
| `HYBRID_BM25_WEIGHT` | `0.45` | Poids accordé à la recherche par mots-clés dans la fusion |
| `RERANKER_ENABLED` | `false` | Active le reclassement des résultats par pertinence |
| `MEMORY_MAX_EXCHANGES` | `4` | Nombre d'échanges gardés en mémoire dans une conversation |
| `RESPONSE_CACHE_TTL_SECONDS` | `604800` | Durée de conservation du cache de réponses (7 jours) |

**Changer de modèle Claude :**
```bash
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # rapide, environ 0,006 $ par question
ANTHROPIC_MODEL=claude-sonnet-4-5           # plus précis, environ 0,05 $ par question
```

> ⚠️ Si vous changez `EMBEDDING_MODEL`, supprimez le dossier `data/faiss_index/` avant de réindexer vos documents : les index générés par des modèles différents ne sont pas compatibles entre eux.

---

## Tests

```bash
pytest                                        # Suite de tests complète
pytest --cov=src --cov-report=term-missing    # Avec le taux de couverture du code
```

Les tests s'exécutent entièrement hors ligne : le modèle d'IA et le moteur de recherche sont simulés, aucune clé API n'est nécessaire.

---

<div align="center">

Projet personnel · FastAPI · LangChain · Claude Haiku · FAISS · BM25 · fastembed/ONNX · BGE-reranker · HuggingFace Spaces · Cloudflare R2

</div>
