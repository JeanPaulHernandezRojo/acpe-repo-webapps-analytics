import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router";
import { FullScreenMessage } from "@/components/FullScreenMessage";
import { Sidebar } from "@/components/layout/Sidebar";
import { useConfig } from "@/context/ConfigContext";
import { SessionContext } from "@/context/SessionContext";
import { ApiError, getMe } from "@/lib/api";
import { readLocal, writeLocal } from "@/lib/storage";
import type { Me } from "@/types";

/**
 * Layout de las páginas con sesión: valida la sesión con /api/yo, redirige al ingreso o a
 * "sin herramientas" según corresponda y dibuja el sidebar.
 */

const COLLAPSE_KEY = "alejandria_menu_colapsado";

type SessionState =
  | { status: "loading" }
  | { status: "ready"; me: Me }
  | { status: "unauthenticated"; expired: boolean }
  | { status: "error" };

export function ProtectedLayout() {
  const config = useConfig();
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [collapsed, setCollapsed] = useState(() => readLocal(COLLAPSE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    getMe()
      .then((me) => setState({ status: "ready", me }))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          setState({ status: "unauthenticated", expired: error.detail === "sesion_expirada" });
        } else {
          setState({ status: "error" });
        }
      });
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((value) => {
      writeLocal(COLLAPSE_KEY, value ? "0" : "1");
      return !value;
    });
  };

  if (state.status === "loading") return <FullScreenMessage title="Cargando…" message="" />;
  if (state.status === "error") {
    return (
      <FullScreenMessage
        title="No pudimos cargar tus herramientas"
        message="Recarga la página en unos minutos."
      />
    );
  }
  if (state.status === "unauthenticated") {
    return <Navigate to={state.expired ? "/ingreso?motivo=sesion_expirada" : "/ingreso"} replace />;
  }
  if (state.me.apps.length === 0) return <Navigate to="/sin-herramientas" replace />;

  const sidebarProps = {
    name: config.portal.nombre,
    subtitle: config.portal.subtitulo,
    email: state.me.correo,
    toolCount: state.me.apps.length,
  };

  return (
    <SessionContext.Provider value={state.me}>
      <div className="flex h-full">
        <div className="hidden md:block">
          <Sidebar
            {...sidebarProps}
            collapsed={collapsed}
            onToggleCollapsed={toggleCollapsed}
            onNavigate={() => undefined}
          />
        </div>

        {mobileOpen && (
          <div className="fixed inset-0 z-40 flex md:hidden">
            <Sidebar
              {...sidebarProps}
              collapsed={false}
              onToggleCollapsed={() => undefined}
              onNavigate={() => setMobileOpen(false)}
            />
            <button
              type="button"
              aria-label="Cerrar menú"
              className="flex-1 bg-black/30"
              onClick={() => setMobileOpen(false)}
            >
              <X className="ml-auto mr-4 mt-4 size-6 text-white" />
            </button>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-3 border-b border-[#E5E7EB] bg-white px-4 py-3 md:hidden">
            <button type="button" aria-label="Abrir menú" onClick={() => setMobileOpen(true)}>
              <Menu className="size-6 text-secondary-500" />
            </button>
            <span className="font-display font-bold text-primary-500">{config.portal.nombre}</span>
          </div>
          <main className="min-h-0 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </SessionContext.Provider>
  );
}
