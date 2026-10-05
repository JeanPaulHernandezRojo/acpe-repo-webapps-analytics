import {
  Boxes,
  Calculator,
  ChartBar,
  ChartLine,
  ChartPie,
  Coins,
  Factory,
  FileSpreadsheet,
  LayoutDashboard,
  Map as MapIcon,
  MapPin,
  Package,
  Percent,
  ShoppingCart,
  Store,
  Table,
  Target,
  TrendingUp,
  Truck,
  UserCheck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

/**
 * Íconos permitidos para las tarjetas (app.yaml -> tarjeta.icono).
 * Debe coincidir con portal/config/iconos_permitidos.yaml (lo verifica tests/icons.test.ts).
 */
export const ICONS: Record<string, LucideIcon> = {
  "layout-dashboard": LayoutDashboard,
  "chart-line": ChartLine,
  "chart-bar": ChartBar,
  "chart-pie": ChartPie,
  map: MapIcon,
  "map-pin": MapPin,
  boxes: Boxes,
  package: Package,
  truck: Truck,
  store: Store,
  "shopping-cart": ShoppingCart,
  users: Users,
  "user-check": UserCheck,
  calculator: Calculator,
  percent: Percent,
  coins: Coins,
  factory: Factory,
  warehouse: Warehouse,
  target: Target,
  "trending-up": TrendingUp,
  table: Table,
  "file-spreadsheet": FileSpreadsheet,
};

export function iconFor(name: string): LucideIcon {
  return ICONS[name] ?? LayoutDashboard;
}
