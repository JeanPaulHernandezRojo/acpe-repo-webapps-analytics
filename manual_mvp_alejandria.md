# ALEJANDRÍA · Manual del MVP en un proyecto de GCP propio

> **Objetivo:** validar de punta a punta, en un proyecto de GCP nuevo y fuera de los ambientes de Alicorp, que:
> 1. un workflow de GitHub Actions despliega el portal y una herramienta HTML en QA;
> 2. el pase a PRD (rama release + issue + workflow) despliega ambos en PRD;
> 3. puedes ingresar con tu correo, ver la tarjeta de tu HTML, abrirlo e interactuar con él.
>
> Todo se hace desde la consola de GCP, GitHub (web) y GitHub Desktop. No se usa la línea de comandos.
>
> Tiempo estimado: 2 a 3 horas la primera vez.

---

## 0. Antes de empezar

### 0.1 Qué incluye el MVP y qué queda fuera

| Incluido | Fuera del MVP (va en el manual de Alicorp) |
|---|---|
| Un proyecto de GCP con QA y PRD dentro (dos Cloud Run y un bucket con carpetas `qa/` y `prd/`) | Proyectos separados para QA y PRD |
| Login con enlace al correo (Identity Platform) | CODEOWNERS, rulesets de ramas y aprobaciones obligatorias |
| Workflows `Deploy to QA`, `Deploy to PRD` y `Sync accesos QA` | Bitácora de pases en el bucket (la evidencia queda solo en el issue) |
| Controles del pase C1–C4 | Sink de auditoría a BigQuery (los eventos sí quedan en Cloud Logging) |
| Una herramienta HTML propia (`tipo: herramienta`) | Conexión con el repo de ML pipelines, Dependabot, permisos por bucket y restricción de la API key |

`pr_checks` corre igual en cada PR, pero en el MVP **no bloquea** el merge (no hay rulesets). Úsalo como información.

### 0.2 Qué necesitas

