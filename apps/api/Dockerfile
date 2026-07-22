# Multi-stage build: dependencies compiled in the builder, discarded from
# the final image. Target: under 200 MB, non-root, no build tools shipped.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
# Non-root user; the container refuses to run as root.
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY main.py .
COPY data/ data/
USER 10001
EXPOSE 8000
# Liveness probes /health/live, readiness probes /health/ready.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
