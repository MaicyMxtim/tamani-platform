FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
# Bake the embedding model into the image so the read-only, egress-locked
# container never downloads anything at runtime.
ENV PYTHONPATH=/install/lib/python3.12/site-packages
ENV FASTEMBED_CACHE_PATH=/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
COPY --from=builder /models /models
ENV FASTEMBED_CACHE_PATH=/models
WORKDIR /app
COPY main.py provider.py semcache.py budget.py ./
COPY prompts/ prompts/
USER 10001
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
