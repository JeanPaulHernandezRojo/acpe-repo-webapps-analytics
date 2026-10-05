import { beaconViewerEvent, reportViewerEvent } from "@/lib/api";
import type { ViewerEvent } from "@/types";

/**
 * Auditoría del visor: apertura, latido (solo con la pestaña visible) y cierre.
 * Los eventos los arma el portal; lo que ocurre dentro del HTML no se registra.
 */

interface TrackingTarget {
  dominio: string;
  appId: string;
  generation: string | null;
}

function event(
  tipo: ViewerEvent["tipo"],
  target: TrackingTarget,
  tiempoCargaMs: number | null,
  duracionS: number | null,
): ViewerEvent {
  return {
    tipo,
    dominio: target.dominio,
    app_id: target.appId,
    tiempo_carga_ms: tiempoCargaMs,
    duracion_s: duracionS,
    generacion_html: target.generation,
  };
}

/**
 * Registra la apertura y programa latidos hasta que se llame a la función devuelta,
 * que envía el cierre. También envía el cierre si se cierra la pestaña.
 */
export function startViewerTracking(
  target: TrackingTarget,
  loadMs: number,
  heartbeatSeconds: number,
): () => void {
  const openedAt = Date.now();
  const elapsed = () => Math.round((Date.now() - openedAt) / 1000);
  let closed = false;

  void reportViewerEvent(event("app_abierta", target, loadMs, null)).catch(() => undefined);

  const timer = window.setInterval(() => {
    if (document.visibilityState === "visible") {
      void reportViewerEvent(event("latido", target, null, elapsed())).catch(() => undefined);
    }
  }, heartbeatSeconds * 1000);

  const close = () => {
    if (closed) return;
    closed = true;
    window.clearInterval(timer);
    window.removeEventListener("pagehide", close);
    beaconViewerEvent(event("app_cerrada", target, null, elapsed()));
  };
  window.addEventListener("pagehide", close);
  return close;
}
