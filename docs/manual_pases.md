# Manual de pases a producción

Aplica a las dos unidades desplegables: el **portal** y cada **app**
(`apps/<dominio>/<app>`). Todo pase deja evidencia: el issue de solicitud, los controles
C1–C4 y un JSON en la bitácora `gs://us-prod-stg-ml-webapps/prd_bitacora/`.

## 1. Antes del pase

| | Portal | App |
|---|---|---|
| Versión | Subir `portal.version` en `portal/config/portal.yaml` | Subir `version` en el `app.yaml` |
| QA | `Deploy to QA` exitoso sobre el último commit de la PR | Ídem, salvo en cambios solo de accesos |
| Merge | PR aprobada y mergeada a `main` | Ídem |
| Rama release (desde `main`) | `release_portal_<version>` | `release_<dominio>_<app>_<version>` |

Ejemplo: `release_supply_stock_seguridad_indirectos_2026-10-01-01`.

La rama release se crea desde la interfaz de GitHub (selector de ramas → escribir el nombre
→ "Create branch … from main"). El ruleset de `release_*` la vuelve inmutable.

## 2. Solicitud

**Issues → New issue → Pase a producción**, con:

| Campo | Valor |
|---|---|
| Unidad a desplegar | `portal` o `apps/<dominio>/<app>` |
| Versión | La declarada en `portal.yaml` / `app.yaml` |
| Tipo de cambio | Inicial · Incremental · Rollback |
| Área de negocio impactada | Texto libre |
| Detalle del cambio | Qué cambia para el usuario (indicar si es solo de accesos) |

## 3. Ejecución

Un usuario de `PRD_APPROVERS` ejecuta **Actions → Deploy to PRD** con el número del issue.

| Control | Qué valida |
|---|---|
| C1 | Quien ejecuta está en `PRD_APPROVERS` |
| C2 | El issue existe, está abierto, se creó con el formulario y sus campos son válidos; existe la rama release |
| C3 | La versión del issue es la declarada en el código de la rama release |
| C4 portal | Hay una imagen `<version>-<sha>` en el Artifact Registry de QA con `deploy/qa` exitoso y con el mismo código del release (`portal/`, `pyproject.toml`, `uv.lock`, `.dockerignore`) |
| C4 app | La huella de la app en la rama release es la publicada en el catálogo de QA |

Si todo pasa:
- **Portal:** la imagen validada se copia por digest al Artifact Registry de PRD (sin
  reconstruir), se despliega en `us-prod-run-portal-webapps` y se verifica `/api/salud`.
- **App:** se publica en `prd/` desde la rama release: la entrada de catálogo y, si es
  herramienta, el `index.html`.

Al final, **siempre** (también si un control rechaza o algo falla), se escribe la
bitácora, se comenta el resultado en el issue y, si fue exitoso, se cierra.

## 4. Cambios solo de accesos

Un cambio que solo toca `acceso` (y opcionalmente `version`) del `app.yaml` no cambia la
huella de la app:
1. No necesita `Deploy to QA`: `pr_checks` lo informa en el log.
2. Al mergear, `Sync accesos QA` actualiza la lista de QA en el catálogo.
3. Para PRD se sigue el flujo normal (rama release + issue). C4 pasa porque la huella es la
   misma que la de QA, y la bitácora registra los correos agregados y quitados.

## 5. Rollback

No hay rollback automático. Volver a una versión anterior es un pase normal:
1. Issue "Pase a producción" con **Tipo de cambio: Rollback**, la versión anterior y su
   rama release existente (no se crea una nueva).
2. `Deploy to PRD` con ese issue.
   - Portal: C4 encuentra la imagen de esa versión en QA y la promueve de nuevo.
   - App: C4 acepta la huella de la release anterior si tuvo un pase exitoso registrado en
     la bitácora, aunque QA ya tenga una versión más nueva.
3. Corregir el problema en `main` y hacer luego un pase con una versión nueva.

Una app de pipeline se corrige desde el repo de ML (su `index.html` lo escribe el
pipeline). El rollback de su `app.yaml` solo afecta la tarjeta, los accesos y el visor.

## 6. Bitácora

`gs://us-prod-stg-ml-webapps/prd_bitacora/{_portal | <dominio>/<app>}/<AAAAMMDD-HHMMSS>_<version>_<resultado>.json`

Cada JSON registra:
- la solicitud;
- el release (versión anterior y actual, rama y SHA);
- la evidencia de QA;
- el artefacto (imagen y digest, o huella y objetos publicados);
- el diff de accesos;
- quién ejecutó y cuándo;
- las PRs incluidas con sus aprobaciones;
- el resultado de C1–C4.

`<resultado>` es `exitoso`, `rechazado`, `fallido` o `cancelado`.