- Una cuenta de Google con una tarjeta para la facturación. El MVP cuesta menos de US$1 al mes (§9).
- Una cuenta de GitHub.
- [GitHub Desktop](https://desktop.github.com/) instalado y con tu cuenta iniciada.
- Un editor de texto, por ejemplo VS Code.
- El zip `alejandria_codigo.zip` (la versión que acompaña este manual).
- Tu HTML. Debe ser **un solo archivo** con estilos, scripts y datos dentro (ver §4.3).

### 0.3 Hoja de datos

Completa esta tabla a medida que avances. Los pasos se refieren a estos valores entre `< >`.

| Dato | Ejemplo | Tu valor | Dónde lo obtienes |
|---|---|---|---|
| `<PROJECT_ID>` | `alejandria-mvp-4821` | | §1.1 |
| `<PROJECT_NUMBER>` | `820424024162` | | §1.1 |
| `<USUARIO_GH>` | `jhernandezr` | | Tu usuario de GitHub |
| `<REPO>` | `alejandria-mvp` | | §2.1 |
| `<TU_CORREO>` | `tu.nombre@gmail.com` | | El correo con el que ingresarás |
| `<API_KEY>` | `AIzaSy…` | | §1.8 |
| `<AUTH_DOMAIN>` | `alejandria-mvp-4821.firebaseapp.com` | | §1.8 |
| `<URL_QA>` | `https://mvp-qa-run-portal-webapps-…run.app` | | §3.4 |
| `<URL_PRD>` | `https://mvp-prd-run-portal-webapps-…run.app` | | §6.4 |

### 0.4 Nombres de los recursos

| Recurso | Nombre |
|---|---|
| Repositorio de Artifact Registry | `mvp-arg-portal` |
| Bucket | `<PROJECT_ID>-webapps` |
| Cuenta de servicio del portal (runtime) | `mvp-gsa-portal-runtime` |
| Cuenta de servicio de GitHub Actions (deployer) | `mvp-gsa-portal-deployer` |
| Grupo y proveedor de Workload Identity | `github-pool` / `github-provider` |
| Cloud Run QA / PRD (los crea el workflow) | `mvp-qa-run-portal-webapps` / `mvp-prd-run-portal-webapps` |
| Región | `us-east1` |

> Los menús se nombran como aparecen en la consola en español. Entre paréntesis va el nombre en inglés cuando es distinto.

---

## 1. GCP

### 1.1 Crear el proyecto

1. Entra a https://console.cloud.google.com con tu cuenta personal.
2. En la barra superior, haz clic en el **selector de proyectos** y luego en **Proyecto nuevo** (New project).
3. Configura:
   - **Nombre del proyecto:** `alejandria-mvp`
   - **Ubicación:** `Sin organización` (No organization)
4. Haz clic en **Crear**.
5. Selecciona el proyecto nuevo en el selector.
6. Abre **Menú ☰ → Descripción general de Cloud → Panel** (Dashboard). En la tarjeta **Información del proyecto**, anota el **ID del proyecto** (`<PROJECT_ID>`) y el **Número del proyecto** (`<PROJECT_NUMBER>`).

> Créalo **sin organización**. Si el proyecto quedara dentro de una organización con la política "uso compartido restringido al dominio", el portal no podría abrirse desde internet.

### 1.2 Vincular la facturación

1. Abre **Menú ☰ → Facturación** (Billing).
2. Si aparece "Este proyecto no tiene una cuenta de facturación", haz clic en **Vincular una cuenta de facturación**.
3. Elige tu cuenta (o créala con **Crear cuenta de facturación** y tu tarjeta) y haz clic en **Establecer cuenta**.

### 1.3 Habilitar las APIs

1. Abre **Menú ☰ → APIs y servicios → Biblioteca** (Library).
2. Para cada API de la tabla: búscala, ábrela y haz clic en **Habilitar** (Enable).

| API | Para qué |
|---|---|
| Cloud Run Admin API | Desplegar el portal |
| Artifact Registry API | Guardar la imagen del portal |
| Identity and Access Management (IAM) API | Cuentas de servicio y Workload Identity |
| IAM Service Account Credentials API | Que GitHub Actions actúe como la cuenta deployer |
| Security Token Service API | Intercambio de tokens de GitHub por tokens de GCP |
| Cloud Storage API | Bucket (suele venir habilitada; verifícala) |

La Identity Toolkit API se habilita sola en §1.8.

### 1.4 Crear el repositorio de imágenes (Artifact Registry)

1. Abre **Menú ☰ → Artifact Registry → Repositorios**.
2. Haz clic en **＋ Crear repositorio**.
3. Configura:
   - **Nombre:** `mvp-arg-portal`
   - **Formato:** Docker
   - **Modo:** Estándar
   - **Tipo de ubicación:** Región → `us-east1`
   - Deja el resto como viene.
4. Haz clic en **Crear**.

### 1.5 Crear el bucket

1. Abre **Menú ☰ → Cloud Storage → Buckets** y haz clic en **＋ Crear**.
2. **Nombre:** `<PROJECT_ID>-webapps`. Clic en **Continuar**.
3. **Ubicación:** Región → `us-east1`. Clic en **Continuar**.
4. **Clase de almacenamiento:** Standard. Clic en **Continuar**.
5. **Control de acceso:**
   - marca **Aplicar la prevención del acceso público a este bucket**;
   - elige **Uniforme**.
6. **Protección de datos:** deja los valores por defecto.
7. Haz clic en **Crear**. Si aparece el aviso de prevención de acceso público, haz clic en **Confirmar**.

No crees carpetas: los workflows crean `qa/` y `prd/` al publicar.

### 1.6 Crear las cuentas de servicio con sus roles

En el MVP los roles se otorgan a nivel de proyecto (en Alicorp serán por bucket y por recurso).

**Cuenta runtime (la usa el Cloud Run):**

1. Abre **Menú ☰ → IAM y administración → Cuentas de servicio** y haz clic en **＋ Crear cuenta de servicio**.
2. **Paso 1:**
   - **Nombre:** `mvp-gsa-portal-runtime`
   - **Descripción:** `Identidad del portal ALEJANDRÍA (MVP)`
   - Clic en **Crear y continuar**.
3. **Paso 2 (Permisos):** agrega estos roles, cada uno con **＋ Agregar otro rol**:
   - `Administrador de Firebase Authentication` (Firebase Authentication Admin). Permite crear la cookie de sesión.
   - `Visualizador de objetos de Storage` (Storage Object Viewer). Permite leer el catálogo y los HTML.
4. Haz clic en **Continuar** y luego en **Listo**.

**Cuenta deployer (la usa GitHub Actions):**

1. Haz clic en **＋ Crear cuenta de servicio**.
2. **Paso 1:**
   - **Nombre:** `mvp-gsa-portal-deployer`
   - **Descripción:** `GitHub Actions de ALEJANDRÍA (MVP)`
   - Clic en **Crear y continuar**.
3. **Paso 2:** agrega estos roles:

| Rol | Para qué |
|---|---|
| `Administrador de Cloud Run` (Cloud Run Admin) | Desplegar los servicios y abrirlos a internet |
| `Usuario de cuenta de servicio` (Service Account User) | Asignar la cuenta runtime al Cloud Run |
| `Escritor de Artifact Registry` (Artifact Registry Writer) | Subir, listar y promover la imagen |
| `Administrador de objetos de Storage` (Storage Object Admin) | Publicar el catálogo y los HTML |

4. Haz clic en **Continuar** y luego en **Listo**.
5. Anota el correo de esta cuenta: `mvp-gsa-portal-deployer@<PROJECT_ID>.iam.gserviceaccount.com`.

### 1.7 Workload Identity Federation (GitHub → GCP sin llaves)

**Crear el grupo y el proveedor:**

1. Abre **Menú ☰ → IAM y administración → Federación de identidades para cargas de trabajo** (Workload Identity Federation). Si te pide habilitar APIs, acepta.
2. Haz clic en **＋ Crear grupo** (Create pool).
3. **Paso 1, identidad:**
   - **Nombre:** `github-pool`
   - **Descripción:** `GitHub Actions`
   - Clic en **Continuar**.
4. **Paso 2, proveedor:**
   - **Seleccionar un proveedor:** OpenID Connect (OIDC)
   - **Nombre del proveedor:** `github-provider`
   - **ID del proveedor:** `github-provider` (se completa solo)
   - **Emisor (URL):** `https://token.actions.githubusercontent.com`
   - **Públicos:** Público predeterminado (Default audience)
   - Clic en **Continuar**.
5. **Paso 3, atributos del proveedor:** completa las asignaciones (con **＋ Agregar asignación** para cada fila nueva):

| Google | OIDC |
|---|---|
| `google.subject` | `assertion.sub` |
| `attribute.repository` | `assertion.repository` |
| `attribute.repository_owner` | `assertion.repository_owner` |

6. **Condiciones de atributos:** haz clic en **＋ Agregar condición** y escribe, con tu usuario y repo exactos:

   ```
   assertion.repository == '<USUARIO_GH>/<REPO>'
   ```

   Esto impide que otro repositorio de GitHub use tu proyecto. Respeta mayúsculas y minúsculas tal como aparecen en la URL del repo.
7. Haz clic en **Guardar**.

**Dar acceso a la cuenta deployer:**

1. En la página del grupo `github-pool`, haz clic en **＋ Otorgar acceso** (Grant access).
2. Elige **Otorgar acceso mediante la suplantación de identidad de la cuenta de servicio** (Grant access using service account impersonation).
3. **Cuenta de servicio:** `mvp-gsa-portal-deployer`.
4. **Seleccionar principales:**
   - **Nombre del atributo:** `repository`
   - **Valor del atributo:** `<USUARIO_GH>/<REPO>`
5. Haz clic en **Guardar**. Si aparece "Configura tu aplicación", ciérralo con **Descartar**.

**Anotar el nombre del proveedor:**

En la pestaña **Proveedores** del grupo, abre `github-provider` y arma este valor con tu número de proyecto:

```
projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

Lo usarás como `WIF_PROVIDER_QA` y `WIF_PROVIDER_PRD`. Debe coincidir con lo que muestra la consola después de `https://iam.googleapis.com/`.

### 1.8 Identity Platform (login con enlace al correo)

1. Busca **Identity Platform** en la barra de búsqueda de la consola y ábrelo.
2. Haz clic en **Habilitar Identity Platform** (Enable Identity Platform).
3. En **Proveedores** (Providers), haz clic en **＋ Agregar un proveedor** y elige **Correo electrónico/contraseña** (Email / Password).
4. Activa **Habilitado** y marca la opción de **acceso sin contraseña / vínculo de correo electrónico** (Passwordless / Email link).
5. Haz clic en **Guardar**.
6. En la misma página de **Proveedores**, haz clic en **Detalles de configuración de la aplicación** (Application setup details), a la derecha. Anota:
   - `apiKey` → `<API_KEY>`
   - `authDomain` → `<AUTH_DOMAIN>` (normalmente `<PROJECT_ID>.firebaseapp.com`)

La API key es pública por diseño: va al navegador. No es un secreto.

Los **dominios autorizados** se agregan después del primer despliegue (§3.5 y §6.4), porque ahí conocerás las URLs.

---

## 2. GitHub

### 2.1 Crear el repositorio

1. En https://github.com/new configura:
   - **Repository name:** `alejandria-mvp` (`<REPO>`)
   - **Visibility:** Private
   - No marques README, `.gitignore` ni licencia: el repo debe quedar vacío.
2. Haz clic en **Create repository**.

### 2.2 Subir el código con GitHub Desktop

1. En GitHub Desktop: **File → Clone repository → GitHub.com**. Elige `<REPO>`, define la carpeta local y haz clic en **Clone**.
2. Descomprime `alejandria_codigo.zip` en otra carpeta.
3. Muestra los archivos ocultos:
   - **Windows:** Explorador → Vista → Mostrar → Elementos ocultos.
   - **Mac:** en Finder, `Cmd + Shift + .`
4. Copia **el contenido** de la carpeta `acpe-repo-webapps-advanced-analytics/` (no la carpeta misma) dentro de la carpeta clonada. Verifica que se copiaron `.github/`, `.gitignore`, `.dockerignore` y `.pre-commit-config.yaml`.
5. Dentro de la carpeta clonada, **elimina**:
   - `.github/CODEOWNERS` (el team de Alicorp no existe en tu cuenta);
   - `.github/dependabot.yml` (evita PRs automáticas en el MVP).
6. En GitHub Desktop aparecerán los cambios:
   - en **Summary** escribe `Código base de ALEJANDRÍA`;
   - haz clic en **Commit to main**;
   - haz clic en **Publish branch** (o **Push origin**).
7. Verifica en github.com que el repo tiene `portal/`, `scripts/`, `.github/workflows/` (4 archivos) y `apps/`.

La carpeta `pr_acpe-repo-mlops-advanced-analytics/` del zip **no se usa** en el MVP.

### 2.3 Variables del repositorio

En el repo abre **Settings → Secrets and variables → Actions → pestaña Variables → New repository variable**. Crea estas 9 variables:

| Name | Value |
|---|---|
| `WIF_PROVIDER_QA` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_PROVIDER_PRD` | (el mismo valor) |
| `DEPLOYER_SA_QA` | `mvp-gsa-portal-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |
| `DEPLOYER_SA_PRD` | (el mismo valor) |
| `IDENTITY_API_KEY_QA` | `<API_KEY>` |
| `IDENTITY_API_KEY_PRD` | (el mismo valor) |
| `IDENTITY_AUTH_DOMAIN_QA` | `<AUTH_DOMAIN>` |
| `IDENTITY_AUTH_DOMAIN_PRD` | (el mismo valor) |
| `PRD_APPROVERS` | `<USUARIO_GH>` (exacto, sin `@`) |

**No crees `BITACORA_URI_PRD`.** Sin ella, el pase a PRD corre igual y la evidencia queda solo como comentario en el issue.

---

## 3. Portal en QA

### 3.1 Rama con la configuración del MVP

1. En GitHub Desktop: **Current branch → New branch**, con nombre `mvp-portal` (basada en `main`). Haz clic en **Create branch**.
2. Abre la carpeta en tu editor (**Repository → Open in Visual Studio Code**, o tu editor).

### 3.2 Editar 3 o 4 archivos

**a) `portal/config/env_qa.yaml`:** reemplaza todo el contenido por lo siguiente, cambiando `<PROJECT_ID>` (aparece 3 veces):

