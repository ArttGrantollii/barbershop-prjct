import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

interface Props {
  children: ReactNode
  adminOnly?: boolean
  customerOnly?: boolean
}

export function ProtectedRoute({ children, adminOnly = false, customerOnly = false }: Props) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-6 w-6 rounded-full border-2 border-foreground border-t-transparent animate-spin" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />
  if (customerOnly && user.role === "admin") return <Navigate to="/admin" replace />

  return <>{children}</>
}
