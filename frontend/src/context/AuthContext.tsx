import React, { createContext, useCallback, useContext, useEffect, useState } from "react"
import api from "@/lib/api"
import type { User } from "@/types"

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string, phone?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    const token = localStorage.getItem("access_token")
    if (!token) { setIsLoading(false); return }
    try {
      const { data } = await api.get<User>("/api/v1/auth/me")
      setUser(data)
    } catch {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

  const login = async (email: string, password: string) => {
    const form = new URLSearchParams()
    form.append("username", email)
    form.append("password", password)
    const { data } = await api.post("/api/v1/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    localStorage.setItem("access_token", data.access_token)
    localStorage.setItem("refresh_token", data.refresh_token)
    await fetchMe()
  }

  const register = async (name: string, email: string, password: string, phone?: string) => {
    await api.post("/api/v1/auth/register", { name, email, password, phone: phone || null })
    await login(email, password)
  }

  const logout = () => {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}
