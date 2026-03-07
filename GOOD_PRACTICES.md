# Buenas practicas del proyecto

## Arquitectura

- Separar responsabilidades: UI en `frontend/` y logica de negocio/API en `backend/`.
- Evitar dependencias cruzadas directas entre modulos.
- Mantener endpoints y contratos (payloads) versionados o documentados.

## Frontend

- No hardcodear URLs de servicios: usar variables `PUBLIC_*`.
- Componentes pequenos y reutilizables.
- Evitar logica compleja inline en paginas; extraer a utilidades cuando crezca.
- Mantener assets servidos por `public/` y codigo por `src/`.

## Backend

- Usar `default_factory` en Pydantic para listas/dicts mutables.
- Configurar modelos, URLs y CORS por variables de entorno.
- Resolver rutas de datos con `Path(__file__)` para evitar dependencias del directorio de ejecucion.
- Devolver mensajes de error controlados y loguear errores del servidor.

## Calidad

- Ejecutar build/check antes de merge:
  - Frontend: `npm run build`
  - Backend: correr API y probar `/health` + flujo `/chat`
- Mantener README de cada modulo actualizado al cambiar comandos o estructura.

## Git

- Commits pequenos y descriptivos.
- No subir secretos (`.env` real, tokens, claves).
- Ignorar artefactos (`node_modules`, `.venv`, `__pycache__`, `dist`, `.astro`).
