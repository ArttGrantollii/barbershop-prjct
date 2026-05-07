import { Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/context/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { AdminLayout } from "@/components/admin/AdminLayout"
import HomePage from "@/pages/HomePage"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import BookPage from "@/pages/BookPage"
import MyBookingsPage from "@/pages/MyBookingsPage"
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage"
import AdminBookingsPage from "@/pages/admin/AdminBookingsPage"
import AdminServicesPage from "@/pages/admin/AdminServicesPage"
import AdminHoursPage from "@/pages/admin/AdminHoursPage"
import AdminBlockedDatesPage from "@/pages/admin/AdminBlockedDatesPage"

export default function App() {
  return (
    <AuthProvider>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/book"
              element={<ProtectedRoute customerOnly><BookPage /></ProtectedRoute>}
            />
            <Route
              path="/my-bookings"
              element={<ProtectedRoute customerOnly><MyBookingsPage /></ProtectedRoute>}
            />
            <Route
              path="/admin"
              element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>}
            >
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboardPage />} />
              <Route path="bookings" element={<AdminBookingsPage />} />
              <Route path="services" element={<AdminServicesPage />} />
              <Route path="hours" element={<AdminHoursPage />} />
              <Route path="blocked-dates" element={<AdminBlockedDatesPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  )
}
