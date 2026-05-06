# 📚 Chatbot RAG — Assistant Documentaire Multi-Domaine

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.2-1C3C3C?logo=langchain&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-F55036?logo=meta&logoColor=white)
![FAISS](https://img.shields.io/badge/VectorDB-FAISS-0078D4)
![License](https://img.shields.io/badge/License-MIT-green)

> Un assistant interne d'entreprise basé sur RAG (Retrieval-Augmented Generation).
> Répond aux questions sur trois bases documentaires et **cite toujours ses sources** (document + page).

---

## Cas d'usage

Une entreprise met à disposition de ses collaborateurs un assistant capable de répondre à des questions sur :

| Catégorie | Exemples de documents |
|-----------|----------------------|
| ⚙️ **Technique** | Guides dev, documentation API, tutoriels framework |
| 👥 **RH** | Règlement intérieur, politique congés, onboarding |
| ⚖️ **Juridique** | Contrats types, CGU, mentions légales |

---

## Architecture

```
Utilisateur
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Frontend (HTML/CSS/JS)                          │
│  Chat · Filtre catégorie · Sources citées        │
└──────────────────┬──────────────────────────────┘
                   │ HTTP POST /api/chat
                   ▼
┌─────────────────────────────────────────────────┐
│  Backend FastAPI                                 │
│  /api/chat  /api/documents  /api/health          │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
 ┌────────────────┐  ┌────────────────┐
 │  RAG Pipeline  │  │  Groq LLM API  │
 │  (LangChain)   │  │  Llama 3.3 70B │
 └───────┬────────┘  └────────────────┘
         │
         ▼
 ┌────────────────┐    ┌────────────────────┐
 │  FAISS Index   │◄───│  Embeddings locaux │
 │  (persisté)    │    │  MiniLM-L12 (CPU)  │
 └────────────────┘    └────────────────────┘
         ▲
         │
 ┌───────┴────────────────────────────────┐
 │  Documents  PDF · DOCX · TXT           │
 │  docs/technique/  docs/rh/  docs/juridique/  │
 └────────────────────────────────────────┘
```

---

## Fonctionnalités

- **Réponses sourcées** — chaque réponse cite le document et la page
- **Multi-formats** — PDF, Word (.docx) et texte brut (.txt)
- **Filtrage par catégorie** — Technique / RH / Juridique / Tout
- **Mémoire conversationnelle** — conserve les 5 derniers échanges
- **Ré-indexation incrémentale** — seuls les fichiers nouveaux ou modifiés sont traités
- **"Je ne sais pas"** — réponse honnête quand aucun chunk pertinent n'est trouvé
- **Interface responsive** — sidebar, mobile, indicateur de frappe, score de pertinence
- **LLM gratuit via Groq** — Llama 3.3 70B, rapide et multilingue

---

## Prérequis

- Python 3.11+
- Une clé API Groq gratuite : [console.groq.com](https://console.groq.com)

---

## Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-user/chatbot-rag.git
cd chatbot-rag

# 2. Créer et activer le virtualenv
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer la clé API
cp .env.example .env
# Éditer .env et renseigner GROQ_API_KEY=votre_cle
```

---

## Démarrage rapide

### 1. Ajouter des documents

Placez vos fichiers PDF, DOCX ou TXT dans les dossiers correspondants :

```
docs/
├── technique/   ← guides dev, documentation API
├── rh/          ← règlement intérieur, politique congés
└── juridique/   ← contrats, CGU
```

### 2. Indexer les documents

```bash
# Indexer tout (incrémental par défaut)
python ingest.py

# Options avancées
python ingest.py --reset                        # Recréer l'index depuis zéro
python ingest.py --categorie rh                 # Une seule catégorie
python ingest.py --file docs/rh/nouveau.pdf     # Un seul fichier
```

### 3. Lancer l'API

```bash
uvicorn api.main:app --reload --port 8000
```

Ouvrir http://localhost:8000 dans le navigateur.

---

## API REST

### `POST /api/chat`

```json
// Requête
{
  "question": "Combien de jours de congés payés ai-je ?",
  "categorie": "rh",
  "session_id": "uuid-de-session"
}

// Réponse
{
  "answer": "Selon le règlement intérieur, vous bénéficiez de 25 jours...",
  "sources": [
    {
      "fichier": "reglement_interieur.pdf",
      "page": 4,
      "categorie": "rh",
      "score": 0.91,
      "extrait": "Chaque salarié bénéficie de 25 jours ouvrés..."
    }
  ],
  "session_id": "uuid-de-session",
  "nb_sources": 1
}
```

### `GET /api/documents`

Liste tous les documents indexés par catégorie.

### `GET /api/health`

Statut de l'API, disponibilité de l'index FAISS et infos sur les modèles.

Documentation interactive : http://localhost:8000/docs

---

## Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture
pytest --cov=src --cov-report=term-missing

# Un module spécifique
pytest tests/test_loader.py -v
```

Les tests sont entièrement hors-ligne (LLM et embeddings mockés).

---

## Structure du projet

```
chatbot-rag/
├── docs/                     ← Documents à indexer (PDF, DOCX, TXT)
│   ├── technique/
│   ├── rh/
│   └── juridique/
├── src/
│   ├── loader.py             ← Extraction multi-formats + chunking
│   ├── embedder.py           ← Embeddings MiniLM (local, CPU)
│   ├── indexer.py            ← Index FAISS + manifeste incrémental
│   ├── retriever.py          ← Recherche sémantique Top-K
│   ├── chain.py              ← Pipeline RAG (LangChain + Groq)
│   ├── memory.py             ← Historique conversationnel
│   └── utils.py              ← Logger, formatage
├── api/
│   ├── main.py               ← App FastAPI
│   ├── routes/               ← chat.py · documents.py · health.py
│   └── schemas.py            ← Modèles Pydantic
├── frontend/
│   ├── index.html            ← Interface chat
│   ├── css/style.css
│   └── js/                   ← api.js · chat.js · app.js
├── tests/
│   ├── conftest.py           ← Fixtures (PDF/TXT générés à la volée)
│   ├── test_loader.py
│   ├── test_retriever.py
│   └── test_chain.py
├── data/faiss_index/         ← Index FAISS persisté (généré)
├── ingest.py                 ← CLI d'indexation
├── config.py                 ← Configuration centralisée
├── Dockerfile
├── render.yaml
├── requirements.txt
└── .env.example
```

---

## Déploiement sur Render

### Option A — Via render.yaml (recommandé)

1. Pousser le repo sur GitHub
2. Sur [render.com](https://render.com) → **New > Web Service** → connecter le repo
3. Render détecte automatiquement `render.yaml`
4. Ajouter la variable d'environnement `GROQ_API_KEY` dans le dashboard

> **⚠️ Index FAISS sur Render Free** : le disque est éphémère.
> Commitez l'index généré (`data/faiss_index/`) ou utilisez un **Persistent Disk** (plan payant).
> Pour commiter l'index, retirez `data/` du `.gitignore`.

### Option B — Docker

```bash
docker build -t chatbot-rag .
docker run -e GROQ_API_KEY=votre_cle -p 8000:8000 chatbot-rag
```

### Frontend uniquement (GitHub Pages / Netlify)

Si vous déployez le frontend séparément du backend, modifiez `API_BASE` dans `frontend/js/api.js` :

```javascript
const API_BASE = 'https://votre-app.onrender.com/api';
```

---

## Configuration

Tous les paramètres sont dans [`config.py`](config.py) :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `GROQ_LLM_MODEL` | `llama-3.3-70b-versatile` | Modèle LLM |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Modèle d'embeddings |
| `CHUNK_SIZE` | `1000` | Taille des chunks (caractères) |
| `CHUNK_OVERLAP` | `200` | Chevauchement entre chunks |
| `TOP_K_RESULTS` | `4` | Nombre de chunks récupérés par requête |
| `SIMILARITY_THRESHOLD` | `0.3` | Score minimum de pertinence |
| `MEMORY_MAX_EXCHANGES` | `5` | Échanges conservés en mémoire |

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| LLM | Groq API — Llama 3.3 70B |
| Embeddings | sentence-transformers (local, CPU) |
| Vector DB | FAISS |
| RAG Framework | LangChain |
| Backend | FastAPI + Pydantic v2 |
| PDF | PyMuPDF |
| Word | python-docx |
| Frontend | HTML5 / CSS3 / JS vanilla |
| Tests | pytest |
| Déploiement | Render / Docker |

---

## Licence

MIT — voir [LICENSE](LICENSE)
