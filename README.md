# ALEJANDRÍA · Herramientas analíticas

Repositorio centralizado de las herramientas interactivas de analítica avanzada de Alicorp.
Cada usuario de negocio entra con su correo corporativo y ve **solo** las herramientas
habilitadas para él.

- **Usuarios:** entran con un enlace que llega a su correo (Identity Platform). No usan
  contraseñas ni necesitan una cuenta en GCP.
- **Apps:** HTML construidos por Data Science. Pueden ser de dos tipos:
  - `pipeline`: un pipeline del repo de ML inyecta datos al HTML y lo escribe en el bucket.
  - `herramienta`: el HTML vive en este repo y el usuario carga su propio Excel/CSV.
- **Portal:** un servicio de Cloud Run por ambiente (FastAPI + React). Muestra cada HTML en
  un iframe aislado, con marca de agua, y **nunca modifica el HTML**.

| | QA | PRD |
|---|---|---|
| Proyecto | `acpe-qa-uc-ml` | `acpe-prod-uc-ml` |
| Cloud Run | `us-qa-run-portal-webapps` | `us-prod-run-portal-webapps` |
| Bucket | `us-qa-stg-ml-webapps` (carpeta `qa/`) | `us-prod-stg-ml-webapps` (carpeta `prd/`) |
| Auditoría | `monitoreo__portal_webapps` | `monitoreo__portal_webapps` |

## Estructura

```
├── apps/<dominio>/<app>/        una carpeta por app: app.yaml (+ index.html si es herramienta)
├── portal/
│   ├── config/                  parámetros del portal y de cada ambiente (YAML)
│   ├── backend/                 FastAPI (paquete alejandria) + tests
│   ├── frontend/                React + Vite + Tailwind + tests
│   └── Dockerfile               imagen única: build de React + backend
├── scripts/                     scripts de CI (validación, publicación, pase a PRD) + tests
├── docs/                        guía del DS, manual de pases y arquitectura
└── .github/                     workflows, plantillas de PR e issue, CODEOWNERS, Dependabot
```

## Configuración (`portal/config/`)

| Archivo | Qué define |
|---|---|
| `portal.yaml` | Nombre, subtítulo, texto de contacto, **versión del portal** y labels |
| `env_qa.yaml` / `env_prd.yaml` | Proyecto, Cloud Run (instancias, CPU, memoria), imagen, bucket, sesión, auditoría, límites |
| `politica_correos.yaml` | Dominios permitidos y prefijos excluidos (por ejemplo `ext_`) |
| `csp_allowlist.yaml` | Dominios externos que pueden usar los HTML (mapas y CDN) |
| `iconos_permitidos.yaml` | Íconos disponibles para las tarjetas (mismo listado que `frontend/src/config/icons.ts`) |

## Flujos

Hay dos **unidades desplegables**: el `portal` y cada app (`apps/<dominio>/<app>`). Una PR
toca como máximo una.

| Paso | Portal | App |
|---|---|---|
| PR a `main` | `pr_checks`: lint, tests, build y escaneo de la imagen | `pr_checks`: contrato del `app.yaml`, tamaño del HTML |
| QA (`Deploy to QA`, manual con la rama) | Build → Artifact Registry → Cloud Run QA | Catálogo (+ `index.html`) → bucket QA |
| Solo accesos | — | No requiere QA: al mergear, `Sync accesos QA` actualiza QA |
| PRD (`Deploy to PRD`, manual con el issue) | C1–C4 → promoción de la imagen por digest → Cloud Run PRD | C1–C4 → catálogo (+ `index.html`) → bucket PRD |
| Evidencia | Bitácora en `gs://us-prod-stg-ml-webapps/prd_bitacora/` | Ídem, con el diff de accesos |

- DS: cómo publicar una app en [`docs/guia_data_scientist.md`](docs/guia_data_scientist.md).
- LT / MLE: pases, accesos y rollback en [`docs/manual_pases.md`](docs/manual_pases.md).
- Diseño técnico en [`docs/arquitectura.md`](docs/arquitectura.md).

## Desarrollo local

Requisitos: Python 3.12 con [uv](https://docs.astral.sh/uv/), Node 22 y pnpm 10.

```bash
# Python (backend + scripts) y hooks
uv sync --group dev
uv run pre-commit install
uv run ruff check . && uv run ruff format --check .
uv run pytest

# Frontend
cd portal/frontend
pnpm install
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

Para levantar el portal contra el ambiente de QA (necesita credenciales de GCP con lectura
del bucket de QA y el rol de Identity Platform de la cuenta runtime):

```bash
# Terminal 1: backend en :8080 (sirve la API; el frontend lo toma de FRONTEND_DIST)
cd portal/frontend && pnpm build && cd ../..
APP_ENV=qa GCP_PROJECT_ID=acpe-qa-uc-ml \
IDENTITY_API_KEY=<api key web de QA> IDENTITY_AUTH_DOMAIN=<auth domain de QA> \
CONFIG_DIR=portal/config FRONTEND_DIST=portal/frontend/dist \
uv run uvicorn alejandria.app:create_app_from_env --factory --port 8080

# Terminal 2 (opcional): frontend con recarga en caliente en :5173 (proxy de /api a :8080)
cd portal/frontend && pnpm dev
```

`localhost` debe estar en los dominios autorizados de Identity Platform de QA. La cookie de
sesión es `Secure`: los navegadores la aceptan en `http://localhost`.
