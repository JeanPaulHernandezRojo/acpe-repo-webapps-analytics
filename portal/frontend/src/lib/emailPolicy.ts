import type { EmailPolicyRules } from "@/types";

/**
 * Réplica de la política de correos del backend (alejandria/email_policy.py).
 * Solo sirve para dar un mensaje inmediato: la decisión real la toma el backend.
 */

export interface PolicyResult {
  allowed: boolean;
  email: string;
  reason: "" | "formato_invalido" | "dominio_no_permitido" | "prefijo_excluido";
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function evaluateEmail(email: string, rules: EmailPolicyRules): PolicyResult {
  const normalized = normalizeEmail(email);
  const at = normalized.lastIndexOf("@");
  const user = at > 0 ? normalized.slice(0, at) : "";
  const domain = at > 0 ? normalized.slice(at + 1) : "";
  if (!user || !domain || normalized.includes(" ")) {
    return { allowed: false, email: normalized, reason: "formato_invalido" };
  }
  const domains = rules.dominios_permitidos.map(normalizeEmail);
  if (!domains.includes(domain)) {
    return { allowed: false, email: normalized, reason: "dominio_no_permitido" };
  }
  const prefixes = rules.prefijos_excluidos.map(normalizeEmail);
  if (prefixes.some((prefix) => user.startsWith(prefix))) {
    return { allowed: false, email: normalized, reason: "prefijo_excluido" };
  }
  return { allowed: true, email: normalized, reason: "" };
}
