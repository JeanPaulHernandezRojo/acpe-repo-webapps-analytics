"""Eventos de auditoría como JSON estructurado en stdout.

Cloud Logging interpreta cada línea JSON de stdout como un log estructurado (`jsonPayload`).
Un sink envía los que tienen `tipo_registro = "auditoria"` al dataset
`monitoreo__portal_webapps`, de donde los toman los pipelines de monitoreo.
"""

import json
import threading
from datetime import UTC, datetime
from typing import Any, TextIO

RECORD_TYPE = "auditoria"

EVENT_TYPES = frozenset(
    {
        "enlace_solicitado",
        "enlace_rechazado_politica",
        "login_ok",
        "login_rechazado",
        "sin_apps",
        "app_abierta",
        "latido",
        "app_cerrada",
        "acceso_denegado",
        "limite_excedido",
        "sesion_expirada",
    }
)

# Eventos que indican un intento rechazado: se registran con severidad WARNING.
_WARNING_EVENTS = frozenset(
    {"enlace_rechazado_politica", "login_rechazado", "acceso_denegado", "limite_excedido"}
)


class AuditLogger:
    """Escribe eventos de auditoría con un esquema fijo."""

    def __init__(self, stream: TextIO, environment: str, portal_version: str):
        """Inicializa el registrador.

        Args:
            stream: Destino de las líneas JSON (sys.stdout en producción).
            environment: Ambiente (qa o prd).
            portal_version: Versión CalVer del portal.
        """
        self._stream = stream
        self._environment = environment
        self._portal_version = portal_version
        self._lock = threading.Lock()

    def emit(self, event_type: str, fields: dict[str, Any]) -> None:
        """Registra un evento.

        Args:
            event_type: Tipo de evento (uno de EVENT_TYPES).
            fields: Campos del evento (correo, app_id, ip, etc.). Los None se omiten.

        Raises:
            ValueError: si el tipo de evento no está en el esquema.
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Tipo de evento de auditoría desconocido: {event_type}")
        record = {
            "severity": "WARNING" if event_type in _WARNING_EVENTS else "INFO",
            "message": event_type,
            "tipo_registro": RECORD_TYPE,
            "tipo_evento": event_type,
            "fecha_evento": datetime.now(tz=UTC).isoformat(timespec="milliseconds"),
            "ambiente": self._environment,
            "version_portal": self._portal_version,
            **{key: value for key, value in fields.items() if value is not None},
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()
