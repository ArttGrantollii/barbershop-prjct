import { lazy, Suspense } from "react"
import type { ReactNode } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { AnimatePresence } from "framer-motion"
import { AuthProvider } from "@/context/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { PageTransition } from "@/components/ui/PageTransition"

const HomePage = lazy(() => import("@/pages/HomePage"))
const LoginPage = lazy(() => import("@/pages/LoginPage"))
const RegisterPage = lazy(() => import("@/pages/RegisterPage"))
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage"))
const ResetPasswordPage = lazy(() => import("@/pages/ResetPasswordPage"))
const VerifyEmailPage = lazy(() => import("@/pages/VerifyEmailPage"))
const BookPage = lazy(() => import("@/pages/BookPage"))
const BookingConfirmationPage = lazy(() => import("@/pages/BookingConfirmationPage"))
const MyBookingsPage = lazy(() => import("@/pages/MyBookingsPage"))
const ProfilePage = lazy(() => import("@/pages/ProfilePage"))
const AdminLayout = lazy(() => import("@/components/admin/AdminLayout").then((mod) => ({ default: mod.AdminLayout })))
const AdminDashboardPage = lazy(() => import("@/pages/admin/AdminDashboardPage"))
const AdminBookingsPage = lazy(() => import("@/pages/admin/AdminBookingsPage"))
const AdminWaitlistPage = lazy(() => import("@/pages/admin/AdminWaitlistPage"))
const AdminServicesPage = lazy(() => import("@/pages/admin/AdminServicesPage"))
const AdminStaffPage = lazy(() => import("@/pages/admin/AdminStaffPage"))
const AdminHoursPage = lazy(() => import("@/pages/admin/AdminHoursPage"))
const AdminBlockedDatesPage = lazy(() => import("@/pages/admin/AdminBlockedDatesPage"))

function RouteSuspense({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="container py-16">
          <div className="h-px w-24 overflow-hidden bg-border">
            <div className="h-full w-12 animate-pulse bg-foreground" />
          </div>
        </div>
      }
    >
      {children}
    </Suspense>
  )
}

function Page({ children }: { children: ReactNode }) {
  return <RouteSuspense><PageTransition>{children}</PageTransition></RouteSuspense>
}

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Page><HomePage /></Page>} />
        <Route path="/login" element={<Page><LoginPage /></Page>} />
        <Route path="/register" element={<Page><RegisterPage /></Page>} />
        <Route path="/forgot-password" element={<Page><ForgotPasswordPage /></Page>} />
        <Route path="/reset-password" element={<Page><ResetPasswordPage /></Page>} />
        <Route path="/verify-email" element={<Page><VerifyEmailPage /></Page>} />
        <Route
          path="/book"
          element={<ProtectedRoute customerOnly><Page><BookPage /></Page></ProtectedRoute>}
        />
        <Route
          path="/my-bookings"
          element={<ProtectedRoute customerOnly><Page><MyBookingsPage /></Page></ProtectedRoute>}
        />
        <Route
          path="/bookings/:id/confirmation"
          element={<ProtectedRoute customerOnly><Page><BookingConfirmationPage /></Page></ProtectedRoute>}
        />
        <Route
          path="/profile"
          element={<ProtectedRoute><Page><ProfilePage /></Page></ProtectedRoute>}
        />
        <Route
          path="/admin"
          element={<ProtectedRoute adminOnly><RouteSuspense><AdminLayout /></RouteSuspense></ProtectedRoute>}
        >
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<Page><AdminDashboardPage /></Page>} />
          <Route path="bookings" element={<Page><AdminBookingsPage /></Page>} />
          <Route path="waitlist" element={<Page><AdminWaitlistPage /></Page>} />
          <Route path="services" element={<Page><AdminServicesPage /></Page>} />
          <Route path="staff" element={<Page><AdminStaffPage /></Page>} />
          <Route path="hours" element={<Page><AdminHoursPage /></Page>} />
          <Route path="blocked-dates" element={<Page><AdminBlockedDatesPage /></Page>} />
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
