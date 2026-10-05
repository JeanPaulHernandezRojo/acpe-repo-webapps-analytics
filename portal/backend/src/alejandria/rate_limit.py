"""Límite de solicitudes en memoria con ventana deslizante.

Vive en cada instancia de Cloud Run: con pocas instancias el límite efectivo es aproximado,
suficiente para frenar abuso sin depender de Redis ni de una base de datos.
"""

import threading
from collections import deque
from collections.abc import Callable, Mapping

WINDOW_SECONDS = 60

# Cada cuántas llamadas se eliminan las claves sin actividad, para acotar la memoria.
_CLEANUP_EVERY = 1000


class RateLimiter:
    """Limita la cantidad de solicitudes por clave dentro de una ventana."""

    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float]):
        """Inicializa el limitador.

        Args:
            limit: Solicitudes permitidas por clave dentro de la ventana.
            window_seconds: Duración de la ventana en segundos.
            clock: Reloj monotónico (inyectable para tests).
        """
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def allow(self, key: str) -> bool:
        """Registra una solicitud y dice si está dentro del límite.

        Args:
            key: Clave de agrupación (correo o IP).

        Returns:
            True si la solicitud se permite.
        """
        now = self._clock()
        with self._lock:
            self._calls += 1
            if self._calls % _CLEANUP_EVERY == 0:
                self._cleanup(now=now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True

    def _cleanup(self, now: float) -> None:
        """Elimina las claves cuya última solicitud salió de la ventana.

        Args:
            now: Instante actual del reloj.
        """
        stale = [
            key for key, hits in self._hits.items() if not hits or now - hits[-1] >= self._window
        ]
        for key in stale:
            del self._hits[key]


def client_ip(headers: Mapping[str, str], index_from_end: int, fallback: str) -> str:
    """Obtiene la IP del cliente desde X-Forwarded-For.

    Se toma la posición contada desde el final, porque los primeros valores los puede
    enviar el propio cliente y el último lo agrega la infraestructura de Google.

    Args:
        headers: Cabeceras del request.
        index_from_end: Posición desde el final (1 = último valor).
        fallback: IP a usar si la cabecera no existe (dirección del socket).

    Returns:
        La IP del cliente.
    """
    forwarded = headers.get("x-forwarded-for", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) >= index_from_end >= 1:
        return parts[-index_from_end]
    return fallback
