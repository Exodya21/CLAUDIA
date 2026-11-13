FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Lectura de justificantes DENTRO del servidor: Tesseract (español) y utilidades de PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa poppler-utils fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /datos/justificantes /datos/documentos && chown -R appuser /datos
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
