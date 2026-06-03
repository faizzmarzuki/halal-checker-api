FROM python:3.11-slim

# tesseract binary + eng/osd language data, for /scan-image OCR.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[ocr,postgres]"

# Render injects $PORT; default 8000 for local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn halal_scanner.api.app:app --host 0.0.0.0 --port ${PORT}"]
