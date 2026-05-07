<div align="center">

<h1>📚 DocAssist</h1>
<h3>Un assistant IA qui répond à vos questions en se basant uniquement sur vos documents internes</h3>

<br>

[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/IA-LangChain-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)
[![Groq · Llama 3.3](https://img.shields.io/badge/LLM-Groq%20·%20Llama%203.3-F55036?logo=meta&logoColor=white)](https://console.groq.com)
[![37 tests](https://img.shields.io/badge/Tests-37%20✓-22c55e?logo=pytest&logoColor=white)](tests/)
[![Licence MIT](https://img.shields.io/badge/Licence-MIT-6366f1)](LICENSE)

<br>

### 🚀 [Voir la démo en ligne](https://chatbot-rag-xodz.onrender.com) &nbsp;·&nbsp; 📖 [Tester l'API](https://chatbot-rag-xodz.onrender.com/docs) &nbsp;·&nbsp; 🌐 [Interface web](https://gomugomuNo01.github.io/Chatbot-RAG/)

</div>

---

## Le problème concret

Les collaborateurs perdent du temps à chercher une information dans des dizaines de fichiers PDF, Word ou règlements internes. Ils ne savent pas toujours dans quel document chercher, et même quand ils trouvent le bon fichier, ils doivent le parcourir entièrement.

**DocAssist résout ça** : posez votre question en français, obtenez une réponse claire en quelques secondes, avec la source exacte (nom du document + page).

---

## Comment ça fonctionne — en termes simples

Imaginez un assistant qui aurait lu et mémorisé tous vos documents d'entreprise. Quand vous lui posez une question, il cherche les passages les plus pertinents, les transmet à un modèle d'IA, et vous renvoie une réponse — en précisant toujours où il a trouvé l'information.

**Concrètement :**

```
Vous posez une question
        ↓
L'IA cherche les passages pertinents dans vos documents
        ↓
Elle génère une réponse en se basant UNIQUEMENT sur ces passages
        ↓
Elle vous cite le document et la page source
```

> Si la réponse n'est pas dans vos documents, l'IA le dit clairement plutôt que d'inventer.

---

## Cas d'usage

> Une entreprise connecte DocAssist à trois bases documentaires internes :

| Base | Exemples de documents | Question possible |
|---|---|---|
| ⚙️ **Technique** | Guides dev, documentation API | *"Comment configurer Spring Boot ?"* |
| 👥 **Ressources humaines** | Règlement intérieur, politique congés | *"Combien de jours de congés ai-je droit ?"* |
| ⚖️ **Juridique** | Contrats, Code du travail, CGU | *"Quelles sont les clauses d'un CDI ?"* |

---

## Compétences démontrées

Ce projet couvre l'ensemble de la chaîne de développement d'une application IA en production.

### Intelligence artificielle & traitement du langage
- Implémentation d'une architecture **RAG** *(Retrieval-Augmented Generation)* de A à Z
- Intégration d'un **LLM** via l'API Groq (Llama 3.3 70B) avec gestion du prompt engineering
- Génération et indexation d'**embeddings vectoriels** multilingues en local (sans coût)
- Recherche sémantique dans une base vectorielle **FAISS** avec scoring de pertinence

### Développement backend
- **API REST** complète avec FastAPI : endpoints chat, documents, health check
- Modèles de données typés avec **Pydantic v2** (validation, sérialisation)
- Gestion de sessions conversationnelles en mémoire
- Chargement multi-formats : **PDF** (PyMuPDF), **Word** (.docx), **texte brut** (.txt)

### Développement frontend
- Interface de chat responsive en **HTML/CSS/JS vanilla** (sans framework)
- Affichage des sources citées, score de pertinence, indicateur de frappe animé
- Compatible desktop et mobile

### Qualité logicielle
- **37 tests unitaires** avec pytest — 0 appel réseau (LLM et base de données mockés)
- Couverture des cas nominaux et cas limites (fichier vide, format non supporté, etc.)
- Indexation incrémentale avec détection automatique des fichiers modifiés

### DevOps & déploiement
- **Dockerfile** multi-stage pour une image légère en production
- Déploiement automatisé sur **Render** via `render.yaml`
- **CI/CD GitHub Actions** pour le déploiement continu du frontend sur GitHub Pages
- Gestion des environnements via `.env` (secrets exclus du dépôt)

---

## Fonctionnalités principales

- **Réponses toujours sourcées** — nom du fichier + numéro de page à chaque réponse
- **Filtrage par domaine** — restreindre la recherche à Technique, RH ou Juridique
- **Mémoire de conversation** — l'assistant se souvient des 5 derniers échanges
- **Honnêteté** — si l'information n'est pas dans les documents, l'IA le dit explicitement
- **Indexation intelligente** — l'ajout d'un nouveau document ne recalcule que ce fichier
- **Entièrement gratuit à faire tourner** — LLM via Groq (free tier), embeddings en local

---

## Technologies utilisées

| Rôle | Outil | Pourquoi ce choix |
|---|---|---|
| Modèle de langage | **Groq + Llama 3.3 70B** | Gratuit, rapide, performant en français |
| Recherche sémantique | **FAISS** (Meta) | Standard industriel, ultra-rapide |
| Embeddings | **sentence-transformers** | Local, gratuit, multilingue FR/EN |
| Orchestration IA | **LangChain** | Framework RAG de référence |
| Backend | **FastAPI** | API moderne, documentation auto-générée |
| Frontend | **HTML / CSS / JS** | Aucune dépendance, livrable immédiatement |
| Tests | **pytest** | Standard Python, isolation complète |
| Déploiement | **Render + GitHub Pages** | Hébergement gratuit en production |

---

## Lancer le projet en local

<details>
<summary>Instructions d'installation (cliquer pour dérouler)</summary>

**Prérequis :** Python 3.11+ · Clé API Groq gratuite ([console.groq.com](https://console.groq.com))

```bash
# 1. Récupérer le code
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG

# 2. Créer l'environnement Python
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer la clé API
cp .env.example .env
# Renseigner GROQ_API_KEY dans le fichier .env

# 5. Déposer vos documents dans docs/technique/, docs/rh/, docs/juridique/
#    puis indexer :
python ingest.py

# 6. Démarrer
uvicorn api.main:app --reload --port 8000
```

→ Ouvrir **http://localhost:8000**

</details>

---

## Structure du projet

```
Chatbot-RAG/
├── src/              ← Pipeline IA (chargement, indexation, recherche, génération)
├── api/              ← API REST FastAPI (routes, schémas Pydantic)
├── frontend/         ← Interface web (HTML · CSS · JS)
├── tests/            ← 37 tests unitaires pytest
├── docs/             ← Vos documents à indexer (PDF · DOCX · TXT)
├── data/faiss_index/ ← Index vectoriel pré-généré
├── ingest.py         ← Script d'indexation des documents
├── config.py         ← Tous les paramètres centralisés
├── Dockerfile        ← Image Docker de production
└── render.yaml       ← Configuration de déploiement Render
```

---

<div align="center">
  <sub>Projet personnel · Développé avec FastAPI · LangChain · Groq · FAISS · sentence-transformers</sub>
</div>
