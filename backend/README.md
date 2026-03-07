# Backend - Chatbot CE ICCD UTEM

API FastAPI que entrega respuestas del chatbot usando RAG con Ollama + FAISS.

## Requisitos

- Python 3.10+ (recomendado 3.11)
- Ollama instalado y ejecutandose localmente

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuracion

Copiar variables base:

```bash
copy .env.example .env
```

Variables principales:

- `APP_ENV`
- `TRUSTED_HOSTS`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL` (opcional, si no quieres usar `POSTGRES_*`)
- `CORS_ALLOW_ORIGINS` (separadas por coma)
- `MAX_UPLOAD_SIZE_MB`
- `MAX_REQUEST_SIZE_MB`
- `OUTBOUND_REQUEST_TIMEOUT_S`
- `ALLOWED_REMOTE_IMAGE_HOSTS`
- `OLLAMA_URL`
- `CHAT_MODEL`
- `EMBED_MODEL`
- `OLLAMA_TIMEOUT_S`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_TOKEN_SECRET`
- `ADMIN_TOKEN_TTL_S`
- `STUDENT_TOKEN_SECRET`
- `STUDENT_TOKEN_TTL_S`
- `STUDENT_PASSWORD_ITERATIONS`

## Ejecucion

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:

- `GET /health`
- `POST /chat`
- `GET /projects/public`
- `POST /projects/submit`
- `GET /content/centers`
- `GET /content/presentations`
- `GET /content/alumni-wall`
- `POST /admin/login`
- `GET /admin/me`
- CRUD admin para proyectos, centros, integrantes, presentaciones y muro del recuerdo

## Estructura

```text
backend/
|-- app/
|   |-- api.py
|   `-- chatbot.py
|-- data/
|   |-- rag_store_chunks/
|   |-- PDFs/
|   `-- PDFs_chunks_out/
|-- notebooks/
`-- requirements.txt
```

## Buenas practicas del backend

- No asumir directorio de ejecucion; usar rutas relativas al archivo.
- Mantener configuracion por variables de entorno.
- Validar payloads con Pydantic.
- Cargar modelos/indices una vez al iniciar la app.
- En `APP_ENV=production`, no usar secretos por defecto.
- Se aplican headers de seguridad, hosts confiables y limites de tamano para requests/uploads.

## Despliegue con Docker

Desde la raiz del monorepo:

```bash
copy .env.example .env
docker compose build
docker compose up -d
```

O directamente con la imagen del backend:

```bash
docker build -t ce-iccd-backend .
docker run --env-file .env -p 8000:8000 ce-iccd-backend
```

## Base de datos y migracion inicial

- El backend usa PostgreSQL si encuentra `POSTGRES_*` o `DATABASE_URL`.
- Si no encuentra configuracion de PostgreSQL, usa SQLite local en `backend/data/ce_iccd.db`.
- En el primer arranque, si la base esta vacia, importa los datos semilla desde:
  - `backend/data/content/centers.json`
  - `backend/data/content/presentations.json`
  - `backend/data/content/alumni_wall.json`
  - `backend/data/content/student_accounts.json`

Despues de ese primer arranque, los cambios nuevos quedan en la base de datos, no en esos JSON. Esa importacion automatica ocurre una sola vez para no recrear datos que luego hayas eliminado desde admin.

## Traspaso a otra persona

Para que otra persona despliegue el sistema con los mismos datos:

1. Clonar el repo.
2. Copiar `backend/.env`.
3. Restaurar un dump de PostgreSQL.
4. Copiar `backend/data/uploads` si existen imagenes o PDFs subidos por admin.
5. Levantar `docker compose up -d`.
