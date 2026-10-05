"""Controles de la solicitud y bitácora del pase a producción (portal o app).

Lo usa deploy_prd.yml en tres momentos:

    validar-solicitud  C2: lee el issue, valida sus campos y deriva la rama release y su SHA.
                       Es la única fuente de la unidad a desplegar y de la versión.
    validar-qa         C4: confirma que lo que va a PRD es exactamente lo validado en QA.
                       - portal: la imagen <version>-<sha> más reciente con `deploy/qa` exitoso
                         cuyo portal/, pyproject.toml, uv.lock y .dockerignore son idénticos
                         a los del release.
                       - app: la huella de la app en la rama release es igual a la huella
                         publicada en el catálogo de QA. En un Rollback basta con que esa huella
                         haya tenido un pase exitoso anterior registrado en la bitácora.
    registrar          Escribe en GCS un JSON por ejecución (exitosa, fallida o rechazada),
                       comenta la solicitud y la cierra si el pase terminó bien.

Los tres comparten un archivo de contexto (--contexto). Usa solo la librería estándar y las
CLI git y gcloud, y se ejecuta desde el checkout de main: la bitácora no depende del código
de la versión que se despliega (en un rollback, la rama release puede ser anterior).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

API_URL = "https://api.github.com"
ZONA = ZoneInfo("America/Lima")

# Contrato con .github/ISSUE_TEMPLATE/pase_prd.yml: labels de los campos tal como GitHub
# los renderiza en el cuerpo del issue ("### <label>").
CAMPO_RUTA = "Unidad a desplegar"
CAMPO_VERSION = "Versión"
CAMPO_TIPO = "Tipo de cambio"
CAMPO_AREA = "Área de negocio impactada"
CAMPO_DETALLE = "Detalle del cambio"

TIPOS_VALIDOS = ("Inicial", "Incremental", "Rollback")
PATRON_RUTA = re.compile(r"^(portal|apps/[a-z][a-z0-9_]*/[a-z][a-z0-9_]*)$")
PATRON_VERSION = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}$")

# Todo lo que define la imagen del portal: debe ser idéntico entre el QA y el release.
RUTAS_IMAGEN_PORTAL = ("portal", "pyproject.toml", "uv.lock", ".dockerignore")

# Carpeta de la bitácora para los pases del portal.
CARPETA_BITACORA_PORTAL = "_portal"

CONTEXTO_QA = "deploy/qa"


class ControlError(Exception):
    """Falla de un control: se reporta como ::error:: y marca el pase rechazado."""


def api(token: str, method: str, ruta: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
    """Llama a la API de GitHub.

    Args:
        token: Token de la ejecución (GITHUB_TOKEN).
        method: Método HTTP.
        ruta: Ruta relativa a la API o URL absoluta.
        payload: Cuerpo JSON, o None.

    Returns:
        Tupla (código HTTP, cuerpo deserializado o None).
    """
    url = ruta if ruta.startswith("http") else f"{API_URL}{ruta}"
    datos = json.dumps(payload).encode("utf-8") if payload is not None else None
    peticion = urllib.request.Request(url=url, data=datos, method=method)
    peticion.add_header("Authorization", f"Bearer {token}")
    peticion.add_header("Accept", "application/vnd.github+json")
    peticion.add_header("X-GitHub-Api-Version", "2022-11-28")
    if datos is not None:
        peticion.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            cuerpo = respuesta.read()
            return respuesta.status, (json.loads(cuerpo) if cuerpo else None)
    except urllib.error.HTTPError as error:
        cuerpo = error.read()
        try:
            return error.code, json.loads(cuerpo) if cuerpo else None
        except json.JSONDecodeError:
            return error.code, None


def git(repo_dir: str, args: list[str]) -> str:
    """Ejecuta git sobre el checkout indicado y devuelve su salida.

    Args:
        repo_dir: Carpeta del checkout.
        args: Argumentos de git.

    Returns:
        La salida estándar sin espacios finales.
    """
    resultado = subprocess.run(
        ["git", "-C", repo_dir, *args], check=True, capture_output=True, text=True
    )
    return resultado.stdout.strip()


def gcloud(args: list[str]) -> str:
    """Ejecuta gcloud y devuelve su salida.

    Args:
        args: Argumentos de gcloud.

    Returns:
        La salida estándar sin espacios finales.
    """
    resultado = subprocess.run(["gcloud", *args], check=True, capture_output=True, text=True)
    return resultado.stdout.strip()


def ahora() -> str:
    """Fecha y hora actual en America/Lima, en ISO 8601."""
    return datetime.now(tz=ZONA).isoformat(timespec="seconds")


def a_hora_local(marca_utc: str) -> str:
    """Convierte una marca ISO en UTC de la API a hora de Lima.

    Args:
        marca_utc: Texto ISO 8601 terminado en Z, o vacío.

    Returns:
        La marca en hora de Lima, o el texto original si no se pudo interpretar.
    """
    if not marca_utc:
        return ""
    try:
        return (
            datetime.fromisoformat(marca_utc.replace("Z", "+00:00"))
            .astimezone(ZONA)
            .isoformat(timespec="seconds")
        )
    except ValueError:
        return marca_utc


def salida_github(nombre: str, valor: str) -> None:
    """Publica un output del step actual.

    Args:
        nombre: Nombre del output.
        valor: Valor del output.
    """
    destino = os.environ.get("GITHUB_OUTPUT")
    if destino:
        with open(destino, "a", encoding="utf-8") as archivo:
            archivo.write(f"{nombre}={valor}\n")


def leer_contexto(ruta: str) -> dict[str, Any]:
    """Lee el archivo de contexto; devuelve un dict vacío si aún no existe.

    Args:
        ruta: Ruta del archivo de contexto.

    Returns:
        El contexto acumulado.
    """
    archivo = Path(ruta)
    if not archivo.exists():
        return {}
    return json.loads(archivo.read_text(encoding="utf-8"))


def escribir_contexto(ruta: str, contexto: dict[str, Any]) -> None:
    """Persiste el archivo de contexto.

    Args:
        ruta: Ruta del archivo de contexto.
        contexto: Contenido a guardar.
    """
    Path(ruta).write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")


def parsear_formulario(cuerpo: str) -> dict[str, str]:
    """Convierte el cuerpo renderizado de un issue form en un dict label -> valor.

    Args:
        cuerpo: Texto markdown del issue, con los campos como encabezados '### '.

    Returns:
        Diccionario con el valor de cada campo; los campos sin respuesta quedan vacíos.
    """
    campos: dict[str, str] = {}
    etiqueta = ""
    acumulado: list[str] = []
    for linea in (cuerpo or "").splitlines():
        if linea.startswith("### "):
            if etiqueta:
                campos[etiqueta] = "\n".join(acumulado).strip()
            etiqueta = linea[4:].strip()
            acumulado = []
        elif etiqueta:
            acumulado.append(linea)
    if etiqueta:
        campos[etiqueta] = "\n".join(acumulado).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in campos.items()}


def rama_release(ruta: str, version: str) -> str:
    """Nombre de la rama release de una unidad.

    Args:
        ruta: 'portal' o 'apps/<dominio>/<app>'.
        version: Versión CalVer.

    Returns:
        release_portal_<version> o release_<dominio>_<app>_<version>.
    """
    if ruta == "portal":
        return f"release_portal_{version}"
    _, dominio, app = ruta.split("/")
    return f"release_{dominio}_{app}_{version}"


def carpeta_bitacora(ruta: str) -> str:
    """Carpeta de la bitácora de una unidad.

    Args:
        ruta: 'portal' o 'apps/<dominio>/<app>'.

    Returns:
        '_portal' o '<dominio>/<app>'.
    """
    if ruta == "portal":
        return CARPETA_BITACORA_PORTAL
    _, dominio, app = ruta.split("/")
    return f"{dominio}/{app}"


def persona(token: str, login: str, cache: dict[str, dict[str, str]]) -> dict[str, str]:
    """Devuelve login, ID numérico y nombre de perfil de un usuario.

    Args:
        token: Token de la ejecución.
        login: Usuario de GitHub.
        cache: Resultados ya consultados, que se actualiza in situ.

    Returns:
        Diccionario con nom_usuario_github, id_usuario_github y nom_perfil.
    """
    if login in cache:
        return cache[login]
    estado, cuerpo = api(token=token, method="GET", ruta=f"/users/{login}", payload=None)
    datos = cuerpo if estado == 200 and isinstance(cuerpo, dict) else {}
    ficha = {
        "nom_usuario_github": login,
        "id_usuario_github": str(datos.get("id", "")),
        "nom_perfil": datos.get("name") or "",
    }
    cache[login] = ficha
    return ficha


def hash_de_ruta(token: str, repo: str, sha: str, ruta: str) -> str:
    """Obtiene el hash git (árbol o blob) de una carpeta o archivo en un commit, vía la API.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        sha: Commit a inspeccionar.
        ruta: Carpeta o archivo relativo a la raíz.

    Returns:
        El hash, o cadena vacía si la ruta no existe en ese commit.
    """
    padre, _, nombre = ruta.rpartition("/")
    carpeta = f"/repos/{repo}/contents/{padre}" if padre else f"/repos/{repo}/contents"
    estado, cuerpo = api(token=token, method="GET", ruta=f"{carpeta}?ref={sha}", payload=None)
    if estado != 200 or not isinstance(cuerpo, list):
        return ""
    for entrada in cuerpo:
        if entrada.get("name") == nombre:
            return str(entrada.get("sha", ""))
    return ""


def estado_qa(token: str, repo: str, sha: str) -> dict[str, str]:
    """Busca el commit status `deploy/qa` de un commit.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        sha: Commit a consultar.

    Returns:
        est_resultado, des_url_ejecucion y fec_ejecucion; vacío si no hay status.
    """
    estado, cuerpo = api(
        token=token, method="GET", ruta=f"/repos/{repo}/commits/{sha}/status", payload=None
    )
    if estado != 200 or not isinstance(cuerpo, dict):
        return {}
    for status in cuerpo.get("statuses", []):
        if status.get("context") == CONTEXTO_QA:
            return {
                "est_resultado": status.get("state", ""),
                "des_url_ejecucion": status.get("target_url", ""),
                "fec_ejecucion": a_hora_local(status.get("updated_at", "")),
            }
    return {}


def imagenes_de_version(qa_image: str, version: str) -> list[dict[str, str]]:
    """Lista las imágenes del AR de QA etiquetadas como <version>-<sha>.

    Args:
        qa_image: Ruta de la imagen sin tag en el AR de QA.
        version: Versión CalVer del release.

    Returns:
        Candidatas con tag y sha corto, de la más reciente a la más antigua.
    """
    salida = gcloud(
        ["artifacts", "docker", "images", "list", qa_image, "--include-tags", "--format=json"]
    )
    patron = re.compile(rf"^{re.escape(version)}-([0-9a-f]{{7,40}})$")
    candidatas: list[dict[str, str]] = []
    for imagen in json.loads(salida or "[]"):
        etiquetas = imagen.get("tags", [])
        if isinstance(etiquetas, str):
            etiquetas = [t.strip() for t in etiquetas.split(",") if t.strip()]
        for etiqueta in etiquetas:
            coincidencia = patron.match(etiqueta)
            if coincidencia:
                candidatas.append(
                    {
                        "tag": etiqueta,
                        "sha_corto": coincidencia.group(1),
                        "fec_creacion": imagen.get("createTime", ""),
                    }
                )
    return sorted(candidatas, key=lambda c: c["fec_creacion"], reverse=True)


def leer_gcs_json(uri: str) -> dict[str, Any] | None:
    """Lee un JSON de GCS con gcloud.

    Args:
        uri: URI gs:// del objeto.

    Returns:
        El contenido, o None si no existe.
    """
    try:
        return json.loads(gcloud(["storage", "cat", uri]))
    except subprocess.CalledProcessError:
        return None


def pases_exitosos(bucket_uri: str, carpeta: str) -> list[str]:
    """Lista los JSON de pases exitosos de una unidad, del más antiguo al más reciente.

    Args:
        bucket_uri: Prefijo gs:// de la bitácora.
        carpeta: Carpeta de la unidad en la bitácora.

    Returns:
        URIs de los pases exitosos.
    """
    try:
        listado = gcloud(["storage", "ls", f"{bucket_uri.rstrip('/')}/{carpeta}/"])
    except subprocess.CalledProcessError:
        return []
    return sorted(linea for linea in listado.splitlines() if linea.endswith("_exitoso.json"))


def validar_solicitud(
    token: str, repo: str, server_url: str, issue_number: str, repo_dir: str, contexto_path: str
) -> int:
    """Control C2: valida el issue de solicitud y deriva la rama release.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        server_url: URL base de GitHub.
        issue_number: Número del issue.
        repo_dir: Checkout de main con el historial completo.
        contexto_path: Archivo de contexto a escribir.

    Returns:
        Exit code (0 OK, 1 rechazado).
    """
    contexto: dict[str, Any] = {
        "cod_solicitud": issue_number,
        "des_url_solicitud": f"{server_url}/{repo}/issues/{issue_number}",
    }
    try:
        estado, issue = api(
            token=token, method="GET", ruta=f"/repos/{repo}/issues/{issue_number}", payload=None
        )
        if estado != 200 or not isinstance(issue, dict):
            raise ControlError(f"No existe el issue #{issue_number} en {repo}.")
        if issue.get("pull_request"):
            raise ControlError(f"#{issue_number} es una PR, no una solicitud de pase.")
        if issue.get("state") != "open":
            raise ControlError(f"El issue #{issue_number} está cerrado.")

        campos = parsear_formulario(issue.get("body", ""))
        faltantes = [
            campo
            for campo in (CAMPO_RUTA, CAMPO_VERSION, CAMPO_TIPO, CAMPO_AREA, CAMPO_DETALLE)
            if not campos.get(campo)
        ]
        if faltantes:
            raise ControlError(
                "La solicitud no se creó con el formulario o tiene campos vacíos: "
                + ", ".join(faltantes)
            )

        ruta = campos[CAMPO_RUTA].strip().strip("/")
        version = campos[CAMPO_VERSION].strip()
        tipo = campos[CAMPO_TIPO].strip()
        if not PATRON_RUTA.match(ruta):
            raise ControlError(f"Unidad inválida '{ruta}'. Usar 'portal' o 'apps/<dominio>/<app>'.")
        if not PATRON_VERSION.match(version):
            raise ControlError(f"Versión inválida '{version}'. Formato: AAAA-MM-DD-NN.")
        if tipo not in TIPOS_VALIDOS:
            raise ControlError(f"Tipo de cambio inválido '{tipo}'.")

        tipo_unidad = "portal" if ruta == "portal" else "app"
        _, dominio, app_id = ruta.split("/") if tipo_unidad == "app" else ("", "", "")
        contexto.update(
            {
                "des_ruta_unidad": ruta,
                "tip_unidad": tipo_unidad,
                "nom_dominio": dominio,
                "nom_app": app_id,
                "cod_version": version,
                "tip_cambio": tipo,
            }
        )
        rama = rama_release(ruta=ruta, version=version)
        try:
            sha_release = git(
                repo_dir, ["rev-parse", "--verify", f"refs/remotes/origin/{rama}^{{commit}}"]
            )
        except subprocess.CalledProcessError:
            raise ControlError(
                f"No existe la rama '{rama}'. Debe crearse desde main antes del pase."
            ) from None

        asignados = issue.get("assignees") or []
        cache: dict[str, dict[str, str]] = {}
        contexto.update(
            {
                "des_cambio": campos[CAMPO_DETALLE].strip(),
                "des_area_negocio": campos[CAMPO_AREA].strip(),
                "fec_solicitud": a_hora_local(issue.get("created_at", "")),
                "solicitante": persona(token=token, login=issue["user"]["login"], cache=cache),
                "lt_asignado": (
                    persona(token=token, login=asignados[0]["login"], cache=cache)
                    if asignados
                    else None
                ),
                "nom_rama_release": rama,
                "cod_sha_release": sha_release,
            }
        )
    except ControlError as error:
        contexto["des_motivo_resultado"] = str(error)
        escribir_contexto(contexto_path, contexto)
        sys.stderr.write(f"::error::C2: {error}\n")
        return 1

    escribir_contexto(contexto_path, contexto)
    salida_github("unidad", contexto["des_ruta_unidad"])
    salida_github("tipo_unidad", contexto["tip_unidad"])
    salida_github("tipo_cambio", contexto["tip_cambio"])
    salida_github("version", contexto["cod_version"])
    salida_github("release_branch", contexto["nom_rama_release"])
    salida_github("release_sha", contexto["cod_sha_release"])
    return 0


def _rechazar_qa(contexto_path: str, contexto: dict[str, Any], motivo: str) -> int:
    """Registra el rechazo de C4 en el contexto y lo reporta.

    Args:
        contexto_path: Archivo de contexto.
        contexto: Contexto actual.
        motivo: Motivo del rechazo.

    Returns:
        Exit code 1.
    """
    contexto["des_motivo_resultado"] = motivo
    escribir_contexto(contexto_path, contexto)
    sys.stderr.write(f"::error::C4: {motivo}\n")
    return 1


def validar_qa_portal(token: str, repo: str, qa_image: str, contexto_path: str) -> int:
    """C4 del portal: ubica la imagen de QA construida con el mismo código del release.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        qa_image: Ruta de la imagen sin tag en el AR de QA.
        contexto_path: Archivo de contexto a completar.

    Returns:
        Exit code (0 OK, 1 rechazado).
    """
    contexto = leer_contexto(contexto_path)
    sha_release = contexto["cod_sha_release"]
    huella_release = {
        ruta: hash_de_ruta(token=token, repo=repo, sha=sha_release, ruta=ruta)
        for ruta in RUTAS_IMAGEN_PORTAL
    }
    descartes: list[str] = []
    elegida: dict[str, Any] = {}
    for candidata in imagenes_de_version(qa_image=qa_image, version=contexto["cod_version"]):
        estado, commit = api(
            token=token,
            method="GET",
            ruta=f"/repos/{repo}/commits/{candidata['sha_corto']}",
            payload=None,
        )
        if estado != 200 or not isinstance(commit, dict):
            descartes.append(f"{candidata['tag']}: el commit ya no existe en el repo")
            continue
        sha_qa = commit["sha"]
        qa = estado_qa(token=token, repo=repo, sha=sha_qa)
        if qa.get("est_resultado") != "success":
            descartes.append(f"{candidata['tag']}: sin commit status '{CONTEXTO_QA}' exitoso")
            continue
        distintas = [
            ruta
            for ruta in RUTAS_IMAGEN_PORTAL
            if hash_de_ruta(token=token, repo=repo, sha=sha_qa, ruta=ruta) != huella_release[ruta]
        ]
        if distintas:
            descartes.append(f"{candidata['tag']}: difiere del release en {distintas}")
            continue
        elegida = {"tag": candidata["tag"], "sha": sha_qa, "qa": qa}
        break

    if not elegida:
        detalle = "; ".join(descartes) if descartes else "no hay imágenes con ese tag en QA"
        return _rechazar_qa(
            contexto_path=contexto_path,
            contexto=contexto,
            motivo=f"No hay un deploy_qa exitoso del portal con el código del release ({detalle}). "
            "Correr deploy_qa sobre la rama con el código final.",
        )

    contexto["qa"] = {
        "cod_sha_probado": elegida["sha"],
        "des_url_ejecucion": elegida["qa"].get("des_url_ejecucion", ""),
        "fec_ejecucion": elegida["qa"].get("fec_ejecucion", ""),
    }
    contexto["cod_tag_imagen_qa"] = elegida["tag"]
    escribir_contexto(contexto_path, contexto)
    salida_github("qa_tag", elegida["tag"])
    return 0


def validar_qa_app(
    huella_release: str, qa_catalogo_uri: str, bucket_uri: str, contexto_path: str
) -> int:
    """C4 de una app: lo que va a PRD tiene la misma huella que lo validado en QA.

    En un Rollback, el catálogo de QA suele tener una versión más nueva: basta con que la
    huella del release haya tenido un pase exitoso anterior en la bitácora.

    Args:
        huella_release: Huella calculada sobre la rama release.
        qa_catalogo_uri: URI gs:// de la entrada de catálogo de QA de la app.
        bucket_uri: Prefijo gs:// de la bitácora; vacío desactiva el camino de Rollback.
        contexto_path: Archivo de contexto a completar.

    Returns:
        Exit code (0 OK, 1 rechazado).
    """
    contexto = leer_contexto(contexto_path)
    contexto["cod_huella"] = huella_release
    entrada_qa = leer_gcs_json(qa_catalogo_uri) or {}
    if entrada_qa.get("huella") == huella_release:
        contexto["qa"] = {
            "cod_sha_probado": entrada_qa.get("sha_commit", ""),
            "fec_ejecucion": entrada_qa.get("publicado_en", ""),
            "des_publicado_por": entrada_qa.get("publicado_por", ""),
            "des_origen": "catalogo_qa",
        }
        escribir_contexto(contexto_path, contexto)
        return 0

    if contexto.get("tip_cambio") == "Rollback" and bucket_uri:
        carpeta = carpeta_bitacora(ruta=contexto["des_ruta_unidad"])
        for uri in reversed(pases_exitosos(bucket_uri=bucket_uri, carpeta=carpeta)):
            pase = leer_gcs_json(uri) or {}
            if (pase.get("artefacto") or {}).get("cod_huella") == huella_release:
                contexto["qa"] = {
                    "cod_sha_probado": (pase.get("qa") or {}).get("cod_sha_probado", ""),
                    "fec_ejecucion": (pase.get("qa") or {}).get("fec_ejecucion", ""),
                    "des_origen": f"pase_previo:{uri}",
                }
                escribir_contexto(contexto_path, contexto)
                return 0

    return _rechazar_qa(
        contexto_path=contexto_path,
        contexto=contexto,
        motivo=f"La app en la rama release (huella {huella_release[:12]}) no coincide con la "
        f"publicada en QA (huella {str(entrada_qa.get('huella', 'ninguna'))[:12]}). "
        "Correr deploy_qa sobre el código final (o, si solo cambiaron accesos, verificar que "
        "el merge sincronizó QA).",
    )


def pase_anterior(bucket_uri: str, ruta: str) -> dict[str, Any]:
    """Lee el último pase exitoso registrado de la unidad.

    Args:
        bucket_uri: Prefijo gs:// de la bitácora.
        ruta: Unidad desplegada.

    Returns:
        El JSON del último pase exitoso, o un dict vacío si es el primero.
    """
    exitosos = pases_exitosos(bucket_uri=bucket_uri, carpeta=carpeta_bitacora(ruta=ruta))
    if not exitosos:
        return {}
    return leer_gcs_json(exitosos[-1]) or {}


def pull_requests_incluidos(
    token: str, repo: str, repo_dir: str, ruta: str, sha_release: str, sha_anterior: str
) -> list[dict[str, Any]]:
    """Reconstruye las PRs que entraron a la unidad desde el release anterior.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        repo_dir: Checkout de main con el historial completo.
        ruta: Carpeta de la unidad.
        sha_release: Commit de la rama release.
        sha_anterior: Commit del release anterior, o cadena vacía en el primer pase.

    Returns:
        PRs con autor, aprobaciones, merge y su propio QA.
    """
    rango = f"{sha_anterior}..{sha_release}" if sha_anterior else sha_release
    commits = git(
        repo_dir, ["log", "--first-parent", "--format=%H", rango, "--", ruta]
    ).splitlines()
    cache: dict[str, dict[str, str]] = {}
    vistos: set[int] = set()
    resultado: list[dict[str, Any]] = []
    for sha in commits:
        estado, cuerpo = api(
            token=token, method="GET", ruta=f"/repos/{repo}/commits/{sha}/pulls", payload=None
        )
        if estado != 200 or not isinstance(cuerpo, list):
            continue
        for pr in cuerpo:
            numero = pr.get("number")
            if numero in vistos:
                continue
            vistos.add(numero)
            _, revisiones = api(
                token=token,
                method="GET",
                ruta=f"/repos/{repo}/pulls/{numero}/reviews",
                payload=None,
            )
            aprobaciones = [
                {
                    **persona(token=token, login=revision["user"]["login"], cache=cache),
                    "fec_aprobacion": a_hora_local(revision.get("submitted_at", "")),
                }
                for revision in (revisiones if isinstance(revisiones, list) else [])
                if revision.get("state") == "APPROVED"
            ]
            resultado.append(
                {
                    "num_pull_request": numero,
                    "des_titulo": pr.get("title", ""),
                    "autor": persona(token=token, login=pr["user"]["login"], cache=cache),
                    "aprobaciones": aprobaciones,
                    "fec_merge": a_hora_local(pr.get("merged_at", "")),
                    "qa_propio": estado_qa(token=token, repo=repo, sha=pr["head"]["sha"]),
                }
            )
    return resultado


def resolver_estado(estado_validacion: str, estado_qa_control: str, estado_job: str) -> str:
    """Traduce los resultados de los steps al estado del pase.

    Args:
        estado_validacion: Outcome del step de C2.
        estado_qa_control: Outcome del step de C4.
        estado_job: Estado del job al momento de registrar.

    Returns:
        exitoso, rechazado, fallido o cancelado.
    """
    if estado_validacion != "success" or estado_qa_control != "success":
        return "rechazado"
    if estado_job == "success":
        return "exitoso"
    if estado_job == "cancelled":
        return "cancelado"
    return "fallido"


def leer_diff_accesos(ruta_archivo: str) -> dict[str, Any] | None:
    """Lee el diff de accesos que dejó publicar_app.py, si existe.

    Args:
        ruta_archivo: Ruta del JSON, o cadena vacía.

    Returns:
        El diff, o None si no aplica.
    """
    if not ruta_archivo or not Path(ruta_archivo).exists():
        return None
    return json.loads(Path(ruta_archivo).read_text(encoding="utf-8"))


def registrar(
    token: str,
    repo: str,
    server_url: str,
    repo_dir: str,
    contexto_path: str,
    bucket_uri: str,
    run_id: str,
    run_attempt: str,
    ejecutor: str,
    estado_validacion: str,
    estado_qa_control: str,
    estado_job: str,
    fec_inicio: str,
    imagen_prd: str,
    imagen_digest: str,
    objetos: str,
    diff_accesos_path: str,
) -> int:
    """Escribe el JSON de evidencia en GCS y cierra la solicitud si el pase fue exitoso.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        server_url: URL base de GitHub.
        repo_dir: Checkout de main con el historial completo.
        contexto_path: Archivo de contexto dejado por los controles.
        bucket_uri: Prefijo gs:// de la bitácora; vacío desactiva la bitácora.
        run_id: ID de la ejecución de Actions.
        run_attempt: Intento de la ejecución.
        ejecutor: Usuario que lanzó el pase.
        estado_validacion: Outcome del step de C2.
        estado_qa_control: Outcome del step de C4.
        estado_job: Estado del job al momento de registrar.
        fec_inicio: Marca de inicio del job.
        imagen_prd: URI de la imagen promovida (portal), vacío si no aplica.
        imagen_digest: Digest de la imagen promovida (portal), vacío si no aplica.
        objetos: Objetos publicados en el bucket (app), separados por coma; vacío si no aplica.
        diff_accesos_path: JSON con el diff de accesos (app), o cadena vacía.

    Returns:
        Exit code (0 si la evidencia quedó escrita).
    """
    contexto = leer_contexto(contexto_path)
    estado = resolver_estado(
        estado_validacion=estado_validacion,
        estado_qa_control=estado_qa_control,
        estado_job=estado_job,
    )
    cache: dict[str, dict[str, str]] = {}
    ruta = contexto.get("des_ruta_unidad", "")
    version = contexto.get("cod_version", "")
    anterior = pase_anterior(bucket_uri=bucket_uri, ruta=ruta) if ruta and bucket_uri else {}
    release_anterior = anterior.get("release", {})

    pull_requests: list[dict[str, Any]] = []
    if contexto.get("cod_sha_release"):
        pull_requests = pull_requests_incluidos(
            token=token,
            repo=repo,
            repo_dir=repo_dir,
            ruta=ruta,
            sha_release=contexto["cod_sha_release"],
            sha_anterior=release_anterior.get("cod_sha_release", ""),
        )

    evidencia = {
        "id_ejecucion": f"{run_id}-{run_attempt}",
        "tip_origen": "workflow",
        "est_resultado": estado,
        "des_motivo_resultado": contexto.get("des_motivo_resultado"),
        "fec_registro": ahora(),
        "solicitud": {
            "cod_solicitud": contexto.get("cod_solicitud", ""),
            "des_url_solicitud": contexto.get("des_url_solicitud", ""),
            "tip_cambio": contexto.get("tip_cambio", ""),
            "des_cambio": contexto.get("des_cambio", ""),
            "des_area_negocio": contexto.get("des_area_negocio", ""),
            "fec_solicitud": contexto.get("fec_solicitud", ""),
            "solicitante": contexto.get("solicitante"),
            "lt_asignado": contexto.get("lt_asignado"),
        },
        "release": {
            "des_ruta_unidad": ruta,
            "tip_unidad": contexto.get("tip_unidad", ""),
            "cod_version": version,
            "cod_version_anterior": release_anterior.get("cod_version", ""),
            "nom_rama_release": contexto.get("nom_rama_release", ""),
            "cod_sha_release": contexto.get("cod_sha_release", ""),
            "cod_sha_release_anterior": release_anterior.get("cod_sha_release", ""),
        },
        "qa": contexto.get("qa"),
        "artefacto": {
            "cod_tag_origen_qa": contexto.get("cod_tag_imagen_qa", ""),
            "des_uri_imagen_prd": imagen_prd,
            "cod_digest": imagen_digest,
            "cod_huella": contexto.get("cod_huella", ""),
            "des_objetos": [objeto for objeto in objetos.split(",") if objeto],
        },
        "diff_accesos": leer_diff_accesos(ruta_archivo=diff_accesos_path),
        "ejecucion": {
            "ejecutor": persona(token=token, login=ejecutor, cache=cache),
            "fec_inicio": a_hora_local(fec_inicio),
            "fec_fin": ahora(),
            "des_url_ejecucion": f"{server_url}/{repo}/actions/runs/{run_id}",
        },
        "pull_requests": pull_requests,
        "controles": [
            {
                "cod_control": "C1",
                "est_resultado": "ok",
                "des_detalle": f"{ejecutor} ∈ PRD_APPROVERS",
            },
            {"cod_control": "C2", "est_resultado": estado_validacion, "des_detalle": "Solicitud"},
            {
                "cod_control": "C3",
                "est_resultado": estado_job if estado_validacion == "success" else "skipped",
                "des_detalle": "Versión declarada en portal.yaml o app.yaml",
            },
            {
                "cod_control": "C4",
                "est_resultado": estado_qa_control,
                "des_detalle": "Lo desplegado es lo validado en QA",
            },
        ],
    }

    local = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "evidencia_pase.json"
    local.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
    if bucket_uri:
        # El nombre ordena la carpeta cronológicamente y deja el resultado a la vista.
        marca = datetime.now(tz=ZONA).strftime("%Y%m%d-%H%M%S")
        carpeta = carpeta_bitacora(ruta=ruta) if ruta else "_sin_unidad"
        destino = (
            f"{bucket_uri.rstrip('/')}/{carpeta}/{marca}_{version or 'desconocida'}_{estado}.json"
        )
        gcloud(["storage", "cp", str(local), destino])
        sys.stdout.write(f"Bitácora escrita en {destino}\n")
    else:
        # Sin BITACORA_URI_PRD (por ejemplo, en un MVP) la evidencia solo queda en el issue.
        destino = ""
        sys.stdout.write("::notice::Bitácora desactivada: BITACORA_URI_PRD está vacía.\n")

    issue_number = contexto.get("cod_solicitud", "")
    if issue_number and not comentar_solicitud(
        token=token, repo=repo, issue_number=issue_number, evidencia=evidencia, destino=destino
    ):
        sys.stderr.write("::warning::No se pudo comentar la solicitud.\n")
    return 0


def comentar_solicitud(
    token: str, repo: str, issue_number: str, evidencia: dict[str, Any], destino: str
) -> bool:
    """Comenta el resultado en la solicitud y la cierra si el pase fue exitoso.

    Args:
        token: Token de la ejecución.
        repo: Repositorio owner/name.
        issue_number: Número del issue.
        evidencia: JSON de evidencia ya armado.
        destino: Ruta gs:// donde quedó la evidencia, o vacío si la bitácora está desactivada.

    Returns:
        True si el comentario se publicó.
    """
    estado = evidencia["est_resultado"]
    icono = {"exitoso": "✅", "rechazado": "⛔", "fallido": "❌", "cancelado": "⚪"}[estado]
    release = evidencia["release"]
    artefacto = evidencia["artefacto"]
    lineas = [
        f"### {icono} Pase a producción: **{estado.upper()}**",
        "",
        f"- **Unidad:** `{release['des_ruta_unidad']}`",
        f"- **Versión:** `{release['cod_version']}` "
        f"(anterior: `{release['cod_version_anterior'] or 'ninguna'}`)",
        f"- **Commit del release:** `{release['cod_sha_release'][:7]}`",
    ]
    if release["tip_unidad"] == "portal":
        lineas.append(f"- **Imagen:** `{artefacto['des_uri_imagen_prd'] or 'no promovida'}`")
    else:
        lineas.append(f"- **Huella:** `{artefacto['cod_huella'][:12] or 'no calculada'}`")
        diff = evidencia.get("diff_accesos") or {}
        if diff:
            lineas.append(
                f"- **Accesos:** +{len(diff.get('agregados', []))} / "
                f"-{len(diff.get('quitados', []))}"
            )
    lineas += [
        f"- **Ejecutado por:** @{evidencia['ejecucion']['ejecutor']['nom_usuario_github']}",
        f"- **Run:** {evidencia['ejecucion']['des_url_ejecucion']}",
        f"- **Evidencia:** `{destino or 'bitácora desactivada'}`",
    ]
    if evidencia.get("des_motivo_resultado"):
        lineas += ["", f"**Motivo:** {evidencia['des_motivo_resultado']}"]
    codigo, _ = api(
        token=token,
        method="POST",
        ruta=f"/repos/{repo}/issues/{issue_number}/comments",
        payload={"body": "\n".join(lineas)},
    )
    if estado == "exitoso":
        api(
            token=token,
            method="PATCH",
            ruta=f"/repos/{repo}/issues/{issue_number}",
            payload={"state": "closed", "state_reason": "completed"},
        )
    return codigo == 201


def construir_parser() -> argparse.ArgumentParser:
    """Arma el parser con los subcomandos del script."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    solicitud = sub.add_parser("validar-solicitud")
    solicitud.add_argument("--repo", required=True)
    solicitud.add_argument("--server-url", required=True)
    solicitud.add_argument("--issue-number", required=True)
    solicitud.add_argument("--repo-dir", required=True)
    solicitud.add_argument("--contexto", required=True)

    qa_portal = sub.add_parser("validar-qa-portal")
    qa_portal.add_argument("--repo", required=True)
    qa_portal.add_argument("--qa-image", required=True)
    qa_portal.add_argument("--contexto", required=True)

    qa_app = sub.add_parser("validar-qa-app")
    qa_app.add_argument("--huella-release", required=True)
    qa_app.add_argument("--qa-catalogo-uri", required=True)
    qa_app.add_argument("--bucket-uri", required=True)
    qa_app.add_argument("--contexto", required=True)

    bitacora = sub.add_parser("registrar")
    for nombre in (
        "--repo",
        "--server-url",
        "--repo-dir",
        "--contexto",
        "--bucket-uri",
        "--run-id",
        "--run-attempt",
        "--ejecutor",
        "--estado-validacion",
        "--estado-qa",
        "--estado-job",
        "--fec-inicio",
        "--imagen-prd",
        "--imagen-digest",
        "--objetos",
        "--diff-accesos",
    ):
        bitacora.add_argument(nombre, required=True)
    return parser


