import type { WatermarkLevel } from "@/types";

/**
 * Niveles de marca de agua. La marca es una capa del portal por encima del iframe
 * (pointer-events: none), nunca parte del HTML.
 */

export type WatermarkSpec =
  { kind: "pattern"; opacity: number; tileSize: number } | { kind: "corner" } | { kind: "band" };

export function watermarkSpec(level: WatermarkLevel): WatermarkSpec {
  switch (level) {
    case "patron_suave":
      return { kind: "pattern", opacity: 0.05, tileSize: 360 };
    case "patron":
      return { kind: "pattern", opacity: 0.1, tileSize: 240 };
    case "esquina":
      return { kind: "corner" };
    case "franja":
      return { kind: "band" };
  }
}

export function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Arma un SVG en data URI con el texto en diagonal, para repetirlo como fondo. */
export function patternDataUri(text: string, opacity: number, tileSize: number): string {
  const half = tileSize / 2;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${tileSize}" height="${tileSize}">` +
    `<text x="${half}" y="${half}" text-anchor="middle" dominant-baseline="middle" ` +
    `transform="rotate(-30 ${half} ${half})" font-family="Public Sans, sans-serif" ` +
    `font-size="13" fill="#2d2926" fill-opacity="${opacity}">${escapeXml(text)}</text></svg>`;
  return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
}