```yaml
# Parámetros del ambiente QA (MVP en un proyecto propio).

ambiente:
  nombre: "qa"
  proyecto: "<PROJECT_ID>"
  region: "us-east1"

cloud_run:
  servicio: "mvp-qa-run-portal-webapps"
  cuenta_runtime: "mvp-gsa-portal-runtime@<PROJECT_ID>.iam.gserviceaccount.com"
  # MVP: 0 instancias mínimas (sin costo en reposo; el primer ingreso tarda unos segundos).
  min_instances: 0
  max_instances: 1
  cpu: "1"
  memoria: "1Gi"
  concurrencia: 80

imagen:
  repositorio: "us-east1-docker.pkg.dev/<PROJECT_ID>/mvp-arg-portal"
  nombre: "portal-webapps"

bucket:
  nombre: "<PROJECT_ID>-webapps"
  prefijo: "qa"

sesion:
  horas: 12

auditoria:
  latido_segundos: 300

catalogo:
  ttl_segundos: 60

limites:
  usuario_por_minuto: 120
  ip_por_minuto: 30
  ip_indice_desde_final: 1
```

**b) `portal/config/env_prd.yaml`:** el mismo contenido con tres diferencias:
- en la primera línea, `ambiente PRD`;
- `nombre: "prd"`, `servicio: "mvp-prd-run-portal-webapps"` y `prefijo: "prd"`;
- todo lo demás (proyecto, cuenta, imagen y bucket) es idéntico: QA y PRD comparten el proyecto.

