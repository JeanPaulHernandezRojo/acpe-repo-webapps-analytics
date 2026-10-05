import { useEffect, useState, type ReactNode } from "react";
import { FullScreenMessage } from "@/components/FullScreenMessage";
import { ConfigContext } from "@/context/ConfigContext";
import { getPublicConfig } from "@/lib/api";
import type { PublicConfig } from "@/types";

/** Carga una vez la configuración pública y la entrega al resto del portal. */

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getPublicConfig()
      .then((value) => {
        setConfig(value);
        document.title = `${value.portal.nombre} · ${value.portal.subtitulo}`;
      })
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <FullScreenMessage
        title="No pudimos cargar el portal"
        message="Revisa tu conexión y vuelve a intentarlo en unos minutos."
      />
    );
  }
  if (!config) return <FullScreenMessage title="Cargando…" message="" />;
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>;
}
