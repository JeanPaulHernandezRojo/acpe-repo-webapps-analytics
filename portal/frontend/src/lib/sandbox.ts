import type { Capabilities } from "@/types";

/**
 * Traduce las capacidades de una app (app.yaml) a los permisos del atributo sandbox del iframe.
 * El HTML no se modifica: todo se controla desde el iframe que crea el portal.
 */

/** Permiso base: sin scripts el HTML no funciona. */
export const BASE_TOKEN = "allow-scripts";

export const CAPABILITY_TOKENS: Record<keyof Capabilities, string> = {
  descargas: "allow-downloads",
  ventanas: "allow-popups",
  dialogos: "allow-modals",
  formularios: "allow-forms",
};

/**
 * Permisos que nunca se otorgan porque romperían el aislamiento:
 * - allow-same-origin: con scripts, el HTML podría quitarse el sandbox y usar la sesión.
 * - allow-top-navigation*: el HTML podría redirigir el portal completo a otro sitio.
 * - allow-popups-to-escape-sandbox: las ventanas abiertas quedarían sin aislamiento.
 */
export const FORBIDDEN_TOKENS = [
  "allow-same-origin",
  "allow-top-navigation",
  "allow-top-navigation-by-user-activation",
  "allow-top-navigation-to-custom-protocols",
  "allow-popups-to-escape-sandbox",
] as const;

export function sandboxTokens(capabilities: Capabilities): string[] {
  const tokens = [BASE_TOKEN];
  for (const [capability, token] of Object.entries(CAPABILITY_TOKENS)) {
    if (capabilities[capability as keyof Capabilities]) tokens.push(token);
  }
  return tokens;
}
