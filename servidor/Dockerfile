# Servidor de GreenSense IoT. Se construye desde servidor/.
FROM python:3.14-slim

WORKDIR /servidor
COPY pyproject.toml alembic.ini README.md ./
COPY greensense ./greensense
COPY migraciones ./migraciones
COPY simulador ./simulador
# Editable: `greensense migrar` busca alembic.ini y las migraciones junto al código.
RUN pip install --no-cache-dir -e .

# Sin privilegios: solo necesita salir a la base de datos y al broker.
RUN useradd --create-home greensense
USER greensense

EXPOSE 8000
# Aplica las migraciones pendientes y arranca. Si la base aún no está lista, falla y Docker
# lo vuelve a intentar.
CMD ["sh", "-c", "greensense migrar && exec uvicorn --factory greensense.composicion:crear_aplicacion --host 0.0.0.0 --port 8000 --proxy-headers"]
