const id = "[A-Za-z0-9_-]{1,160}";
const document = `documents/${id}`;
const reads = [
  "documents",
  document,
  `${document}/(?:pages|evidence|facts|source|job|index)`,
  `${document}/pages/[1-9][0-9]{0,4}(?:/image)?`,
  `${document}/blocks/${id}/image`,
  `${document}/export/docling`,
  `${document}/figures/${id}/interpretation`,
  `jobs/${id}`,
  `citations/${id}`,
  "index/status",
];
const writes = [
  "documents",
  "qa",
  "retrieve",
  `${document}/(?:reprocess|index)`,
  `${document}/figures/${id}/interpret`,
];

export function allowedProxyPath(method: string, path: string): boolean {
  if (path.includes("%") || path.includes("..") || path.includes("\\")) return false;
  const patterns =
    method === "GET" ? reads : method === "POST" ? writes : method === "DELETE" ? [document] : [];
  return patterns.some((pattern) => new RegExp(`^api/v1/${pattern}$`).test(path));
}

export function configuredBackend(value: string | undefined): URL | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash)
      return null;
    if (
      url.pathname !== "/" ||
      url.hostname === "localhost" ||
      url.hostname.endsWith(".local") ||
      /^[\d.]+$/.test(url.hostname) ||
      url.hostname.includes(":")
    )
      return null;
    return url;
  } catch {
    return null;
  }
}

export function authorizedUser(actual: string | undefined, expected: string | undefined): boolean {
  return Boolean(actual && expected && actual === expected);
}
