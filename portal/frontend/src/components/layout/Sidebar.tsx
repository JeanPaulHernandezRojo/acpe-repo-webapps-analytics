import { CircleUserRound, PanelLeftClose, PanelLeftOpen, Wrench } from "lucide-react";
import { NavLink, useLocation } from "react-router";
import { BrandMark } from "@/components/BrandMark";
import { cn } from "@/lib/utils";

/**
 * Menú lateral (estilo ATLAS). Hoy tiene una sola sección, "Herramientas"; las futuras
 * secciones se agregan como nuevos ítems de NAV_ITEMS.
 */

interface SidebarProps {
  name: string;
  subtitle: string;
  email: string;
  toolCount: number;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onNavigate: () => void;
}

const NAV_ITEMS = [{ to: "/", label: "Herramientas", icon: Wrench, matchPrefix: "/herramientas" }];

export function Sidebar({
  name,
  subtitle,
  email,
  toolCount,
  collapsed,
  onToggleCollapsed,
  onNavigate,
}: SidebarProps) {
  const location = useLocation();
  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-[#E5E7EB] bg-white transition-[width] duration-150",
        collapsed ? "w-[72px]" : "w-[260px]",
      )}
    >
      <div className={cn("px-4 pt-5 pb-6", collapsed && "px-3")}>
        <BrandMark name={name} subtitle={subtitle} compact={collapsed} />
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, matchPrefix }) => {
          const active = location.pathname === to || location.pathname.startsWith(matchPrefix);
          return (
            <NavLink
              key={to}
              to={to}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              className={cn(
                "flex items-center rounded-lg text-[0.9rem] font-semibold transition-colors",
                collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
                active
                  ? "bg-primary-50 text-primary-600"
                  : "text-secondary-500 hover:bg-secondary-100 hover:text-primary-500",
              )}
            >
              <Icon className="size-[1.1rem] shrink-0" strokeWidth={2} />
              {!collapsed && (
                <>
                  <span className="flex-1 truncate">{label}</span>
                  <span
                    className={cn(
                      "rounded-[10px] px-[0.45rem] py-[0.1rem] text-[0.68rem] font-bold",
                      active ? "bg-primary-500 text-white" : "bg-secondary-200 text-secondary-500",
                    )}
                  >
                    {toolCount}
                  </span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="flex flex-col gap-1 border-t border-[#E5E7EB] px-3 py-4">
        <div
          className={cn(
            "flex items-center gap-3 px-3 py-2 text-[0.8rem] text-secondary-400",
            collapsed && "justify-center px-0",
          )}
          title={email}
        >
          <CircleUserRound className="size-[1.1rem] shrink-0" />
          {!collapsed && <span className="truncate">{email}</span>}
        </div>
        <button
          type="button"
          onClick={onToggleCollapsed}
          className={cn(
            "hidden items-center gap-3 rounded-lg px-3 py-2 text-[0.85rem] font-semibold text-secondary-500 transition-colors hover:bg-secondary-100 hover:text-primary-500 md:flex",
            collapsed && "justify-center px-0",
          )}
          title={collapsed ? "Expandir menú" : undefined}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-[1.1rem]" />
          ) : (
            <PanelLeftClose className="size-[1.1rem]" />
          )}
          {!collapsed && <span>Colapsar menú</span>}
        </button>
      </div>
    </aside>
  );
}
