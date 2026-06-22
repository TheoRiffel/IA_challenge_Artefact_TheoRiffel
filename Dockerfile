# Empório da Música — lean CPU-only image for the customer-service agent.
#
# Design goals:
#   • zero local Python/venv setup for a reviewer — `docker compose run --rm app`.
#   • lean: CPU-only torch (no ~2.5 GB of CUDA libs), embedding model NOT baked in.
#   • the embedding model + computed embeddings download ONCE into a mounted
#     cache volume (HF_HOME), so reruns start instantly.
#
# The chat model stays a swappable config value (EMPORIO_MODEL): a hosted
# provider needs only its API key at runtime; a self-hosted OpenAI-compatible
# server needs only EMPORIO_OPENAI_BASE_URL. Embeddings are local either way, so
# the whole system can run with zero paid API.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    EMPORIO_DATA_DIR=/app/data \
    # Model download + computed-embedding cache. Mount a volume here so it
    # persists across runs (otherwise the model re-downloads every time).
    HF_HOME=/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/cache/sentence-transformers \
    EMPORIO_EMBED_CACHE=/cache/embeddings.pkl \
    # Lighter multilingual embedding model by default → fast first run.
    # Override with EMPORIO_EMBEDDING_MODEL=BAAI/bge-m3 for max retrieval quality.
    EMPORIO_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

WORKDIR /app

# 1) CPU-only torch FIRST, so sentence-transformers reuses it instead of pulling
#    the default CUDA build (saves ~2.5 GB).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2) Runtime dependencies — a cached layer that only rebuilds when deps change.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 3) Application source + data (CSVs + policy PDF). Code runs from /app/src via
#    PYTHONPATH, mirroring pyproject's `pythonpath=["src"]` — no install step.
COPY src/ ./src/
COPY data/ ./data/

# Writable mountpoint for the embedding model + .embeddings.pkl cache volume.
RUN mkdir -p /cache

# Interactive CLI by default. Override the command to run a single turn, e.g.
#   docker compose run --rm app python -m emporio_agente.cli --once "Quanto custa o Taylor 110e?"
CMD ["python", "-m", "emporio_agente.cli"]