if __name__ == "__main__":
    args = construir_parser().parse_args()
    if args.comando == "validar-qa-app":
        sys.exit(
            validar_qa_app(
                huella_release=args.huella_release,
                qa_catalogo_uri=args.qa_catalogo_uri,
                bucket_uri=args.bucket_uri,
                contexto_path=args.contexto,
            )
        )
    gh_token = os.environ["GH_TOKEN"]
    if args.comando == "validar-solicitud":
        sys.exit(
            validar_solicitud(
                token=gh_token,
                repo=args.repo,
                server_url=args.server_url,
                issue_number=args.issue_number,
                repo_dir=args.repo_dir,
                contexto_path=args.contexto,
            )
        )
    if args.comando == "validar-qa-portal":
        sys.exit(
            validar_qa_portal(
                token=gh_token, repo=args.repo, qa_image=args.qa_image, contexto_path=args.contexto
            )
        )
    sys.exit(
        registrar(
            token=gh_token,
            repo=args.repo,
            server_url=args.server_url,
            repo_dir=args.repo_dir,
            contexto_path=args.contexto,
            bucket_uri=args.bucket_uri,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            ejecutor=args.ejecutor,
            estado_validacion=args.estado_validacion,
            estado_qa_control=args.estado_qa,
            estado_job=args.estado_job,
            fec_inicio=args.fec_inicio,
            imagen_prd=args.imagen_prd,
            imagen_digest=args.imagen_digest,
            objetos=args.objetos,
            diff_accesos_path=args.diff_accesos,
        )
    )
