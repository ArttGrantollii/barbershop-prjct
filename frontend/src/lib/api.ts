import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios"

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Single-flight refresh ────────────────────────────────────────────────────
// Concurrent 401s must not each fire their own /auth/refresh. The first
// rotation blacklists the consumed refresh token; any other in-flight call
// using that same token would 401 and log the user out. We cache the
// in-flight Promise so every concurrent caller awaits the same rotation.

let refreshInFlight: Promise<string> | null = null

async function rotateTokens(): Promise<string> {
  const refresh = localStorage.getItem("refresh_token")
  if (!refresh) throw new Error("no refresh token")
  const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
    refresh_token: refresh,
  })
  localStorage.setItem("access_token", data.access_token)
  localStorage.setItem("refresh_token", data.refresh_token)
  return data.access_token as string
}

function refreshAccessToken(): Promise<string> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = rotateTokens().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

type RetryableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined
    if (error.response?.status !== 401 || !original || original._retry) {
      return Promise.reject(error)
    }
    original._retry = true
    try {
      const token = await refreshAccessToken()
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    } catch {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      window.location.href = "/login"
      return Promise.reject(error)
    }
  },
)

export default api