```yaml
# Parámetros del ambiente PRD (MVP en un proyecto propio).

ambiente:
  nombre: "prd"
  proyecto: "<PROJECT_ID>"
  region: "us-east1"

cloud_run:
  servicio: "mvp-prd-run-portal-webapps"
  cuenta_runtime: "mvp-gsa-portal-runtime@<PROJECT_ID>.iam.gserviceaccount.com"
  min_instances: 0
  max_instances: 1
  cpu: "1"
  memoria: "1Gi"
  concurrencia: 80

imagen:
  repositorio: "us-east1-docker.pkg.dev/<PROJECT_ID>/mvp-arg-portal"
  nombre: "portal-webapps"

bucket:
  nombre: "<PROJECT_ID>-webapps"
  prefijo: "prd"

sesion:
  horas: 12

auditoria:
  latido_segundos: 300

catalogo:
  ttl_segundos: 60

limites:
  usuario_por_minuto: 120
  ip_por_minuto: 30
  ip_indice_desde_final: 1
```

**c) `portal/config/portal.yaml`:** cambia la versión a la de hoy:

```yaml
  version: "2026-10-05-01"
```

**d) `portal/config/politica_correos.yaml`:** solo si `<TU_CORREO>` **no** es `@alicorp.com.pe`. Agrega su dominio:

