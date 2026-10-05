"""Lectura y escritura de objetos en el bucket de webapps desde los workflows.

Usa las credenciales que deja `google-github-actions/auth` (Workload Identity Federation).
"""

import json
from typing import Any

from google.cloud import storage


def open_bucket(bucket_name: str, project: str) -> storage.Bucket:
    """Abre un bucket con las credenciales del workflow.

    Args:
        bucket_name: Nombre del bucket.
        project: Proyecto que factura las operaciones.

    Returns:
        El bucket.
    """
    return storage.Client(project=project).bucket(bucket_name)


def read_json(bucket: storage.Bucket, name: str) -> dict[str, Any] | None:
    """Lee un objeto JSON.

    Args:
        bucket: Bucket de webapps.
        name: Nombre del objeto.

    Returns:
        El contenido, o None si el objeto no existe.
    """
    blob = bucket.get_blob(name)
    if blob is None:
        return None
    return json.loads(blob.download_as_bytes())


def upload(
    bucket: storage.Bucket,
    name: str,
    data: bytes,
    content_type: str,
    metadata: dict[str, str],
) -> None:
    """Sube un objeto con tipo de contenido y metadatos.

    Args:
        bucket: Bucket de webapps.
        name: Nombre del objeto.
        data: Contenido.
        content_type: Tipo MIME.
        metadata: Metadatos personalizados (sha, huella, versión).
    """
    blob = bucket.blob(name)
    blob.metadata = metadata
    # Sin caché intermedia: el portal siempre debe leer la última versión publicada.
    blob.cache_control = "no-store"
    blob.upload_from_string(data, content_type=content_type)
