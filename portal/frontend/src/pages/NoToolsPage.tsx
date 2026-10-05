import { FullScreenMessage } from "@/components/FullScreenMessage";
import { useConfig } from "@/context/ConfigContext";

/** Página estática para quien ingresó pero no tiene herramientas habilitadas. */

export function NoToolsPage() {
  const config = useConfig();
  return (
    <FullScreenMessage
      title="Aún no tienes herramientas habilitadas"
      message={config.portal.contacto}
    />
  );
}
