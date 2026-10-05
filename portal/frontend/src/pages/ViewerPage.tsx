import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { Link, useParams } from "react-router";
import { SandboxedFrame } from "@/components/SandboxedFrame";
import { Watermark } from "@/components/Watermark";
import { useConfig } from "@/context/ConfigContext";
import { useSession } from "@/context/SessionContext";
import { startViewerTracking } from "@/lib/tracking";
import { formatDateTime } from "@/lib/utils";

/** Visor: muestra el HTML de una herramienta dentro del layout, con el sidebar visible. */

export function ViewerPage() {
  const { dominio = "", appId = "" } = useParams();
  const config = useConfig();
  const { apps, correo } = useSession();
  const app = apps.find((item) => item.dominio === dominio && item.id === appId);
  const stopTracking = useRef<(() => void) | null>(null);
  const watermarkText = useMemo(() => `${correo} · ${formatDateTime(new Date())}`, [correo]);

  const handleLoaded = useCallback(
    (loadMs: number, generation: string | null) => {
      stopTracking.current?.();
      stopTracking.current = startViewerTracking(
        { dominio, appId, generation },
        loadMs,
        config.latido_segundos,
      );
    },
    [appId, config.latido_segundos, dominio],
  );

  useEffect(
    () => () => {
      stopTracking.current?.();
      stopTracking.current = null;
    },
    [dominio, appId],
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-[#E5E7EB] bg-white px-5 py-3">
        <div className="flex min-w-0 items-center gap-2 text-[0.9rem]">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-1.5 font-semibold text-secondary-500 hover:text-primary-600"
          >
            <ArrowLeft className="size-4" />
            Herramientas
          </Link>
          {app && (
            <>
              <span className="text-secondary-300">/</span>
              <span className="truncate font-semibold text-[#1A1A1A]">{app.titulo}</span>
            </>
          )}
        </div>
        {app?.marca_agua === "franja" && (
          <span className="shrink-0 text-[0.75rem] text-secondary-400">{watermarkText}</span>
        )}
      </div>

      <div className="relative min-h-0 flex-1">
        {app ? (
          <>
            <SandboxedFrame key={`${dominio}/${appId}`} app={app} onLoaded={handleLoaded} />
            <Watermark level={app.marca_agua} text={watermarkText} />
          </>
        ) : (
          <div className="flex h-full items-center justify-center p-8 text-center text-secondary-400">
            No tienes acceso a esta herramienta o no existe.
          </div>
        )}
      </div>
    </div>
  );
}
