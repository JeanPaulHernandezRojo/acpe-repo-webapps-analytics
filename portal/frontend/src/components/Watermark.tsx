import { patternDataUri, watermarkSpec } from "@/lib/watermark";
import type { WatermarkLevel } from "@/types";

/**
 * Capa de marca de agua sobre el visor. No bloquea clics ni scroll (pointer-events: none).
 * El nivel "franja" no dibuja capa: el texto se muestra en la barra del visor.
 */

interface WatermarkProps {
  level: WatermarkLevel;
  text: string;
}

export function Watermark({ level, text }: WatermarkProps) {
  const spec = watermarkSpec(level);
  if (spec.kind === "band") return null;
  if (spec.kind === "corner") {
    return (
      <div className="pointer-events-none absolute right-3 bottom-3 z-10 rounded bg-white/75 px-2 py-1 text-[0.7rem] text-secondary-400 select-none">
        {text}
      </div>
    );
  }
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-10 select-none"
      style={{ backgroundImage: patternDataUri(text, spec.opacity, spec.tileSize) }}
    />
  );
}
