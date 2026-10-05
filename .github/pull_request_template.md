## Descripción

<!-- Qué cambia y por qué -->

## Tipo de cambio

- [ ] App nueva (`apps/<dominio>/<app>/`)
- [ ] Modificación de una app existente (HTML o `app.yaml`)
- [ ] Solo accesos (`acceso` y/o `version` del `app.yaml`)
- [ ] Portal (`portal/`, `pyproject.toml`, `uv.lock`)
- [ ] Tooling / CI / documentación (`scripts/`, `.github/`, `docs/`)

## Checklist

- [ ] La PR toca **solo una** unidad: `portal` o una carpeta `apps/<dominio>/<app>`
- [ ] **Ningún HTML contiene datos reales** (solo datos ficticios o de ejemplo)
- [ ] El HTML muestra de forma visible la fecha de actualización de sus datos
- [ ] Los tests y el lint pasan localmente (`uv run pytest`, `uv run ruff check .`)
- [ ] Se ejecutó `Deploy to QA` sobre el **último commit** de esta rama, ya actualizada con `main` (no aplica a cambios solo de accesos)
- [ ] Se actualizó la documentación si aplica
