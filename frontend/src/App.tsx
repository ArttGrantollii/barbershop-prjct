import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { AnimatePresence } from "framer-motion"
import { AuthProvider } from "@/context/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { AdminLayout } from "@/components/admin/AdminLayout"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { PageTransition } from "@/components/ui/PageTransition"
import HomePage from "@/pages/HomePage"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import ForgotPasswordPage from "@/pages/ForgotPasswordPage"
import ResetPasswordPage from "@/pages/ResetPasswordPage"
import VerifyEmailPage from "@/pages/VerifyEmailPage"
import BookPage from "@/pages/BookPage"
import BookingConfirmationPage from "@/pages/BookingConfirmationPage"
import MyBookingsPage from "@/pages/MyBookingsPage"
import ProfilePage from "@/pages/ProfilePage"
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage"
import AdminBookingsPage from "@/pages/admin/AdminBookingsPage"
import AdminWaitlistPage from "@/pages/admin/AdminWaitlistPage"
import AdminServicesPage from "@/pages/admin/AdminServicesPage"
import AdminStaffPage from "@/pages/admin/AdminStaffPage"
import AdminHoursPage from "@/pages/admin/AdminHoursPage"
import AdminBlockedDatesPage from "@/pages/admin/AdminBlockedDatesPage"

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageTransition><HomePage /></PageTransition>} />
        <Route path="/login" element={<PageTransition><LoginPage /></PageTransition>} />
        <Route path="/register" element={<PageTransition><RegisterPage /></PageTransition>} />
        <Route path="/forgot-password" element={<PageTransition><ForgotPasswordPage /></PageTransition>} />
        <Route path="/reset-password" element={<PageTransition><ResetPasswordPage /></PageTransition>} />
        <Route path="/verify-email" element={<PageTransition><VerifyEmailPage /></PageTransition>} />
        <Route
          path="/book"
          element={<ProtectedRoute customerOnly><PageTransition><BookPage /></PageTransition></ProtectedRoute>}
        />
        <Route
          path="/my-bookings"
          element={<ProtectedRoute customerOnly><PageTransition><MyBookingsPage /></PageTransition></ProtectedRoute>}
        />
        <Route
          path="/bookings/:id/confirmation"
          element={<ProtectedRoute customerOnly><PageTransition><BookingConfirmationPage /></PageTransition></ProtectedRoute>}
        />
        <Route
          path="/profile"
          element={<ProtectedRoute><PageTransition><ProfilePage /></PageTransition></ProtectedRoute>}
        />
        <Route
          path="/admin"
          element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>}
        >
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<PageTransition><AdminDashboardPage /></PageTransition>} />
          <Route path="bookings" element={<PageTransition><AdminBookingsPage /></PageTransition>} />
          <Route path="waitlist" element={<PageTransition><AdminWaitlistPage /></PageTransition>} />
          <Route path="services" element={<PageTransition><AdminServicesPage /></PageTransition>} />
          <Route path="staff" element={<PageTransition><AdminStaffPage /></PageTransition>} />
          <Route path="hours" element={<PageTransition><AdminHoursPage /></PageTransition>} />
          <Route path="blocked-dates" element={<PageTransition><AdminBlockedDatesPage /></PageTransition>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1">
          {/* Scoped to <main> so the navbar stays usable even if a page crashes. */}
          <ErrorBoundary>
            <AnimatedRoutes />
          </ErrorBoundary>
        </main>
      </div>
    </AuthProvider>
  )
}
