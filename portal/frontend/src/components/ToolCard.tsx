import { ArrowRight } from "lucide-react";
import { Link } from "react-router";
import { iconFor } from "@/config/icons";
import type { AppSummary } from "@/types";

/** Tarjeta de una herramienta (estilo de las tarjetas de ATLAS). Datos desde app.yaml -> tarjeta. */

export function ToolCard({ app }: { app: AppSummary }) {
  const Icon = iconFor(app.icono);
  return (
    <Link
      to={`/herramientas/${app.dominio}/${app.id}`}
      className="group flex flex-col items-start gap-3 rounded-xl border border-[#E5E7EB] bg-white p-5 text-left transition-all hover:border-primary-300 hover:shadow-sm"
    >
      <div className="flex w-full items-center justify-between">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
          <Icon className="size-5" strokeWidth={1.75} />
        </div>
        <span className="text-[0.75rem] font-bold text-secondary-400">{app.etiqueta}</span>
      </div>
      <div>
        <div className="flex items-center gap-1.5 text-[15px] font-semibold text-gray-900">
          {app.titulo}
          <ArrowRight className="size-3.5 text-primary-500 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <p className="mt-1 text-[0.82rem] leading-snug text-secondary-400">{app.descripcion}</p>
      </div>
    </Link>
  );
}
