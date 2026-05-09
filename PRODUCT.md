# DocAssist — PRODUCT.md

## Product Purpose

Assistant documentaire RAG pour équipes entreprise. L'utilisateur pose une question en langage naturel ; le système retrouve les passages pertinents dans les documents indexés et génère une réponse avec citations de sources. Pas un chatbot généraliste : un outil de recherche sémantique précis sur corpus fermé.

## Register

product

## Users

Employés d'entreprise francophones (et anglophones secondairement) qui ont besoin de retrouver rapidement une information dans la documentation interne : équipes RH, techniques, juridiques. Ils sont dans une tâche ; l'interface doit s'effacer derrière la réponse. Ils utilisent principalement un ordinateur de bureau, mais aussi des tablettes et mobiles.

## Brand Tone

Sobre, précis, professionnel. Pas de familiarité, pas d'enthousiasme artificiel. La crédibilité vient des sources citées, pas du ton. L'outil doit inspirer confiance comme un moteur de recherche interne de qualité, pas comme un assistant IA grand public.

## Anti-references

- OpenAI ChatGPT UI — trop centré, trop rond, trop bleu, trop "AI product"
- Claude.ai — même problème : bulles, centrage, violet, générique
- Intercom / Drift — chat widget = contexte faux, pas un outil métier
- Notion AI — trop éditorial pour un produit orienté recherche

## Strategic Principles

1. **Sources avant réponse** : une réponse sans source est suspecte. Les citations sont premières, pas un détail.
2. **Précision > Fluidité** : mieux vaut refuser que halluciner. Le ton ne compense pas les approximations.
3. **Densité d'information** : l'utilisateur veut la réponse, pas une interface spectaculaire.
4. **Persistance entre sessions** : les documents indexés survivent aux redéploiements (via Cloudflare R2).
5. **Multilinguisme** : FR / EN bascule en cours de session, les réponses suivent la langue de la question.