```yaml
  dominios_permitidos:
    - "alicorp.com.pe"
    - "gmail.com"
```

> Recomendado: prueba con un correo personal. El enlace llega desde `noreply@<PROJECT_ID>.firebaseapp.com`, y el filtro del correo corporativo podría retenerlo.

### 3.3 Commit, publicar la rama y abrir la PR

1. En GitHub Desktop: en **Summary** escribe `Configuración del MVP`. Haz clic en **Commit to mvp-portal** y luego en **Publish branch**.
2. Haz clic en **Create Pull Request**. Se abre el navegador: haz clic en **Create pull request**.
3. `PR Checks` empieza a correr (5 a 10 min). Es informativo: si falla el escaneo Trivy de la imagen base, anótalo y continúa.

### 3.4 Desplegar el portal en QA

1. En el repo abre **Actions → Deploy to QA** (lista de la izquierda) y haz clic en **Run workflow**.
2. **Use workflow from:** déjalo en `main`.
3. **Rama a desplegar:** `mvp-portal`.
4. Haz clic en **Run workflow**. Demora unos 8 a 12 minutos: construye la imagen, la sube, despliega y hace el smoke test.
5. Cuando termine en verde, abre la PR: tendrás el comentario **✅ Deploy a QA: EXITOSO** con la **URL**. Anótala como `<URL_QA>`.

Si falla, revisa el step en rojo y la tabla de §8.

### 3.5 Autorizar el dominio de QA en Identity Platform

1. Abre **Identity Platform → Configuración** (Settings) **→ pestaña Seguridad** (Security).
2. En **Dominios autorizados** (Authorized domains), haz clic en **Agregar dominio**.
3. Pega el dominio de `<URL_QA>` **sin** `https://` ni `/` final (ejemplo: `mvp-qa-run-portal-webapps-123456789012.us-east1.run.app`).
4. Haz clic en **Agregar** y luego en **Guardar**.

### 3.6 Probar el ingreso

1. Abre `<URL_QA>` y escribe `<TU_CORREO>`. Haz clic en **Enviar enlace de acceso**.
2. Abre el correo (revisa spam) y haz clic en el enlace **en el mismo navegador**.
3. Resultado esperado: **"Aún no tienes herramientas habilitadas"**. El login funciona; todavía no hay apps.

### 3.7 Mergear la PR del portal

En la PR haz clic en **Merge pull request** y luego en **Confirm merge**.

---

