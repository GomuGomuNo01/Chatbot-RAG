# ─── Build stage ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Installer les dépendances dans un environnement isolé
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt


# ─── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copier les dépendances installées
COPY --from=builder /install /usr/local

# Copier le code source
COPY . .

# En production (HF_TOKEN défini au runtime), les embeddings passent par l'API HF :
# aucun modèle n'est chargé en RAM — le pré-téléchargement n'est pas nécessaire.
# En développement local (sans HF_TOKEN), sentence-transformers est utilisé.

# Port exposé (Render utilise $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
