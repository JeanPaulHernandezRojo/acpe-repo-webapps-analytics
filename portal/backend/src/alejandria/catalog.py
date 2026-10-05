"""Catálogo de apps publicado en `<prefijo>/_catalogo/<dominio>/<app>.json`.

Cada entrada la escribe el workflow de despliegue (`scripts/publicar_app.py`) y trae ya
resuelta la lista de accesos del ambiente. El backend solo la lee, con caché por TTL.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from alejandria.storage import ObjectStore

logger = logging.getLogger(__name__)

CATALOG_FOLDER = "_catalogo"

CAPABILITIES = ("descargas", "ventanas", "dialogos", "formularios")
WATERMARK_LEVELS = ("patron_suave", "esquina", "franja", "patron")


@dataclass(frozen=True)
class AppCard:
    """Datos visibles de la tarjeta de una app.

    Attributes:
        title: Título.
        description: Descripción corta.
        icon: Nombre del ícono lucide.
        tag: Texto de la esquina de la tarjeta.
    """

    title: str
    description: str
    icon: str
    tag: str


@dataclass(frozen=True)
class AppEntry:
    """Entrada de catálogo de una app, para el ambiente actual.

    Attributes:
        app_id: Identificador de la app.
        domain: Dominio de la app.
        version: Versión CalVer publicada.
        app_type: 'pipeline' o 'herramienta'.
        card: Datos de la tarjeta.
        access: Correos con acceso en el ambiente.
        capabilities: Capacidades del iframe, ya resueltas.
        watermark: Nivel de marca de agua.
        labels: Labels de la app para la auditoría.
        fingerprint: Huella de contenido publicada.
    """

    app_id: str
    domain: str
    version: str
    app_type: str
    card: AppCard
    access: frozenset[str]
    capabilities: dict[str, bool]
    watermark: str
    labels: dict[str, str]
    fingerprint: str


def parse_entry(raw: dict) -> AppEntry:
    """Convierte el JSON publicado en una entrada validada.

    Args:
        raw: Contenido de la entrada de catálogo.

    Returns:
        La entrada validada.

    Raises:
        ValueError: si la entrada no cumple el contrato.
    """
    card = raw.get("tarjeta") or {}
    capabilities = raw.get("capacidades") or {}
    unknown = sorted(set(capabilities) - set(CAPABILITIES))
    if unknown:
        raise ValueError(f"Capacidades desconocidas: {unknown}")
    watermark = str(raw.get("marca_agua", ""))
    if watermark not in WATERMARK_LEVELS:
        raise ValueError(f"marca_agua inválida: {watermark!r}")
    required = ("id", "dominio", "version", "tipo", "huella")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"Entrada de catálogo sin {missing}")
    return AppEntry(
        app_id=str(raw["id"]),
        domain=str(raw["dominio"]),
        version=str(raw["version"]),
        app_type=str(raw["tipo"]),
        card=AppCard(
            title=str(card["titulo"]),
            description=str(card["descripcion"]),
            icon=str(card["icono"]),
            tag=str(card["etiqueta"]),
        ),
        access=frozenset(str(email) for email in raw.get("acceso") or []),
        capabilities={name: bool(capabilities.get(name, True)) for name in CAPABILITIES},
        watermark=watermark,
        labels={str(k): str(v) for k, v in (raw.get("labels") or {}).items()},
        fingerprint=str(raw["huella"]),
    )


class CatalogStore:
    """Lee y cachea el catálogo del ambiente."""

    def __init__(
        self,
        object_store: ObjectStore,
        bucket_prefix: str,
        ttl_seconds: int,
        clock: Callable[[], float],
    ):
        """Inicializa el catálogo.

        Args:
            object_store: Acceso al bucket.
            bucket_prefix: Carpeta del ambiente dentro del bucket (qa o prd).
            ttl_seconds: Segundos que se reutiliza el catálogo leído.
            clock: Reloj monotónico (inyectable para tests).
        """
        self._store = object_store
        self._prefix = f"{bucket_prefix}/{CATALOG_FOLDER}/"
        self._ttl = ttl_seconds
        self._clock = clock
        self._cached: list[AppEntry] = []
        self._loaded_at: float | None = None

    def entries(self) -> list[AppEntry]:
        """Devuelve las entradas vigentes, releyendo el bucket si venció el TTL.

        Una entrada mal formada se descarta y se registra: no debe tumbar el catálogo
        completo ni dejar sin acceso a los usuarios de las demás apps.

        Returns:
            Entradas válidas del catálogo.
        """
        now = self._clock()
        if self._loaded_at is not None and now - self._loaded_at < self._ttl:
            return self._cached
        entries: list[AppEntry] = []
        for name in self._store.list_objects(prefix=self._prefix):
            if not name.endswith(".json"):
                continue
            obj = self._store.read(name=name)
            if obj is None:
                continue
            try:
                entries.append(parse_entry(raw=json.loads(obj.data)))
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                logger.error("Entrada de catálogo inválida %s: %s", name, error)
        self._cached = sorted(entries, key=lambda e: (e.card.title.lower(), e.app_id))
        self._loaded_at = now
        return self._cached
