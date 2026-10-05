import { createContext, useContext } from "react";
import type { PublicConfig } from "@/types";

/** Configuración pública del portal (nombre, política, Identity Platform). */

export const ConfigContext = createContext<PublicConfig | null>(null);

export function useConfig(): PublicConfig {
  const config = useContext(ConfigContext);
  if (!config) throw new Error("useConfig debe usarse dentro de ConfigProvider");
  return config;
}
