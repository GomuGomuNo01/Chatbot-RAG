# ─── Build stage ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt


# ─── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="DocAssist"
LABEL description="Assistant documentaire RAG — FastAPI + FAISS + Claude"

WORKDIR /app

# Copier les dépendances installées depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source (les répertoires data/ et docs/ sont dans .dockerignore)
COPY . .

# Créer les dossiers de données avec les bonnes permissions
# (données persistées via R2 + HF Hub, pas dans l'image)
RUN mkdir -p data/faiss_index docs && chmod -R 777 data docs

# Pré-télécharger le modèle fastembed au build pour éviter le téléchargement
# à chaud au démarrage (améliore le cold-start et évite les timeouts HF Spaces)
RUN python -c "\
from fastembed import TextEmbedding; \
print('Téléchargement du modèle fastembed...'); \
model = TextEmbedding('BAAI/bge-small-en-v1.5', threads=1); \
print('Modèle prêt.')" || echo "Pré-téléchargement ignoré (pas de réseau au build)"

# HF Spaces utilise le port 7860 par défaut.
# La variable PORT peut être surchargée via les secrets du Space.
ENV PORT=7860

EXPOSE 7860

# Health check adapté au port HF Spaces
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
    CMD python -c "\
import urllib.request, os; \
port = os.getenv('PORT', '7860'); \
urllib.request.urlopen(f'http://localhost:{port}/api/health')"

# Démarrage avec le port défini dans $PORT (7860 par défaut sur HF Spaces)
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
