# Despliegue con Base de Datos

Esta aplicacion separa:

- `Git`: codigo
- `PostgreSQL`: contenido editable y pizarra compartida
- `backend/data/uploads`: archivos que siguen en disco
- `backend/data/project_submissions`: proyectos enviados por alumnos

## 1. Preparar entorno

Requisitos:

- Docker Desktop
- Git

Clonar repo:

```bash
git clone <URL_DEL_REPO>
cd landing_page_movile
```

Generar `backend/.env`:

```powershell
.\scripts\init-shared-deploy.ps1
```

Ese script genera secretos nuevos y deja el despliegue listo sin subir `backend/.env` al repo.

## 2. Levantar sitio + base

```powershell
docker compose build
docker compose up -d
docker compose ps
```

Servicios:

- sitio: `http://localhost:8080`
- sitio alternativo: `http://localhost:4321`
- API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## 3. Que queda en PostgreSQL

La base guarda:

- centros e integrantes CE
- muro del recuerdo
- fotos del muro
- cuentas UTEM
- configuraciones del sitio
- pizarra compartida de `Crea`

## 4. Que sigue en archivos

Estos datos aun no viven en PostgreSQL:

- PDFs de presentaciones: `backend/data/uploads/presentations`
- imagenes de integrantes CE: `backend/data/uploads/centers`
- proyectos enviados: `backend/data/project_submissions`
- credenciales admin: `backend/.env`

## 5. Backup y restore

Este repo privado ya incluye:

```text
backups/ce-iccd.sql
```

Backup nuevo:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

Restore:

```powershell
.\scripts\db-restore.ps1 -InputPath backups\ce-iccd.sql
```

## 6. Traspaso a otra persona

Para conservar todo, comparte:

- acceso al repo privado
- la instruccion de correr `.\scripts\init-shared-deploy.ps1`

El clone ya lleva:

- `backups/ce-iccd.sql`
- `backend/data/uploads`
- `backend/data/project_submissions`

## 7. Guia paso a paso

Guia completa para entrar a PostgreSQL, revisar tablas, sacar backup y compartir el proyecto:

[README_BASE_DE_DATOS.md](/C:/Users/avega/Desktop/BOT_GABRIELITO/landing_page_movile/README_BASE_DE_DATOS.md)
