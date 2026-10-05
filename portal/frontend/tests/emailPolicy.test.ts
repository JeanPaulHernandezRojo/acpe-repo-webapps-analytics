import { describe, expect, it } from "vitest";
import { evaluateEmail, normalizeEmail } from "../src/lib/emailPolicy";

const RULES = {
  dominios_permitidos: ["alicorp.com.pe"],
  prefijos_excluidos: ["ext_"],
  mensaje_rechazo: "Solo correos corporativos.",
};

describe("política de correos (réplica del backend)", () => {
  it("normaliza espacios y mayúsculas", () => {
    expect(normalizeEmail("  JPerez@Alicorp.COM.pe ")).toBe("jperez@alicorp.com.pe");
  });

  it.each([
    ["jperez@alicorp.com.pe", true, ""],
    ["JPerez@ALICORP.com.pe", true, ""],
    ["jperez@gmail.com", false, "dominio_no_permitido"],
    ["EXT_jperez@alicorp.com.pe", false, "prefijo_excluido"],
    ["sin-arroba", false, "formato_invalido"],
    ["@alicorp.com.pe", false, "formato_invalido"],
  ])("%s → permitido=%s", (email, allowed, reason) => {
    const result = evaluateEmail(email, RULES);
    expect(result.allowed).toBe(allowed);
    expect(result.reason).toBe(reason);
  });
});
