import { describe, expect, it } from "vitest";
import { escapeXml, patternDataUri, watermarkSpec } from "../src/lib/watermark";

describe("marca de agua", () => {
  it("patron_suave es más tenue y espaciado que patron", () => {
    const soft = watermarkSpec("patron_suave");
    const strong = watermarkSpec("patron");
    if (soft.kind !== "pattern" || strong.kind !== "pattern") throw new Error("se esperaba patrón");
    expect(soft.opacity).toBeLessThan(strong.opacity);
    expect(soft.tileSize).toBeGreaterThan(strong.tileSize);
  });

  it("esquina y franja no son patrones", () => {
    expect(watermarkSpec("esquina").kind).toBe("corner");
    expect(watermarkSpec("franja").kind).toBe("band");
  });

  it("escapa caracteres especiales en el SVG", () => {
    expect(escapeXml(`a<b>&"c'`)).toBe("a&lt;b&gt;&amp;&quot;c&apos;");
    const uri = patternDataUri("ana@alicorp.com.pe · 01/10/2026", 0.05, 360);
    expect(uri.startsWith('url("data:image/svg+xml')).toBe(true);
    expect(decodeURIComponent(uri)).toContain("ana@alicorp.com.pe");
  });
});
