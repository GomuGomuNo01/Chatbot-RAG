# Guide de contribution

Merci de votre intérêt pour DocAssist ! Ce guide vous explique comment contribuer efficacement au projet.

---

## Table des matières

- [Prérequis](#prérequis)
- [Installation locale](#installation-locale)
- [Stratégie de branches](#stratégie-de-branches)
- [Conventions de commit](#conventions-de-commit)
- [Workflow de contribution](#workflow-de-contribution)
- [Tests](#tests)
- [Linting](#linting)
- [Ouverture d'une Pull Request](#ouverture-dune-pull-request)

---

## Prérequis

- Python **3.11** ou 3.12
- Git ≥ 2.40
- Un compte [Groq](https://console.groq.com) pour obtenir une clé API

---

## Installation locale

```bash
# 1. Cloner le dépôt
git clone https://github.com/GomuGomuNo01/Chatbot-RAG.git
cd Chatbot-RAG

# 2. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env             # puis éditer .env avec votre GROQ_API_KEY

# 5. Lancer l'API
uvicorn api.main:app --reload
```

L'API est disponible sur `http://localhost:8000` et la documentation Swagger sur `http://localhost:8000/docs`.

---

## Stratégie de branches

| Branche | Rôle |
|---------|------|
| `main`  | Code en production — protégée, merge via PR uniquement |
| `dev`   | Branche d'intégration — toutes les features y convergent |
| `feat/<nom>` | Nouvelle fonctionnalité |
| `fix/<nom>`  | Correction de bug |
| `chore/<nom>` | Maintenance, dépendances, config |
| `docs/<nom>`  | Documentation uniquement |

**Règle :** créez toujours votre branche à partir de `dev`, jamais de `main`.

```bash
git checkout dev
git pull origin dev
git checkout -b feat/ma-fonctionnalite
```

---

## Conventions de commit

Ce projet suit [Conventional Commits](https://www.conventionalcommits.org/fr/).

```
<type>(<périmètre optionnel>): <description courte>

[corps optionnel]

[pied de page optionnel]
```

### Types autorisés

| Type | Usage |
|------|-------|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `style` | Formatage, espaces (pas de logique) |
| `refactor` | Refactoring sans changement fonctionnel |
| `perf` | Amélioration des performances |
| `test` | Ajout ou correction de tests |
| `chore` | Maintenance, dépendances, CI |
| `ci` | Configuration pipeline CI/CD |

### Exemples

```bash
feat(rag): ajouter le re-ranking des sources par score BM25
fix(api): corriger la gestion des fichiers PDF multi-pages
docs(readme): mettre à jour les captures d'écran
chore(deps): mettre à jour langchain vers 0.3.x
```

---

## Workflow de contribution

```
dev ──► feat/ma-feature ──► PR vers dev ──► review ──► merge
```

1. Créez votre branche depuis `dev`
2. Développez et committez selon les conventions
3. Ouvrez une PR vers `dev` (jamais directement vers `main`)
4. Attendez la review et la validation CI
5. Après merge dans `dev`, les releases sont intégrées dans `main` par le mainteneur

---

## Tests

Tous les changements fonctionnels doivent être couverts par des tests.

```bash
# Lancer tous les tests
pytest

# Avec couverture de code
pytest --cov=src --cov=api --cov-report=term-missing

# Un fichier spécifique
pytest tests/test_retriever.py -v
```

**Règle :** une PR sans tests pour du nouveau code sera refusée.

La couverture minimale attendue est de **80 %** sur les modules `src/` et `api/`.

---

## Linting

Ce projet utilise [Ruff](https://docs.astral.sh/ruff/) pour le linting et le formatage.

```bash
# Vérifier le style
ruff check .

# Corriger automatiquement
ruff check . --fix

# Vérifier le formatage
ruff format --check .

# Appliquer le formatage
ruff format .
```

La configuration Ruff se trouve dans `pyproject.toml`.

---

## Ouverture d'une Pull Request

1. Vérifiez que les tests passent localement : `pytest`
2. Vérifiez le linting : `ruff check .`
3. Remplissez entièrement le template de PR
4. Linkez l'issue correspondante avec `Closes #<numéro>`
5. Attendez la review de @GomuGomuNo01

Merci pour votre contribution ! 🙌
