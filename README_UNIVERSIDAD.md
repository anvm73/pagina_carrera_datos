# Guia Para Computador De La Universidad

Esta es la ruta recomendada para dejar la pagina corriendo en un computador Windows dedicado de la universidad, sin depender de Docker.

## Requisitos

- Windows con acceso a la red universitaria.
- Git, Node.js 18+ y npm 9+.
- Python 3.11 o 3.12 recomendado.
- Ollama solo si se quiere usar el chatbot. La pagina, el panel admin y la base funcionan aunque Ollama no este corriendo.

## Primer Arranque

Desde la raiz del proyecto:

```powershell
.\scripts\init-local-university.ps1
.\arranque.bat
```

El script crea estos archivos locales:

- `backend/.env`
- `frontend/.env`

Ambos estan ignorados por Git porque contienen claves locales.

## URLs

`arranque.bat` imprime las URLs al iniciar. Normalmente quedan asi:

- Frontend local: `http://localhost:4321`
- Backend local: `http://localhost:8000`
- Frontend red: `http://IP_DEL_PC:4321`
- Backend red: `http://IP_DEL_PC:8000`

Para fijar manualmente la IP o dominio de la universidad:

```powershell
.\scripts\init-local-university.ps1 -PublicHost "IP_O_DOMINIO"
```

Despues vuelve a correr:

```bat
arranque.bat
```

## Cuenta Admin

La cuenta admin queda en `backend/.env`:

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

Si quieres definir una clave manual:

```powershell
.\scripts\init-local-university.ps1 -AdminPassword "TuClaveSegura"
```

No subas `backend/.env` ni `frontend/.env` al repo.

## Base De Datos

El camino principal usa SQLite:

- `backend/data/ce_iccd.db`

Esa base viaja en el repo e incluye contenido editable, cuentas, muro, presentaciones, integrantes y pizarra de `Crea`.

Tambien queda disponible el respaldo PostgreSQL opcional:

- `backups/ce-iccd.sql`

Usalo solo si deciden desplegar con Docker/PostgreSQL.

## Comprobaciones

Backend:

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

Base/pizarra:

```powershell
Invoke-WebRequest http://localhost:8000/crea/board -UseBasicParsing
```

Frontend:

```text
http://localhost:4321
```

Si el health check muestra `chatbot: unavailable`, falta iniciar Ollama o descargar los modelos configurados. Eso no impide usar el resto de la pagina.
