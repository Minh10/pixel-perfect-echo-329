export type PdfFit = "width" | "page" | "custom";

/** Dimensions are reader layout only, never parser geometry or evidence coordinates. */
export function pdfDisplayWidth(
  fit: PdfFit,
  viewportWidth: number,
  viewportHeight: number,
  aspect: number,
  zoom: number,
) {
  const width = Math.max(180, viewportWidth - 48);
  if (fit === "page") return Math.min(width, Math.max(180, viewportHeight - 72) * aspect);
  if (fit === "custom") return Math.max(180, 794 * zoom);
  return width;
}