## 4. Herramienta (tu HTML) en QA

### 4.1 Rama nueva desde el `main` actualizado

1. En GitHub Desktop: **Current branch → main**, luego **Fetch origin** y **Pull origin**.
2. **Current branch → New branch** con nombre `mvp-app` (basada en `main`). Haz clic en **Create branch**.

### 4.2 Agregar la app

Crea la carpeta `apps/demo/mi_herramienta/`. Si cambias el dominio o el nombre, usa minúsculas, dígitos y `_`, y cambia también `id` y `dominio` en el `app.yaml`. Dentro de la carpeta:

**a) `index.html`:** tu HTML, renombrado exactamente así.

**b) `app.yaml`:**

```yaml
id: mi_herramienta
dominio: demo
version: "2026-10-05-01"
tipo: herramienta

tarjeta:
  titulo: "Mi herramienta"
  descripcion: "Descripción corta de lo que hace la herramienta."
  icono: chart-line
  etiqueta: "Demo"

acceso:
  qa:
    - <TU_CORREO>
  prd:
    - <TU_CORREO>

labels:
  ceco: mvp
  managed_by: <USUARIO_GH en minúsculas>
```

Reglas que valida el workflow:
- el correo va en minúsculas y debe cumplir `politica_correos.yaml`;
- `icono` debe estar en `portal/config/iconos_permitidos.yaml` (por ejemplo `chart-line`, `table`, `calculator`, `map`);
- los labels solo admiten minúsculas, dígitos, `_` y `-`.

### 4.3 Revisar el HTML antes de publicarlo

| Revisa | Por qué |
|---|---|
| Es un solo archivo, sin `src="./algo.js"` ni archivos locales | El visor carga solo `index.html` |
| Pesa menos de 5 MB | Tope de la plataforma (`pr_checks`) |
| Sus librerías externas vienen de jsDelivr, cdnjs, unpkg, Plotly o Google Fonts, y sus mapas de OpenStreetMap o Carto | Todo lo demás lo bloquea el navegador. Para otro dominio hay que agregarlo en `portal/config/csp_allowlist.yaml` y redesplegar el portal |
| No usa `localStorage`, `sessionStorage`, IndexedDB ni cookies | El visor aísla el HTML y esas APIs fallan dentro del iframe |
| No contiene datos sensibles | El repo es privado, pero es git: queda en el historial |

### 4.4 Commit, PR y despliegue en QA

1. En GitHub Desktop: escribe `App de prueba`, haz clic en **Commit to mvp-app**, luego en **Publish branch** y en **Create Pull Request → Create pull request**.
2. Abre **Actions → Deploy to QA → Run workflow**. Deja **Use workflow from:** `main` y en **Rama a desplegar** pon `mvp-app`. Haz clic en **Run workflow**. Demora unos 2 minutos.
3. Resultado: en la PR aparece el comentario con la huella y los objetos publicados (`qa/_catalogo/demo/mi_herramienta.json` y `qa/demo/mi_herramienta/index.html`).

### 4.5 Probar en QA

1. Recarga `<URL_QA>`. Si la sesión venció, vuelve a ingresar.
2. Resultado esperado:
   - en **Herramientas** aparece la tarjeta **Mi herramienta**;
   - al hacer clic, el HTML se abre en el visor con la marca de agua;
   - puedes interactuar con él.
3. Si algo no se ve bien dentro del HTML, abre las herramientas de desarrollador (F12 → Consola) y revisa §8.

### 4.6 Mergear la PR de la app

Haz clic en **Merge pull request → Confirm merge**. Esto dispara **Sync accesos QA**, que debe terminar en verde. Ese workflow sincroniza los accesos de QA sin redesplegar.

---

## 5. Cómo funciona el pase a PRD (resumen)

Cada pase es igual para el portal y para la app:

1. Crear desde `main` la **rama release** con el nombre exacto.
2. Crear el **issue "Pase a producción"**.
3. Ejecutar **Deploy to PRD** con el número del issue.

El workflow valida:

| Control | Qué valida |
|---|---|
| C1 | Quien ejecuta está en `PRD_APPROVERS` |
| C2 | El issue y sus campos son válidos y la rama release existe |
| C3 | La versión del issue es la del código |
| C4 | Lo que va a PRD es exactamente lo que pasó por QA |

Si todo pasa, despliega, comenta el resultado en el issue y lo cierra. Si un control rechaza el pase, el issue queda abierto con el motivo.

