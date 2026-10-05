import { describe, expect, it } from "vitest";
import { BASE_TOKEN, FORBIDDEN_TOKENS, sandboxTokens } from "../src/lib/sandbox";

const ALL = { descargas: true, ventanas: true, dialogos: true, formularios: true };

describe("sandboxTokens", () => {
  it("con todas las capacidades activas otorga los cuatro permisos más scripts", () => {
    expect(sandboxTokens(ALL).sort()).toEqual(
      ["allow-downloads", "allow-forms", "allow-modals", "allow-popups", BASE_TOKEN].sort(),
    );
  });

  it("siempre incluye scripts aunque todo esté desactivado", () => {
    const none = { descargas: false, ventanas: false, dialogos: false, formularios: false };
    expect(sandboxTokens(none)).toEqual([BASE_TOKEN]);
  });

  it("desactiva solo la capacidad indicada", () => {
    expect(sandboxTokens({ ...ALL, descargas: false })).not.toContain("allow-downloads");
  });

  it("nunca otorga permisos que rompen el aislamiento", () => {
    const tokens = sandboxTokens(ALL);
    for (const forbidden of FORBIDDEN_TOKENS) expect(tokens).not.toContain(forbidden);
  });
});
