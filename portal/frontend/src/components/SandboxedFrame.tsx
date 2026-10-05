import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { ApiError, fetchAppContent } from "@/lib/api";
import { sandboxTokens } from "@/lib/sandbox";
import type { AppSummary } from "@/types";

/**
 * Carga el HTML de una app y lo muestra en un iframe aislado.
 * El HTML se descarga autenticado, se convierte en Blob y se carga sin modificarlo; el iframe
 * no tiene el permiso "mismo origen", así que el HTML no puede leer la sesión del portal.
 */

interface SandboxedFrameProps {
  app: AppSummary;
  onLoaded: (loadMs: number, generation: string | null) => void;
}

type FrameState =
  | { status: "loading" }
  | { status: "ready"; url: string; generation: string | null; startedAt: number }
  | { status: "error"; message: string };

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Aún no hay datos publicados para esta herramienta.";
    if (error.status === 403) return "No tienes acceso a esta herramienta.";
    if (error.status === 429) return "Demasiadas solicitudes. Espera un minuto y recarga.";
  }
  return "No pudimos cargar la herramienta. Recarga la página para intentarlo de nuevo.";
}

export function SandboxedFrame({ app, onLoaded }: SandboxedFrameProps) {
  const navigate = useNavigate();
  const [state, setState] = useState<FrameState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const startedAt = performance.now();
    setState({ status: "loading" });
    fetchAppContent(app.dominio, app.id)
      .then(({ html, generation }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
        setState({ status: "ready", url: objectUrl, generation, startedAt });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          navigate("/ingreso?motivo=sesion_expirada", { replace: true });
          return;
        }
        setState({ status: "error", message: errorMessage(error) });
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [app.dominio, app.id, navigate]);

  if (state.status === "error") {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-secondary-400">
        {state.message}
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      {state.status === "loading" && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#f5f5f5] text-secondary-400">
          Cargando herramienta…
        </div>
      )}
      {state.status === "ready" && (
        <iframe
          title={app.titulo}
          src={state.url}
          sandbox={sandboxTokens(app.capacidades).join(" ")}
          referrerPolicy="no-referrer"
          className="h-full w-full border-0 bg-white"
          onLoad={() => onLoaded(Math.round(performance.now() - state.startedAt), state.generation)}
        />
      )}
    </div>
  );
}
