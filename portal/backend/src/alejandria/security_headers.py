"""Cabeceras de seguridad del portal y del endpoint de contenido.

La CSP del portal se hereda en el iframe del visor (el HTML se carga como Blob creado por
el portal). Por eso incluye lo que necesitan los HTML publicados:
  - 'unsafe-inline' / 'unsafe-eval' en scripts: los HTML traen scripts inline y librerías
    como Plotly o Vega usan evaluación dinámica. El aislamiento real lo da el sandbox del
    iframe (origen opaco), no esta directiva.
  - La lista blanca de mapas y CDN: cualquier otro dominio queda bloqueado.
"""

from alejandria.settings import CspAllowlist

# Endpoints de Identity Platform que usa el SDK web del propio portal.
IDENTITY_ORIGINS = (
    "https://identitytoolkit.googleapis.com",
    "https://securetoken.googleapis.com",
)

# CSP del endpoint de contenido: si alguien abre la URL directamente en el navegador,
# el HTML queda aislado y sin scripts.
CONTENT_CSP = "sandbox"


def build_portal_csp(csp: CspAllowlist) -> str:
    """Arma la Content-Security-Policy de las páginas del portal.

    Args:
        csp: Lista blanca de dominios externos.

    Returns:
        El valor de la cabecera Content-Security-Policy.
    """
    maps = " ".join(csp.maps)
    cdn = " ".join(csp.cdn)
    identity = " ".join(IDENTITY_ORIGINS)
    directives = [
        "default-src 'self'",
        f"script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: {cdn}",
        f"style-src 'self' 'unsafe-inline' {cdn}",
        f"font-src 'self' data: {cdn}",
        f"img-src 'self' data: blob: {maps} {cdn}",
        f"connect-src 'self' {identity} {maps} {cdn}",
        "frame-src blob:",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(" ".join(directive.split()) for directive in directives)


def common_headers() -> dict[str, str]:
    """Cabeceras de seguridad que llevan todas las respuestas.

    Returns:
        Mapa cabecera -> valor.
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Frame-Options": "DENY",
    }
