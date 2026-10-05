import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { ICONS, iconFor } from "../src/config/icons";

const yamlPath = new URL("../../config/iconos_permitidos.yaml", import.meta.url);

describe("íconos permitidos", () => {
  it("el mapa del frontend coincide con portal/config/iconos_permitidos.yaml", () => {
    const allowed = (parse(readFileSync(yamlPath, "utf-8")) as { iconos: string[] }).iconos;
    expect(Object.keys(ICONS).sort()).toEqual([...allowed].sort());
  });

  it("un ícono desconocido cae al ícono por defecto", () => {
    expect(iconFor("no-existe")).toBe(ICONS["layout-dashboard"]);
  });
});
