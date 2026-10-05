"""Acceso de solo lectura al bucket de webapps.

El protocolo `ObjectStore` permite probar catálogo y contenido sin GCP; `GcsObjectStore` es
la implementación real con google-cloud-storage y la identidad de la cuenta runtime.
"""

from dataclasses import dataclass
from typing import Protocol

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

# Intentos de lectura consistente (datos + generación) ante sobrescrituras concurrentes.
_READ_ATTEMPTS = 3


@dataclass(frozen=True)
class ObjectData:
    """Contenido de un objeto junto con su generación.

    Attributes:
        data: Bytes del objeto.
        generation: Generación de GCS; cambia en cada sobrescritura.
    """

    data: bytes
    generation: int


class ObjectStore(Protocol):
    """Operaciones de lectura que necesita el portal sobre el bucket."""

    def list_objects(self, prefix: str) -> list[str]:
        """Lista los nombres de objeto bajo un prefijo."""
        ...

    def get_generation(self, name: str) -> int | None:
        """Devuelve la generación vigente de un objeto, o None si no existe."""
        ...

    def read(self, name: str) -> ObjectData | None:
        """Lee un objeto con su generación, o None si no existe."""
        ...


class GcsObjectStore:
    """Implementación de `ObjectStore` sobre Google Cloud Storage."""

    def __init__(self, client: storage.Client, bucket_name: str):
        """Inicializa el acceso al bucket.

        Args:
            client: Cliente de GCS autenticado con la cuenta runtime.
            bucket_name: Nombre del bucket de webapps.
        """
        self._bucket = client.bucket(bucket_name)

    def list_objects(self, prefix: str) -> list[str]:
        """Lista los nombres de objeto bajo un prefijo.

        Args:
            prefix: Prefijo a listar.

        Returns:
            Nombres completos de los objetos.
        """
        return [blob.name for blob in self._bucket.list_blobs(prefix=prefix)]

    def get_generation(self, name: str) -> int | None:
        """Consulta solo los metadatos del objeto para conocer su generación.

        Args:
            name: Nombre completo del objeto.

        Returns:
            La generación, o None si el objeto no existe.
        """
        blob = self._bucket.get_blob(name)
        return None if blob is None else int(blob.generation)

    def read(self, name: str) -> ObjectData | None:
        """Descarga un objeto y su generación.

        Args:
            name: Nombre completo del objeto.

        Returns:
            El contenido con su generación, o None si el objeto no existe.
        """
        # Se descarga fijando la generación leída, para que datos y generación coincidan.
        # Si el pipeline sobrescribe el objeto justo entre ambas llamadas, se reintenta.
        for _ in range(_READ_ATTEMPTS):
            blob = self._bucket.get_blob(name)
            if blob is None:
                return None
            try:
                data = blob.download_as_bytes(if_generation_match=blob.generation)
            except PreconditionFailed:
                continue
            return ObjectData(data=data, generation=int(blob.generation))
        raise RuntimeError(f"El objeto {name} cambió durante {_READ_ATTEMPTS} lecturas seguidas.")
