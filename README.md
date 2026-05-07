<div align="center">

# 📚 DocAssist — Assistant Documentaire RAG

**Posez des questions sur vos documents internes. Obtenez des réponses sourcées.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)
[![Groq · Llama 3.3](https://img.shields.io/badge/LLM-Groq%20·%20Llama%203.3%2070B-F55036?logo=meta&logoColor=white)](https://console.groq.com)
[![FAISS](https://img.shields.io/badge/VectorDB-FAISS-0078D4?logo=meta&logoColor=white)](https://github.com/facebookresearch/faiss)
[![Tests](https://img.shields.io/badge/Tests-pytest%2037%20✓-success?logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/Licence-MIT-22c55e)](LICENSE)

🚀 **[Demo live](https://chatbot-rag-xodz.onrender.com)** · 📖 **[API Swagger](https://chatbot-rag-xodz.onrender.com/docs)** · 🌐 **[Frontend](https://gomugomuNo01.github.io/Chatbot-RAG/)**

</div>

---

## Présentation

**DocAssist** est un assistant conversationnel d'entreprise basé sur l'architecture **RAG** *(Retrieval-Augmented Generation)*. Il permet aux collaborateurs d'interroger en langage naturel une base documentaire interne, et **cite systématiquement ses sources** — document et numéro de page — pour chaque réponse.

Le modèle ne répond qu'à partir des documents fournis : pas d'hallucination, pas d'invention.

### Cas d'usage concret

> Une entreprise met à disposition un assistant interne connecté à trois bases documentaires :
>
> | Catégorie | Contenu | Exemple de question |
> |---|---|---|
> | ⚙️ **Technique** | Guides dev, API, frameworks | *"Comment configurer Spring Boot ?"* |
> | 👥 **RH** | Règlement, politique congés, onboarding | *"Combien de jours de congés ai-je ?"* |
> | ⚖️ **Juridique** | Contrats types, CGU, code du travail | *"Quelles sont les clauses d'un CDI ?"* |

---

## Fonctionnalités

| | Fonctionnalité | Détail |
|---|---|---|
| 🎯 | **Réponses 100% sourcées** | Chaque réponse cite le fichier et la page |
| 📂 | **Multi-formats** | PDF · Word (.docx) · Texte brut (.txt) |
| 🔍 | **Recherche sémantique** | Embeddings multilingues FR/EN, score de pertinence affiché |
| 🧠 | **Mémoire conversationnelle** | Conserve les 5 derniers échanges du contexte |
| ⚡ | **Indexation incrémentale** | Seuls les fichiers nouveaux ou modifiés sont recalculés |
| 🤔 | **"Je ne sais pas"** | Réponse honnête si aucun document pertinent trouvé |
| 📱 | **Interface responsive** | Sidebar, mobile, indicateur de frappe animé |
| 💸 | **100% gratuit** | LLM via Groq (free tier) · Embeddings locaux (CPU) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Utilisateur (navigateur)                  │
│          Interface chat · Filtre catégorie · Sources         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI  /api/*                         │
│         /chat   ·   /documents   ·   /health                 │
└──────────┬────────────────────────────────┬─────────────────┘
           │                                │
           ▼                                ▼
  ┌─────────────────┐              ┌─────────────────┐
  │  Pipeline RAG   │              │   Groq Cloud    │
  │   LangChain     │─────────────▶│  Llama 3.3 70B  │
  └────────┬────────┘              └─────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
 ┌────────┐  ┌──────────────────────┐
 │ FAISS  │  │  sentence-transformers│
 │ Index  │  │  MiniLM-L12 (local)  │
 └────────┘  └──────────────────────┘
     ▲
     │  python ingest.py
     │
 ┌───┴──────────────────────────────┐
 │   docs/  PDF · DOCX · TXT        │
 │   technique/ · rh/ · juridique/  │
 └──────────────────────────────────┘
```

---

## Stack technique

| Couche | Technologie | Rôle |
|---|---|---|
| **LLM** | Groq API — Llama 3.3 70B | Génération des réponses |
| **Embeddings** | sentence-transformers MiniLM-L12 | Vectorisation locale, CPU, gratuit |
| **Vector DB** | FAISS (Meta) | Recherche sémantique ultra-rapide |
| **RAG** | LangChain 1.2 | Orchestration retrieval → prompt → LLM |
| **Backend** | FastAPI + Pydantic v2 | API REST typée, docs Swagger auto |
| **Parsing** | PyMuPDF + python-docx | Extraction PDF, Word |
| **Frontend** | HTML5 / CSS3 / JS vanilla | Aucune dépendance, léger |
| **Tests** | pytest (37 tests, 0 appel réseau) | Mocks LLM + fixtures dynamiques |
| **Déploiement** | Render + GitHub Pages + Docker | Backend + frontend séparés ou unifiés |

---

## Démarrage rapide

### Prérequis

- Python 3.11+
- Clé API Groq gratuite → [console.groq.com](https://console.groq.com)

### Installation

```bash
# Cloner
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG

# Environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Dépendances
pip install -r requirements.txt

# Clé API
cp .env.example .env
# Ouvrir .env et renseigner : GROQ_API_KEY=votre_cle
```

### Lancement en 3 étapes

```bash
# 1. Déposer vos documents
#    docs/technique/   docs/rh/   docs/juridique/

# 2. Indexer
python ingest.py

# 3. Démarrer
uvicorn api.main:app --reload --port 8000
```

→ Ouvrir **http://localhost:8000**

---

## Indexation des documents

```bash
python ingest.py                          # Tout indexer (incrémental)
python ingest.py --reset                  # Reconstruire depuis zéro
python ingest.py --categorie rh           # Une seule catégorie
python ingest.py --file docs/rh/note.pdf  # Un seul fichier
```

L'indexation est **incrémentale par défaut** : un fichier `manifest.json` trace l'empreinte de chaque document. Seuls les fichiers nouveaux ou modifiés sont recalculés.

---

## API REST

### `POST /api/chat`

```jsonc
// Requête
{
  "question": "Combien de jours de congés payés ai-je ?",
  "categorie": "rh",          // optionnel : technique | rh | juridique
  "session_id": "abc-123"     // optionnel : mémoire conversationnelle
}

// Réponse
{
  "answer": "Selon la convention collective, vous bénéficiez de 25 jours...",
  "sources": [
    {
      "fichier": "convention_collective.pdf",
      "page": 12,
      "categorie": "rh",
      "score": 0.91,
      "extrait": "Chaque salarié bénéficie de 25 jours ouvrés de congés..."
    }
  ],
  "session_id": "abc-123",
  "nb_sources": 1
}
```

### `GET /api/documents` — Liste des fichiers indexés par catégorie

### `GET /api/health` — Statut API, index FAISS et modèles chargés

📖 Documentation interactive : **[/docs](https://chatbot-rag-xodz.onrender.com/docs)**

---

## Tests

```bash
pytest                                       # 37 tests
pytest --cov=src --cov-report=term-missing   # avec couverture
pytest tests/test_loader.py -v               # module ciblé
```

Les tests tournent **entièrement hors-ligne** : le LLM et les embeddings sont mockés.

---

## Déploiement

### Render (backend + frontend intégré)

1. Connecter le repo sur [render.com](https://render.com) → **New > Web Service**
2. Render lit `render.yaml` automatiquement
3. Ajouter `GROQ_API_KEY` dans **Environment**
4. Deploy → service disponible en ~2 min

> L'index FAISS est commité dans le repo (`data/faiss_index/`), Render n'a pas besoin de le reconstruire.

### GitHub Pages (frontend seul)

1. `Settings > Pages > Source` → **GitHub Actions**
2. Renseigner l'URL Render dans [`frontend/js/config.js`](frontend/js/config.js) :
   ```js
   const RENDER_URL = 'https://votre-app.onrender.com';
   ```
3. Pousser sur `main` → le workflow déploie automatiquement

### Docker

```bash
docker build -t docassist .
docker run -e GROQ_API_KEY=votre_cle -p 8000:8000 docassist
```

---

## Configuration

Tous les paramètres dans [`config.py`](config.py) :

| Paramètre | Défaut | Description |
|---|---|---|
| `GROQ_LLM_MODEL` | `llama-3.3-70b-versatile` | Modèle Groq |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embeddings locaux |
| `CHUNK_SIZE` | `1000` | Taille des chunks (caractères) |
| `CHUNK_OVERLAP` | `200` | Chevauchement entre chunks |
| `TOP_K_RESULTS` | `4` | Chunks retournés par requête |
| `SIMILARITY_THRESHOLD` | `0.3` | Score minimal de pertinence |
| `MEMORY_MAX_EXCHANGES` | `5` | Échanges conservés en mémoire |

---

## Structure du projet

```
Chatbot-RAG/
├── docs/                      ← Vos documents (PDF · DOCX · TXT)
│   ├── technique/
│   ├── rh/
│   └── juridique/
├── src/
│   ├── loader.py              ← Extraction multi-formats + chunking
│   ├── embedder.py            ← Embeddings MiniLM (local, CPU)
│   ├── indexer.py             ← FAISS + manifeste incrémental
│   ├── retriever.py           ← Recherche sémantique Top-K
│   ├── chain.py               ← Pipeline RAG (LangChain + Groq)
│   ├── memory.py              ← Historique conversationnel
│   └── utils.py               ← Logger, formatage
├── api/
│   ├── main.py                ← App FastAPI
│   ├── routes/                ← chat · documents · health
│   └── schemas.py             ← Modèles Pydantic v2
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/                    ← config · api · chat · app
├── tests/
│   ├── conftest.py            ← Fixtures PDF/TXT dynamiques
│   ├── test_loader.py
│   ├── test_retriever.py
│   └── test_chain.py
├── data/faiss_index/          ← Index FAISS pré-généré (commité)
├── .github/workflows/         ← CI GitHub Pages
├── ingest.py                  ← CLI d'indexation
├── config.py                  ← Configuration centralisée
├── Dockerfile
├── render.yaml
└── requirements.txt
```

---

## Licence

Distribué sous licence **MIT**. Voir [LICENSE](LICENSE).

---

<div align="center">
  <sub>Construit avec LangChain · FastAPI · Groq · FAISS · sentence-transformers</sub>
</div>
