# Base de Datos y Traspaso

Esta guia explica:

- como levantar PostgreSQL
- como generar `backend/.env` de forma segura
- como entrar a la base
- como ver lo que hay guardado
- como sacar un backup
- como restaurarlo en otra maquina
- que cosas viajan en la base y cuales no

## 1. Generar backend/.env

El repo no incluye `backend/.env` por seguridad, incluso siendo privado.

Generalo automaticamente con:

```powershell
.\scripts\init-shared-deploy.ps1
```

Ese script:

- crea `backend/.env`
- genera `POSTGRES_PASSWORD`
- genera `ADMIN_TOKEN_SECRET`
- genera `STUDENT_TOKEN_SECRET`
- genera una clave admin nueva

Si quieres definir una clave admin manualmente:

```powershell
.\scripts\init-shared-deploy.ps1 -AdminPassword "TuClaveSegura123"
```

## 2. Levantar el proyecto con Docker

Desde la raiz del proyecto:

```powershell
docker compose build
docker compose up -d
docker compose ps
```

Deberias ver estos servicios arriba:

- `postgres`
- `backend`
- `frontend`

Puertos:

- sitio: `http://localhost:8080`
- sitio alternativo: `http://localhost:4321`
- API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## 3. Entrar a PostgreSQL

Si usas los valores por defecto de este proyecto:

```powershell
docker compose exec postgres psql -U ce_iccd -d ce_iccd
```

Si cambiaste `POSTGRES_USER` o `POSTGRES_DB` en `backend/.env`, reemplaza esos valores en el comando.

Cuando entres a `psql`, puedes usar:

```sql
\dt
select count(*) from centers;
select count(*) from alumni_profiles;
select count(*) from presentations;
select count(*) from student_accounts;
select count(*) from shared_board_states;
\q
```

## 4. Que queda guardado en PostgreSQL

La base guarda:

- centros CE e integrantes
- muro del recuerdo
- fotos del muro del recuerdo
- cuentas UTEM
- texto introductorio del muro
- pizarra compartida de `Crea`

## 5. Que NO queda guardado en PostgreSQL

Estas cosas siguen como archivos en disco:

- PDFs de presentaciones: `backend/data/uploads/presentations`
- imagenes de integrantes CE: `backend/data/uploads/centers`
- proyectos enviados por estudiantes: `backend/data/project_submissions`

Y ademas:

- la cuenta admin no vive en la base
- la cuenta admin vive en `backend/.env`

## 6. Backup incluido en este repo

Este repo privado ya incluye un dump listo para restaurar:

- `backups\ce-iccd.sql`

Tambien puedes generar uno nuevo cuando quieras con:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

## 7. Restaurar la base en otra maquina

En la otra maquina solo hace falta:

1. Clonar el repo.
2. Generar `backend/.env`.
3. Levantar contenedores.
4. Restaurar `backups\ce-iccd.sql`.

Comandos:

```powershell
.\scripts\init-shared-deploy.ps1
docker compose build
docker compose up -d
.\scripts\db-restore.ps1 -InputPath backups\ce-iccd.sql
```

## 8. Crear un backup nuevo de la base

La forma mas simple es usar el script:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

Si no existe la carpeta `backups`, puedes crearla antes:

```powershell
New-Item -ItemType Directory -Force backups
```

Eso genera un archivo `.sql` con todo lo que hay en PostgreSQL, incluyendo la pizarra compartida de `Crea`.

## 9. Que hay que compartirle a otra persona

Si usas este repo privado, ya viajan dentro del clone:

- `backups\ce-iccd.sql`
- `backend/data/uploads`
- `backend/data/project_submissions`

Entonces ya no necesitas mandar esas carpetas por separado.

Solo debes compartir:

- acceso al repo privado
- la instruccion de correr `.\scripts\init-shared-deploy.ps1`

En resumen:

- `Git` lleva el codigo
- `backups\ce-iccd.sql` lleva la base versionada
- `backend/data/uploads` y `backend/data/project_submissions` ya vienen en el repo
- `backend/.env` se genera localmente en cada despliegue

## 10. Comprobaciones utiles

Ver salud del backend:

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

Ver la pizarra compartida:

```powershell
Invoke-WebRequest http://localhost:8000/crea/board -UseBasicParsing
```

Ver cuantas filas tiene la pizarra en PostgreSQL:

```powershell
docker compose exec postgres psql -U ce_iccd -d ce_iccd -c "select key, updated_by, updated_at from shared_board_states;"
```

## 11. Flujo recomendado para entregar el proyecto

1. Haz `git pull` del repo privado.
2. Genera `backend/.env`:

```powershell
.\scripts\init-shared-deploy.ps1
```

3. Levanta Docker y restaura la base:

```powershell
docker compose build
docker compose up -d
.\scripts\db-restore.ps1 -InputPath backups\ce-iccd.sql
```

Con eso la otra persona queda con la pagina, la base y el contenido listo para desplegar desde este mismo repo privado.
