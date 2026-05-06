# ─── Build stage ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Installer les dépendances dans un environnement isolé
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copier les dépendances installées
COPY --from=builder /install /usr/local

# Copier le code source
COPY . .

# Pré-télécharger le modèle d'embeddings au build (évite le timeout au 1er démarrage)
RUN python -c "from src.embedder import get_embeddings; get_embeddings()" \
    || echo "⚠️  Pré-chargement embeddings ignoré (variable GROQ_API_KEY absente)"

# Port exposé (Render utilise $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