---

## 6. Pase del portal a PRD

### 6.1 Rama release

1. En la página principal del repo, abre el selector de ramas (dice `main`).
2. Escribe `release_portal_2026-10-05-01`.
3. Haz clic en **Create branch: release_portal_2026-10-05-01 from main**.

### 6.2 Issue de solicitud

Abre **Issues → New issue → Pase a producción → Get started** y completa:

| Campo | Valor |
|---|---|
| Unidad a desplegar | `portal` |
| Versión | `2026-10-05-01` |
| Tipo de cambio | `Inicial` |
| Área de negocio impactada | `MVP` |
| Detalle del cambio | `Primer despliegue del portal en PRD` |

Haz clic en **Create** y anota el número del issue (por ejemplo `#3`).

### 6.3 Ejecutar el pase

1. Abre **Actions → Deploy to PRD → Run workflow**.
2. Deja **Use workflow from:** `main` e ingresa el número del issue, sin `#`.
3. Haz clic en **Run workflow**. Demora unos 5 a 8 minutos: promueve la imagen validada en QA, despliega y hace el smoke test.
4. Resultado: el issue recibe el comentario **✅ Pase a producción: EXITOSO** y se cierra.

### 6.4 URL de PRD y dominio autorizado

1. Abre **Menú ☰ → Cloud Run → Servicios → `mvp-prd-run-portal-webapps`** y copia la **URL** de arriba. Anótala como `<URL_PRD>`. También aparece en el log del step **Deploy a Cloud Run (PRD)**.
2. Agrégala a **Identity Platform → Configuración → Seguridad → Dominios autorizados**, igual que en §3.5.
3. Abre `<URL_PRD>` e ingresa. Resultado esperado: **"Aún no tienes herramientas habilitadas"**, porque la app aún no está en PRD.

---

## 7. Pase de la app a PRD

1. **Rama release:** `release_demo_mi_herramienta_2026-10-05-01`, desde `main`.
2. **Issue "Pase a producción":**
   - Unidad a desplegar: `apps/demo/mi_herramienta`
   - Versión: `2026-10-05-01`
   - Tipo de cambio: `Inicial`
   - Área de negocio impactada: `MVP`
   - Detalle del cambio: `Primera publicación de la herramienta`
3. **Actions → Deploy to PRD → Run workflow** con el número del issue. Demora unos 2 minutos.
4. Recarga `<URL_PRD>`. Resultado esperado: la tarjeta aparece y el HTML se abre y funciona. **El MVP queda validado.**

### 7.1 Checklist final

| # | Verificación | ✔ |
|---|---|---|
| 1 | `Deploy to QA` del portal en verde y comentario en la PR | |
| 2 | Ingreso por enlace en QA → página "sin herramientas" | |
| 3 | `Deploy to QA` de la app → tarjeta visible en QA | |
| 4 | El HTML funciona dentro del visor, con la marca de agua | |
| 5 | `Sync accesos QA` en verde al mergear la app | |
| 6 | `Deploy to PRD` del portal: issue comentado y cerrado | |
| 7 | `Deploy to PRD` de la app: tarjeta y HTML funcionando en PRD | |
| 8 | Un correo que no está en `acceso.prd` ve "sin herramientas" (opcional, con un segundo correo) | |

### 7.2 Pruebas opcionales

- **Cambio solo de accesos:**
  1. Agrega un segundo correo en `acceso.prd`, sube `version` a `2026-10-05-02` y abre una PR. No corras `Deploy to QA`.
  2. Mergea, crea la release `release_demo_mi_herramienta_2026-10-05-02`, el issue y ejecuta `Deploy to PRD`.
  3. El pase debe pasar C4 sin un nuevo QA, y el comentario del issue muestra `Accesos: +1 / -0`.
- **Control C4:**
  1. Cambia el HTML en una rama y mergéala **sin** correr `Deploy to QA`.
  2. Intenta el pase a PRD. Debe rechazarse en C4 con el motivo en el issue.

---

