# Frontend - Landing CE ICCD UTEM

Aplicacion Astro/Tailwind para la landing institucional y secciones del Centro de Estudiantes.

## Requisitos

- Node.js 18+
- npm 9+

## Instalacion y ejecucion

```bash
npm install
npm run dev
```

Comandos utiles:

```bash
npm run dev:host
npm run build
npm run preview
```

## Variables de entorno

Crear `.env` en `frontend/` usando `.env.example`:

```bash
PUBLIC_CHATBOT_API_URL=http://localhost:8000/chat
PUBLIC_PROJECTS_API_URL=http://localhost:8000
```

## Estructura

```text
frontend/
|-- public/        # Archivos estaticos servidos tal cual
|-- src/
|   |-- pages/     # Rutas Astro
|   |-- components/
|   |-- layouts/
|   `-- styles/
`-- resources/     # Fuentes de material (ej: PDFs originales)
```

## Buenas practicas del frontend

- Mantener textos y contenido por pagina en `src/pages`.
- Evitar hardcodear URLs backend en componentes.
- Mantener consistencia visual usando tokens/clases existentes.
- Si agregas rutas nuevas, actualiza `src/layouts/MainLayout.astro`.

## Rutas relevantes

- `/login` para acceso de administrador
- `/admin` para gestionar proyectos, centros, presentaciones y muro del recuerdo
- `/muro-recuerdo` para la nueva seccion publica de titulados
