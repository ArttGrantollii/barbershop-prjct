const DEFAULT_API_URL = "http://localhost:8000"

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "")
}

export function getApiHttpBaseUrl(rawBase: string | undefined = DEFAULT_API_URL): string {
  const base = trimTrailingSlashes((rawBase || DEFAULT_API_URL).trim())
  if (base.endsWith("/api/v1")) return trimTrailingSlashes(base.slice(0, -"/api/v1".length))
  if (base.endsWith("/api")) return trimTrailingSlashes(base.slice(0, -"/api".length))
  return base
}

export function getApiWebSocketBaseUrl(
  rawBase: string | undefined = DEFAULT_API_URL,
  browserLocation: Pick<Location, "protocol" | "host"> = window.location,
): string {
  const httpBase = getApiHttpBaseUrl(rawBase)
  if (!httpBase) {
    const protocol = browserLocation.protocol === "https:" ? "wss" : "ws"
    return `${protocol}://${browserLocation.host}`
  }
  if (httpBase.startsWith("https://")) return httpBase.replace(/^https:\/\//, "wss://")
  if (httpBase.startsWith("http://")) return httpBase.replace(/^http:\/\//, "ws://")
  return httpBase
}
