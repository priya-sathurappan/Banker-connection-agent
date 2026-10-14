declare const __webpack_public_path__: string | undefined;

export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Where the backend lives, in order of precedence:
 * 1. the `apiBaseUrl` prop from the parent container;
 * 2. config.json served next to remoteEntry.js (set per environment at deploy time);
 * 3. the local default.
 */
export async function resolveApiBaseUrl(fromProps?: string): Promise<string> {
  if (fromProps) return fromProps;
  try {
    const publicPath = typeof __webpack_public_path__ === "string" ? __webpack_public_path__ : "/";
    const url = new URL("config.json", new URL(publicPath, window.location.href));
    const response = await fetch(url, { cache: "no-cache" });
    if (response.ok) {
      const config = await response.json();
      if (typeof config.apiBaseUrl === "string" && config.apiBaseUrl) return config.apiBaseUrl;
    }
  } catch {
    // Fall through to the default.
  }
  return DEFAULT_API_BASE_URL;
}

export function newCorrelationId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}
