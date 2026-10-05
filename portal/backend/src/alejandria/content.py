"""Entrega del HTML de cada app desde `<prefijo>/<dominio>/<app>/index.html`.

El portal consulta la generación del objeto en cada apertura y solo vuelve a descargarlo
si cambió (por ejemplo, porque el pipeline lo sobrescribió). La versión comprimida (gzip)
queda en memoria. El HTML se entrega tal cual: la compresión es solo de transporte.
"""

import gzip
import threading
from dataclasses import dataclass

from alejandria.storage import ObjectStore

INDEX_FILE = "index.html"

# Nivel intermedio: buena compresión para HTML con datos JSON sin costo de CPU relevante.
GZIP_LEVEL = 6


@dataclass(frozen=True)
class AppContent:
    """HTML comprimido de una app.

    Attributes:
        gzipped: Bytes del HTML comprimidos con gzip.
        generation: Generación de GCS del objeto servido.
    """

    gzipped: bytes
    generation: int


class ContentStore:
    """Lee el HTML vigente de cada app con caché por generación."""

    def __init__(self, object_store: ObjectStore, bucket_prefix: str):
        """Inicializa el almacén de contenido.

        Args:
            object_store: Acceso al bucket.
            bucket_prefix: Carpeta del ambiente dentro del bucket (qa o prd).
        """
        self._store = object_store
        self._prefix = bucket_prefix
        self._cache: dict[str, AppContent] = {}
        self._lock = threading.Lock()

    def object_name(self, domain: str, app_id: str) -> str:
        """Nombre del objeto `index.html` de una app.

        Args:
            domain: Dominio de la app.
            app_id: Identificador de la app.

        Returns:
            Nombre completo del objeto en el bucket.
        """
        return f"{self._prefix}/{domain}/{app_id}/{INDEX_FILE}"

    def get(self, domain: str, app_id: str) -> AppContent | None:
        """Devuelve el HTML vigente comprimido, o None si aún no se publicó.

        Args:
            domain: Dominio de la app.
            app_id: Identificador de la app.

        Returns:
            El contenido comprimido con su generación, o None si no existe.
        """
        name = self.object_name(domain=domain, app_id=app_id)
        generation = self._store.get_generation(name=name)
        if generation is None:
            return None
        with self._lock:
            cached = self._cache.get(name)
        if cached is not None and cached.generation == generation:
            return cached
        obj = self._store.read(name=name)
        if obj is None:
            return None
        content = AppContent(
            gzipped=gzip.compress(obj.data, compresslevel=GZIP_LEVEL), generation=obj.generation
        )
        with self._lock:
            self._cache[name] = content
        return content
