# Arquitectura de ALEJANDRÍA

## Vista general

```
 Usuario (internet, correo Alicorp; no necesita usuario en GCP)
   │ 1) correo → normalizado → política → enlace de acceso (Identity Platform)
   │ 2) cookie de sesión httpOnly (se borra al cerrar el navegador; máximo 12 h)
   ▼
┌──────── Cloud Run: us-<env>-run-portal-webapps  (SA <env>-gsa-portal-runtime) ─────────┐
│ FastAPI: sesión · política · autorización · límites · HTML (gzip + caché) · CSP ·     │
│          auditoría · archivos de la SPA                                               │
│ React:   ingreso · sin herramientas · sidebar · Herramientas · visor (iframe + marca) │
└──────┬─────────────────────────────────────────────────────────┬─────────────────────┘
       │ lectura                                                 │ logs JSON (stdout)
       ▼                                                         ▼
 gs://us-<env>-stg-ml-webapps/<qa|prd>/                 Cloud Logging ──sink──► BigQuery
   ├── _catalogo/<dominio>/<app>.json    ← CI (deployer)          monitoreo__portal_webapps
   └── <dominio>/<app>/index.html        ← pipeline o CI
       <dominio>/<app>/historico/…       ← pipeline (el portal no lo lee)
 gs://us-prod-stg-ml-webapps/prd_bitacora/  ← bitácora de pases
```

## Autenticación

1. El frontend valida el correo contra la política (mensaje inmediato) y pide a Identity
   Platform el enlace de acceso (`sendSignInLinkToEmail`).
2. Al abrir el enlace, el frontend obtiene un ID token y lo envía a `POST /api/sesion`.
3. El backend verifica el token, vuelve a aplicar la política y crea una **cookie de sesión
   de Firebase** (`alejandria_sesion`): `httpOnly`, `Secure`, `SameSite=Strict`, sin
   `Max-Age` (se borra al cerrar el navegador) y con vencimiento de 12 h en el servidor.
4. El frontend no guarda tokens: la sesión de Firebase en el navegador es en memoria y se
   cierra apenas se crea la cookie.

## Autorización y catálogo

- Cada app publicada tiene una entrada `_catalogo/<dominio>/<app>.json` con la tarjeta, la
  lista de correos del ambiente, las capacidades, la marca de agua y la huella.
- El backend lista el catálogo y lo reutiliza en memoria `catalogo.ttl_segundos`.
- Toda ruta con sesión filtra por el correo de la cookie. Una app sin permiso responde 403 y
  se audita como `acceso_denegado`.

## Visor

1. El frontend pide `GET /api/apps/<dominio>/<app>/contenido` con el encabezado
   `X-Alejandria-Visor: 1`. Sin ese encabezado, el backend responde 400: abrir la URL
   directamente en el navegador no muestra el HTML.
2. El backend lee `index.html` del bucket, lo guarda en memoria por **generación** del
   objeto (una nueva escritura del pipeline se ve en la siguiente apertura) y lo envía
   comprimido con gzip, `Cache-Control: no-store` y `Content-Security-Policy: sandbox`.
3. El frontend crea un Blob URL y lo carga en un `<iframe sandbox>`:
   - siempre `allow-scripts`;
   - según las capacidades: `allow-downloads`, `allow-popups`, `allow-modals`, `allow-forms`;
   - nunca `allow-same-origin`, `allow-top-navigation*` ni `allow-popups-to-escape-sandbox`.
4. El iframe hereda la CSP de la página del portal, construida desde `csp_allowlist.yaml`:
   los recursos externos solo pueden venir de esos dominios.
5. La marca de agua es una capa del portal sobre el iframe, con el correo del usuario y la
   fecha. No intercepta clics.

## Protección

- Límite de solicitudes en memoria: por correo en rutas con sesión y por IP en rutas
  públicas. La IP se toma de `X-Forwarded-For` en la posición `ip_indice_desde_final`.
- Encabezados en todas las respuestas: CSP, `X-Content-Type-Options`, `Referrer-Policy`,
  HSTS y `X-Frame-Options: DENY`.
- `max_instances` como techo de gasto; Dependabot y Trivy en la imagen.

## Auditoría

Cada evento es una línea JSON en stdout con `tipo_registro="auditoria"`. Un sink de Cloud
Logging los envía a `monitoreo__portal_webapps`.

| Evento | Cuándo |
|---|---|
| `enlace_solicitado` / `enlace_rechazado_politica` | El usuario pide un enlace |
| `login_ok` / `login_rechazado` / `sin_apps` | Se crea (o no) la sesión |
| `app_abierta` / `latido` / `app_cerrada` | Uso del visor (latido cada `latido_segundos` con la pestaña visible) |
| `acceso_denegado` / `limite_excedido` / `sesion_expirada` | Rechazos del backend |

## Unidades desplegables y huella

| | Portal | App |
|---|---|---|
| Artefacto | Imagen Docker (`portal-webapps`) | Entrada de catálogo (+ `index.html` si es herramienta) |
| Identidad de lo validado | Tag `<version>-<sha>` + `deploy/qa` exitoso + mismo código | Huella de contenido |
| Promoción a PRD | Copia por digest (sin rebuild) | Publicación desde la rama release |

La **huella** de una app es el SHA-256 del `app.yaml` sin `acceso` ni `version`
(serializado de forma canónica) más los bytes del `index.html`. Si solo cambian los
accesos, la huella no cambia: por eso esos cambios no necesitan un nuevo QA.

## Código

| Módulo (`portal/backend/src/alejandria/`) | Responsabilidad |
|---|---|
| `settings.py` | Variables de entorno + YAML de `portal/config/` |
| `email_policy.py` | Normalización y política de correos (también la usa CI) |
| `session.py` | Cookies de sesión de Firebase |
| `storage.py` · `catalog.py` · `content.py` | Lectura del bucket, catálogo con TTL y HTML con caché por generación |
| `authorization.py` | Apps visibles para un correo |
| `rate_limit.py` | Ventana fija por clave |
| `security_headers.py` | CSP del portal y encabezados comunes |
| `audit.py` | Eventos de auditoría |
| `routes.py` · `app.py` | API y archivos de la SPA |

| Script (`scripts/`) | Usado por |
|---|---|
| `detectar_unidad.py` · `validar_apps.py` · `solo_accesos.py` | `pr_checks`, `deploy_qa` |
| `publicar_app.py` · `desplegar_portal.py` · `leer_config.py` | `deploy_qa`, `deploy_prd` |
| `sincronizar_accesos_qa.py` | `sync_accesos_qa` |
| `pase_prd.py` · `verificar_version.py` · `huella.py` · `promover_imagen.py` | `deploy_prd` |
