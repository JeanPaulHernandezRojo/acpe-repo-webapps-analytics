import type { LoginEventType, Me, PublicConfig, ViewerEvent } from "@/types";

/** Cliente de la API del portal. Todas las llamadas son al mismo origen, con la cookie de sesión. */

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`HTTP ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

/** Cabecera que exige el endpoint de contenido: solo el visor la envía. */
const VIEWER_HEADER = "X-Alejandria-Visor";

async function errorFrom(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return new ApiError(response.status, typeof body.detail === "string" ? body.detail : "");
  } catch {
    return new ApiError(response.status, "");
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as T;
}

async function requestEmpty(path: string, init: RequestInit): Promise<void> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (!response.ok) throw await errorFrom(response);
}

function jsonPost(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function getPublicConfig(): Promise<PublicConfig> {
  return requestJson<PublicConfig>("/api/configuracion", { method: "GET" });
}

export function getMe(): Promise<Me> {
  return requestJson<Me>("/api/yo", { method: "GET" });
}

export function createSession(idToken: string): Promise<{ tiene_apps: boolean }> {
  return requestJson<{ tiene_apps: boolean }>("/api/sesion", jsonPost({ id_token: idToken }));
}

export function reportLoginEvent(tipo: LoginEventType, correo: string): Promise<void> {
  return requestEmpty("/api/ingreso/evento", jsonPost({ tipo, correo }));
}

export interface AppContent {
  html: string;
  generation: string | null;
}

export async function fetchAppContent(dominio: string, appId: string): Promise<AppContent> {
  const path = `/api/apps/${encodeURIComponent(dominio)}/${encodeURIComponent(appId)}/contenido`;
  const response = await fetch(path, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { [VIEWER_HEADER]: "1" },
  });
  if (!response.ok) throw await errorFrom(response);
  return { html: await response.text(), generation: response.headers.get("X-Generacion-Html") };
}

export function reportViewerEvent(event: ViewerEvent): Promise<void> {
  return requestEmpty("/api/eventos", jsonPost(event));
}

/** Envío que sobrevive al cierre de la pestaña (para app_cerrada). */
export function beaconViewerEvent(event: ViewerEvent): void {
  const body = new Blob([JSON.stringify(event)], { type: "application/json" });
  if (!navigator.sendBeacon("/api/eventos", body)) {
    void reportViewerEvent(event).catch(() => undefined);
  }
}