## 8. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `google-github-actions/auth` falla: "unable to impersonate" o "Permission 'iam.serviceAccounts.getAccessToken' denied" | Falta el acceso de §1.7, o `<USUARIO_GH>/<REPO>` no coincide exactamente | Revisa la condición del proveedor y el principal del acceso (mayúsculas incluidas). Verifica las APIs de §1.3 |
| `Validate required GitHub Variables` falla | Falta una variable o tiene un error de nombre | Revisa §2.3 |
| `denied: Permission "artifactregistry.repositories.uploadArtifacts"` | Rol o repositorio incorrecto | Rol Artifact Registry Writer en la deployer; `imagen.repositorio` debe terminar en `/mvp-arg-portal` |
| `iam.serviceaccounts.actAs` denegado al desplegar | Falta Service Account User | Agrégalo a la deployer (§1.6) |
| Error con `allUsers` o "domain restricted sharing" al desplegar | El proyecto está dentro de una organización | Usa un proyecto **sin organización** (§1.1) |
| El smoke test falla (no responde la versión) | El contenedor no arrancó | **Cloud Run → servicio → Registros** (Logs): suele ser un valor mal escrito en `env_*.yaml` |
| Al enviar el enlace: "auth/operation-not-allowed" | El acceso sin contraseña no está activo | §1.8, paso 4 |
| Al enviar el enlace: "unauthorized-continue-uri" o "domain not allowlisted" | Falta el dominio del Cloud Run | §3.5 / §6.4: dominio exacto, sin `https://` |
| El correo no llega | Spam o filtro corporativo | Revisa spam o usa un correo personal (§3.2 d) |
| Tras abrir el enlace: "No pudimos completar el ingreso" | La cuenta runtime no puede crear la sesión | Verifica el rol Firebase Authentication Admin en `mvp-gsa-portal-runtime`; espera 2 a 3 minutos (propagación de IAM) y pide otro enlace |
| Al escribir el correo: "Solo pueden ingresar colaboradores con correo corporativo de Alicorp." | El dominio no está en la política | §3.2 d; requiere redesplegar el portal (nueva rama → `Deploy to QA`) |
| No aparece la tarjeta | El correo no está en `acceso.qa`/`acceso.prd`, o el catálogo aún no se refrescó | Revisa el `app.yaml`; espera 60 s y recarga |
| "Aún no hay datos publicados para esta herramienta" | No existe el `index.html` en el bucket | Revisa que el archivo se llame `index.html` y que `tipo` sea `herramienta` |
| El HTML se ve en blanco o incompleto | Bloqueo de la CSP, almacenamiento del navegador o archivos locales | F12 → Consola. "Refused to load…": dominio fuera de `csp_allowlist.yaml`. "SecurityError… localStorage": el HTML usa almacenamiento. 404 de `.js`/`.css`: archivos no embebidos |
| Deploy to PRD: C2 rechaza | El nombre de la rama release o un campo del issue no coincide | Rama `release_portal_<versión>` o `release_<dominio>_<app>_<versión>`, creada desde `main` |
| Deploy to PRD: C3 rechaza | La versión del issue ≠ la del código | Corrige el issue o crea un issue nuevo |
| Deploy to PRD: C4 rechaza | Lo que va a PRD no pasó por QA | Corre `Deploy to QA` sobre el código final, mergea y repite el pase |
| Deploy to PRD: C1 rechaza | `PRD_APPROVERS` no tiene tu usuario exacto | §2.3 |

Si algo falla y no está en la tabla, copia el log del step en rojo y lo revisamos.

---

## 9. Costos y limpieza

| Recurso | Costo aproximado |
|---|---|
| Cloud Run (QA y PRD con 0 instancias mínimas) | ~US$0: solo se cobra mientras atiende |
| Artifact Registry (imágenes del portal) | Centavos (US$0.10 por GB al mes) |
| Cloud Storage | Centavos |
| Identity Platform (inicio de sesión por correo) | Gratis a esta escala |
| **Total** | **< US$1 al mes** |

Para borrar todo al terminar: **IAM y administración → Configuración → Cerrar** (Shut down). Ingresa el ID del proyecto y confirma. El proyecto y sus recursos se eliminan en 30 días.

---

## 10. Qué cambia al pasar a Alicorp

El manual de implementación en Alicorp parte de este flujo y agrega lo que se dejó fuera:
- proyectos `acpe-qa-uc-ml` / `acpe-prod-uc-ml`;
- cuentas y roles por recurso;
- WIF existente;
- bitácora (`BITACORA_URI_PRD`);
- sink de auditoría;
- CODEOWNERS y rulesets;
- Dependabot;
- PR al repo de ML.

En los YAML basta con restaurar los valores de Alicorp en `env_qa.yaml` y `env_prd.yaml`.
