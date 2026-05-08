# Politique de sécurité

## Versions supportées

| Version | Support sécurité |
|---------|-----------------|
| `main` (dernière) | ✅ Supportée |
| `dev` (branche d'intégration) | ⚠️ En développement actif |
| Versions antérieures | ❌ Non supportées |

## Signaler une vulnérabilité

**Ne pas ouvrir d'issue publique pour les failles de sécurité.**

Si vous découvrez une vulnérabilité dans ce projet, merci de la signaler de manière responsable :

1. **Envoyez un e-mail à :** [cedrickouadio22@gmail.com](mailto:cedrickouadio22@gmail.com)
2. **Objet :** `[SECURITY] <description courte>`
3. **Contenu attendu :**
   - Description de la vulnérabilité
   - Étapes pour la reproduire
   - Impact potentiel estimé
   - Votre suggestion de correction (optionnel)

### Délai de réponse

| Étape | Délai cible |
|-------|-------------|
| Accusé de réception | 48 heures |
| Évaluation initiale | 7 jours |
| Correction et publication | 30 jours selon la criticité |

## Bonnes pratiques pour les contributeurs

- Ne jamais committer de secrets, clés API, mots de passe ou tokens dans le dépôt
- Le fichier `.env` est listé dans `.gitignore` — ne jamais le committer
- Les variables sensibles sont injectées via les secrets GitHub Actions (`GROQ_API_KEY`)
- Les dépendances sont auditées automatiquement par `pip-audit` dans la CI et par Dependabot chaque semaine

## Dépendances tierces

Ce projet repose sur des bibliothèques open source (FastAPI, LangChain, FAISS…). Les mises à jour de sécurité sont gérées via [Dependabot](.github/dependabot.yml) avec un cycle hebdomadaire.
