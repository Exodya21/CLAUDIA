# Odoo 20 Community del despacho = imagen oficial + herramientas para LEER documentos en el propio servidor
# (sin servicios externos): pdftotext/pdftoppm (poppler) y Tesseract con español para los escaneados.
# Las usa sp_contabilidad para leer facturas recibidas (referencia: Sistema Propio, services/receipts.py).
FROM odoo:20
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*
USER odoo
