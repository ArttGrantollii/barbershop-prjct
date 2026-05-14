import assert from "node:assert/strict"

import { getApiHttpBaseUrl, getApiWebSocketBaseUrl } from "../src/lib/apiUrl.js"

const localhost = { protocol: "http:", host: "localhost:3000" }
const production = { protocol: "https:", host: "salon.example" }

assert.equal(getApiHttpBaseUrl("/api"), "")
assert.equal(`${getApiHttpBaseUrl("/api")}/api/v1/services`, "/api/v1/services")
assert.equal(`${getApiHttpBaseUrl("/api")}/api/v1/auth/refresh`, "/api/v1/auth/refresh")

assert.equal(getApiHttpBaseUrl("http://localhost:8000"), "http://localhost:8000")
assert.equal(
  `${getApiHttpBaseUrl("http://localhost:8000")}/api/v1/services`,
  "http://localhost:8000/api/v1/services",
)

assert.equal(getApiHttpBaseUrl("https://salon.example/api"), "https://salon.example")
assert.equal(getApiHttpBaseUrl("https://salon.example/api/v1"), "https://salon.example")

assert.equal(getApiWebSocketBaseUrl("/api", production), "wss://salon.example")
assert.equal(
  `${getApiWebSocketBaseUrl("/api", production)}/api/v1/ws/slots/2026-05-14`,
  "wss://salon.example/api/v1/ws/slots/2026-05-14",
)
assert.equal(getApiWebSocketBaseUrl("http://localhost:8000", localhost), "ws://localhost:8000")

console.log("API URL construction checks passed")
