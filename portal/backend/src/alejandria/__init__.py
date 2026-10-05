"""Backend del portal ALEJANDRÍA: repositorio centralizado de herramientas analíticas.

El backend autentica (sesión de Identity Platform), autoriza por app según el catálogo
publicado en GCS, entrega el HTML de cada herramienta y registra eventos de auditoría.
Nunca modifica el contenido de los HTML.
"""
