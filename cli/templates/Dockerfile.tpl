FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY main.py .
USER 10001
EXPOSE __PORT__
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "__PORT__"]
