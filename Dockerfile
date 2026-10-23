# Servidor de PasoAPaso. No instala dependencias: usa solo Python estándar.
FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN python herramientas/empaquetar.py

ENV PYTHONUNBUFFERED=1 \
    PASOAPASO_HOST=0.0.0.0 \
    PASOAPASO_PORT=8000 \
    PASOAPASO_PRODUCCION=1 \
    PASOAPASO_PROXY=1 \
    PASOAPASO_DATOS=/app/datos

RUN mkdir -p /app/datos
VOLUME ["/app/datos"]
EXPOSE 8000

CMD ["python", "-m", "servidor", "--host", "0.0.0.0", "--port", "8000"]
