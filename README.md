# CE ICCD UTEM - Monorepo (Frontend + Backend)

Este repositorio esta organizado en dos modulos principales:

- `frontend/`: landing en Astro + Tailwind.
- `backend/`: API FastAPI para el chatbot con RAG (Ollama + FAISS).

## Estructura

```text
.
|-- frontend/
|   |-- src/
|   |-- public/
|   |-- package.json
|   `-- README.md
|-- backend/
|   |-- app/
|   |-- data/
|   |-- requirements.txt
|   `-- README.md
|-- GOOD_PRACTICES.md
`-- README.md
```

## Requisitos

- Node.js 18+
- npm 9+
- Python 3.10+ (recomendado 3.11)
- Ollama corriendo localmente (para el backend chatbot)

## Inicio rapido

1. Frontend
```bash
cd frontend
npm install
npm run dev
```
Abre `http://localhost:4321`.

2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```
Health check: `http://localhost:8000/health`.

## Arranque rapido en Windows

Desde la raiz del proyecto puedes ejecutar:

```bat
arranque.bat
```

Este script:
1. Analiza dependencias de frontend y backend.
2. Instala lo faltante automaticamente.
3. Abre dos ventanas (`frontend` y `backend`) y levanta ambos servicios.

Modos utiles:
```bat
arranque.bat --check
arranque.bat --prepare-only
```

## Compartir link temporal (1 comando)

Desde la raiz del proyecto:

```bat
compartir.bat
```

Que hace este comando:
1. Levanta backend local (si no estaba corriendo).
2. Crea tunel publico para backend (Cloudflare Quick Tunnel).
3. Compila frontend apuntando al backend publico.
4. Levanta frontend estatico y crea su tunel publico.
5. Imprime los links finales y abre automaticamente el frontend en tu navegador.

Para detener todo:

```bat
detener_compartir.bat
```

Nota: los links de `trycloudflare.com` son temporales y cambian en cada ejecucion.

Si no quieres que abra navegador automatico:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\share-link.ps1 -NoOpenBrowser
```

## Variables de entorno

- Frontend: `frontend/.env.example`
- Backend: `backend/.env.example`

## Despliegue

### Opcion 1: Docker Compose

1. Genera `backend/.env` con:

```powershell
.\scripts\init-shared-deploy.ps1
```

2. Desde la raiz ejecuta:

```bash
docker compose build
docker compose up -d
```

Queda disponible en:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

El frontend queda sirviendo el sitio estatico y reenviando `/api/*` al backend.

### Persistencia de datos

- El contenido editable del sitio (`muro`, `integrantes`, `presentaciones`, `cuentas`) ahora vive en PostgreSQL.
- La pizarra compartida de `Crea` tambien vive en PostgreSQL.
- La base se persiste en el volumen `postgres_data`.
- Los PDFs de presentaciones, imagenes de integrantes CE y proyectos enviados siguen viviendo en disco.
- Si la base arranca vacia por primera vez, el backend importa los datos semilla desde los JSON legacy una sola vez.

Si otra persona despliega el proyecto y quiere conservar tambien los datos:

1. Debe llevarse el codigo.
2. Debe restaurar `backups/ce-iccd.sql`.
3. `backend/data/uploads` y `backend/data/project_submissions` ya vienen dentro de este repo privado.

### Backup y restore

Crear backup:

```bash
docker compose exec postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > backups/ce-iccd.sql
```

En PowerShell tambien puedes usar:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

Restaurar backup:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/ce-iccd.sql
```

En PowerShell:

```powershell
.\scripts\db-restore.ps1 -InputPath backups\ce-iccd.sql
```

Guia detallada: [DEPLOY_DATABASE.md](/C:/Users/avega/Desktop/BOT_GABRIELITO/landing_page_movile/DEPLOY_DATABASE.md)

Guia paso a paso para entrar a PostgreSQL, compartir la base y traspasar el proyecto:
[README_BASE_DE_DATOS.md](/C:/Users/avega/Desktop/BOT_GABRIELITO/landing_page_movile/README_BASE_DE_DATOS.md)

### Opcion 2: despliegue separado

- Backend: usa `backend/Dockerfile` o instala con el `requirements.txt` de la raiz.
- Frontend: usa `frontend/Dockerfile` o compila con `npm run build`.

## Convenciones del repositorio

- Cada modulo mantiene su propio README y dependencias.
- Evitar codigo suelto en la raiz.
- Configuraciones y scripts deben vivir en su modulo (`frontend/` o `backend/`).
- Ver guia completa en [GOOD_PRACTICES.md](/C:/Users/avega/Desktop/BOT_GABRIELITO/landing_page_movile/GOOD_PRACTICES.md).
