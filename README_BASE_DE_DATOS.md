# Base de Datos y Traspaso

Esta guia explica:

- como levantar PostgreSQL
- como entrar a la base
- como ver lo que hay guardado
- como sacar un backup
- como restaurarlo en otra maquina
- que cosas viajan en la base y cuales no

## 1. Levantar el proyecto con Docker

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

## 2. Entrar a PostgreSQL

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

## 3. Que queda guardado en PostgreSQL

La base guarda:

- centros CE e integrantes
- muro del recuerdo
- fotos del muro del recuerdo
- cuentas UTEM
- texto introductorio del muro
- pizarra compartida de `Crea`

## 4. Que NO queda guardado en PostgreSQL

Estas cosas siguen como archivos en disco:

- PDFs de presentaciones: `backend/data/uploads/presentations`
- imagenes de integrantes CE: `backend/data/uploads/centers`
- proyectos enviados por estudiantes: `backend/data/project_submissions`

Y ademas:

- la cuenta admin no vive en la base
- la cuenta admin vive en `backend/.env`

## 5. Crear un backup de la base

La forma mas simple es usar el script:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

Si no existe la carpeta `backups`, puedes crearla antes:

```powershell
New-Item -ItemType Directory -Force backups
```

Eso genera un archivo `.sql` con todo lo que hay en PostgreSQL, incluyendo la pizarra compartida de `Crea`.

## 6. Restaurar la base en otra maquina

En la otra maquina:

1. Clona el repo.
2. Crea `backend/.env` a partir de `backend/.env.example`.
3. Levanta los contenedores.
4. Restaura el backup.

Comandos:

```powershell
copy backend\.env.example backend\.env
docker compose build
docker compose up -d
.\scripts\db-restore.ps1 -InputPath backups\ce-iccd.sql
```

## 7. Que hay que compartirle a otra persona

Para que otra persona levante el sitio con la misma informacion actual, debes entregarle:

- el repo
- un backup SQL de PostgreSQL
- `backend/.env`
- `backend/data/uploads`
- `backend/data/project_submissions` si quieres conservar proyectos enviados

En resumen:

- `Git` lleva el codigo
- `backup.sql` lleva la base
- `backend/data/uploads` lleva PDFs e imagenes que aun viven en disco
- `backend/data/project_submissions` lleva los proyectos de alumnos
- `backend/.env` lleva secretos y credenciales admin

## 8. Comprobaciones utiles

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

## 9. Flujo recomendado para entregar el proyecto

1. Ejecuta un backup:

```powershell
.\scripts\db-backup.ps1 -OutputPath backups\ce-iccd.sql
```

2. Comprime o copia:

- el repo
- `backups\ce-iccd.sql`
- `backend/data/uploads`
- `backend/data/project_submissions`
- `backend/.env`

3. La otra persona:

- clona el repo
- deja su `backend/.env`
- levanta `docker compose up -d`
- restaura el backup
- copia las carpetas de archivos

Con eso la otra persona queda con la pagina, la base y el contenido listo para desplegar.
