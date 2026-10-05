import { ToolCard } from "@/components/ToolCard";
import { useSession } from "@/context/SessionContext";

/** Sección "Herramientas": tarjetas de las apps habilitadas para el usuario. */

export function ToolsPage() {
  const { apps } = useSession();
  return (
    <div className="px-6 py-8 md:px-10">
      <div className="mb-8">
        <h1 className="mb-2 font-display text-[1.9rem] leading-tight font-bold text-[#1A1A1A]">
          Herramientas
        </h1>
        <p className="max-w-2xl text-[0.95rem] text-secondary-400">
          Las herramientas analíticas habilitadas para ti.
        </p>
      </div>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
      >
        {apps.map((app) => (
          <ToolCard key={`${app.dominio}/${app.id}`} app={app} />
        ))}
      </div>
    </div>
  );
}
