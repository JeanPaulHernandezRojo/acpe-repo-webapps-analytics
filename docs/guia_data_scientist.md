# Guía del Data Scientist: publicar una app en ALEJANDRÍA

Esta guía explica cómo llevar un HTML analítico al portal: dónde vive, cómo se registra y
qué reglas debe cumplir. El portal **no modifica tu HTML**: lo muestra tal cual, dentro de
un visor aislado y solo a los correos que declares.

## 1. ¿Qué tipo de app es la tuya?

| Tipo | Cuándo | Dónde vive el HTML | Quién escribe el `index.html` que ve el usuario |
|---|---|---|---|
| `pipeline` | El HTML muestra datos que calcula un pipeline (N0) | Plantilla sin datos en el repo de ML: `projects/<dominio>/<proyecto>/src/webapp/` | Tu pipeline, en cada corrida, en el bucket de webapps |
| `herramienta` | El usuario carga su propio Excel/CSV y el HTML lo procesa en el navegador (N1) | Este repo: `apps/<dominio>/<app>/index.html` | CI, al desplegar la app |

En ambos casos la app se **registra** en este repo con un `app.yaml`.

## 2. Registrar la app: `apps/<dominio>/<app>/app.yaml`

```yaml
# apps/supply/stock_seguridad_indirectos/app.yaml
id: stock_seguridad_indirectos        # = nombre de la carpeta (snake_case)
dominio: supply                       # = carpeta padre (snake_case)
version: "2026-10-01-01"              # CalVer AAAA-MM-DD-NN; súbela en cada pase a PRD
tipo: pipeline                        # pipeline | herramienta

tarjeta:                              # lo que el usuario ve en "Herramientas"
  titulo: "Stock de seguridad – indirectos"
  descripcion: "Revisa el stock de seguridad sugerido y su cobertura por material."
  icono: boxes                        # de portal/config/iconos_permitidos.yaml
  etiqueta: "Supply"                  # texto de la esquina de la tarjeta

acceso:                               # correos en minúsculas; pueden ser listas vacías
  qa:
    - ana.perez@alicorp.com.pe
  prd:
    - ana.perez@alicorp.com.pe
    - luis.rojas@alicorp.com.pe

# Opcional. Todas activadas si se omite; desactiva solo lo que la app no deba permitir.
capacidades:
  descargas: true      # exportar archivos (CSV, PNG, etc.)
  ventanas: true       # abrir enlaces o ventanas emergentes
  dialogos: true       # alert / confirm / prompt
  formularios: true    # enviar formularios

# Opcional: patron_suave (por defecto) · esquina · franja · patron
marca_agua: patron_suave

labels:                               # costos y trazabilidad
  ceco: data-analytics
  managed_by: jperez
```

`pr_checks` valida el archivo completo y reporta todos los errores juntos: que `id` y
`dominio` coincidan con las carpetas, la versión, el tipo (y que una herramienta tenga
`index.html` y una app de pipeline no), la tarjeta, el ícono, los correos contra la
política (dominio `@alicorp.com.pe`, minúsculas, sin repetidos), las capacidades, la marca
de agua y los labels. El dominio `portal` está reservado.

## 3. Reglas del HTML

La plataforma solo verifica el tamaño. El resto es responsabilidad tuya y del revisor de
la PR.

1. **Fecha de actualización visible, siempre.** Todo HTML con datos muestra la fecha (y
   de preferencia la hora) de sus datos, en el lugar que consideres adecuado. El usuario
   la usa para saber si está viendo información vigente. El portal no la calcula ni la
   agrega.
2. **Sin datos reales en git.** Las plantillas y herramientas del repo llevan solo datos
   ficticios o de ejemplo. Los datos reales existen únicamente en el bucket. La PR incluye
   una casilla para confirmarlo.
3. **Máximo 5 MB por HTML en git.** Lo controlan el hook de pre-commit y `pr_checks`.
4. **Recursos externos solo de la lista blanca** (`portal/config/csp_allowlist.yaml`):
   - mapas: OpenStreetMap y Carto;
   - CDN: jsDelivr, cdnjs, unpkg, Plotly y Google Fonts.

   Todo lo demás lo bloquea el navegador. Si necesitas otro dominio, pídelo con una PR a
   ese archivo (la revisa el LT).
5. **Todo dentro de un solo `index.html`.** El visor carga ese único archivo: los estilos,
   scripts y datos van embebidos o vienen de la lista blanca.
6. **Nada de sesión propia ni de rutas al portal.** El HTML corre aislado: no puede leer
   las cookies del portal ni navegar la página principal.

## 4. App de pipeline: inyección y escritura en el bucket

La inyección de datos la escribes y validas tú, en tu proyecto (DEV/QA). No hay un helper
de plataforma. El patrón recomendado:

