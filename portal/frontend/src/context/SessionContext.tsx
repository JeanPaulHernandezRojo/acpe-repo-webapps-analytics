import { createContext, useContext } from "react";
import type { Me } from "@/types";

/** Usuario autenticado y sus apps, disponible dentro del layout protegido. */

export const SessionContext = createContext<Me | null>(null);

export function useSession(): Me {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession debe usarse dentro del layout protegido");
  return session;
}
