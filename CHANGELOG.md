# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

---

## [Non publié]

### En cours
- Rien pour le moment

---

## [1.2.0] — 2026-05-08

### Ajouté
- Pipeline CI/CD GitHub Actions (3 jobs : tests pytest sur Python 3.11/3.12, linting Ruff, audit pip-audit)
- Dependabot pour les mises à jour automatiques des dépendances (pip hebdomadaire, Actions mensuel)
- Templates d'issues GitHub (rapport de bug, demande de fonctionnalité)
- Template de Pull Request avec checklist
- Fichier `CODEOWNERS` pour les reviews obligatoires
- Guide de contribution (`CONTRIBUTING.md`)
- Politique de sécurité (`SECURITY.md`)
- Configuration Ruff dans `pyproject.toml`
- Licence MIT (`LICENSE`)

### Modifié
- Refonte responsive complète du frontend (mobile-first, `clamp()`, tiroir latéral, cibles tactiles ≥ 44 px)
- Toutes les tailles de police converties de `px` vers `rem`/`clamp()`
- Accessibilité renforcée : `aria-expanded` sur le menu hamburger, fermeture par touche Échap
- Redesign de la section Sources (rangées plates, puce monospace, sans cercles colorés)
- Micro-interactions UI : skeleton loading, scroll fluide, animation de focus

---

## [1.1.0] — 2025-04-20

### Ajouté
- Interface frontend complète en HTML/CSS/JS vanilla
- Sidebar de navigation avec historique des conversations
- Affichage des sources avec score de pertinence
- Déploiement automatique sur Render
- GitHub Pages pour le frontend statique

### Modifié
- Passage de OpenAI à Groq (Llama 3.3 70B) pour l'inférence
- Pipeline RAG optimisé (FAISS + LangChain)

---

## [1.0.0] — 2025-03-15

### Ajouté
- API FastAPI avec endpoints `/chat`, `/ingest`, `/health`
- Pipeline RAG : ingestion PDF, vectorisation FAISS, récupération contextuelle
- 37 tests unitaires et d'intégration (pytest)
- Documentation Swagger auto-générée
- Configuration Docker pour déploiement

[Non publié]: https://github.com/GomuGomuNo01/Chatbot-RAG/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/GomuGomuNo01/Chatbot-RAG/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/GomuGomuNo01/Chatbot-RAG/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/GomuGomuNo01/Chatbot-RAG/releases/tag/v1.0.0