1. La plantilla (`src/webapp/plantilla.html`) tiene marcadores únicos donde van los datos,
   por ejemplo `__DATOS__` y `__FECHA_ACTUALIZACION__`.
2. El task del pipeline reemplaza cada marcador **una sola vez** con `str.replace`, con los
   datos serializados como JSON. No uses `str.format` ni f-strings sobre el HTML: el CSS y
   el JavaScript están llenos de llaves `{}`.
3. Antes de escribir, verifica que ya no quede ningún marcador en el resultado.

```python
# src/webapp_publicacion.py (junto a src/webapp/plantilla.html)
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mle_runtime import gcs

_PLANTILLA = Path(__file__).parent / "webapp" / "plantilla.html"


def publicar_webapp(datos: list[dict], webapp_root: str) -> None:
    """Inyecta los datos en la plantilla y publica el HTML del portal.

    Args:
        datos: Registros a mostrar.
        webapp_root: gs://us-<env>-stg-ml-webapps/<qa|prd>/<dominio>/<app>/ (parámetro por ambiente).
    """
    ahora = datetime.now(tz=ZoneInfo("America/Lima"))
    html = (
        _PLANTILLA.read_text(encoding="utf-8")
        .replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
        .replace("__FECHA_ACTUALIZACION__", ahora.strftime("%d/%m/%Y %H:%M"))
    )
    if "__DATOS__" in html or "__FECHA_ACTUALIZACION__" in html:
        raise ValueError("Quedaron marcadores sin reemplazar en la plantilla.")

    contenido = html.encode("utf-8")
    # Vigente: es el único archivo que lee el portal.
    gcs.write_bytes(
        data=contenido, uri=f"{webapp_root}index.html", content_type="text/html; charset=utf-8"
    )
    # Opcional: copia histórica (el portal no la lee).
    gcs.write_bytes(
        data=contenido,
        uri=f"{webapp_root}historico/{ahora:%Y%m%d_%H%M%S}.html",
        content_type="text/html; charset=utf-8",
    )
```

**Ruta por ambiente.** Declara `webapp_root` en los overrides de tu proyecto del repo de ML:

```yaml
# config/overrides/qa.yaml
parameters:
  webapp_root: "gs://us-qa-stg-ml-webapps/qa/supply/stock_seguridad_indirectos/"

# config/overrides/prd.yaml
parameters:
  webapp_root: "gs://us-prod-stg-ml-webapps/prd/supply/stock_seguridad_indirectos/"
```

La carpeta debe ser `<prefijo>/<dominio>/<id>/` con el mismo `dominio` e `id` del
`app.yaml`. Usa siempre `content_type="text/html; charset=utf-8"`. No escribas nunca en
`_catalogo/`: esa carpeta es del portal.

**Orden recomendado para una app nueva de pipeline:**
1. En el repo de ML: plantilla + task + `webapp_root`; `Deploy to QA` escribe el primer
   `index.html` en QA.
2. En este repo: `app.yaml` con `tipo: pipeline`; `Deploy to QA` registra la app en el
   catálogo de QA. Valida en el portal de QA con un correo de `acceso.qa`.
3. Pases a PRD de ambos repos (el del pipeline primero, para que el HTML exista).

## 5. Herramienta: el HTML en este repo

1. Crea `apps/<dominio>/<app>/index.html` (sin datos reales) y su `app.yaml` con
   `tipo: herramienta`.
2. Todo el procesamiento del Excel/CSV ocurre en el navegador del usuario (por ejemplo
   SheetJS o PapaParse desde un CDN de la lista blanca). El archivo no sale de su equipo.
3. Si la herramienta exporta resultados, deja `capacidades.descargas: true` (valor por
   defecto).

## 6. Flujo de trabajo en este repo

1. Rama desde `main`, una sola app por PR (`apps/<dominio>/<app>`).
2. Instala los hooks una vez: `uv sync --group dev && uv run pre-commit install`.
3. Abre la PR. `pr_checks` valida el `app.yaml`, el tamaño del HTML y los hooks.
4. Ejecuta **Actions → Deploy to QA** con tu rama. Publica la app en QA y comenta en la PR.
   Si luego haces más commits, vuelve a desplegar: el pase a PRD exige que lo publicado en
   QA sea exactamente lo que se mergea.
5. Valida en el portal de QA con un correo de `acceso.qa`.
6. Pide aprobación y mergea.
7. Para PRD sigue [`manual_pases.md`](manual_pases.md): rama
   `release_<dominio>_<app>_<version>` e issue "Pase a producción".

**Cambios solo de accesos** (agregar o quitar correos, con o sin nueva `version`): no
necesitan `Deploy to QA`. Al mergear, QA se actualiza solo. Para PRD se sigue haciendo el
pase, y la bitácora registra los correos agregados y quitados.
