import { NavLink, Outlet } from "react-router-dom"
import { Ban, CalendarDays, Clock, LayoutDashboard, Scissors, Scissors as ScissorsIcon } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/admin/dashboard", label: "Dashboard",      icon: LayoutDashboard },
  { to: "/admin/bookings",  label: "Bookings",       icon: CalendarDays },
  { to: "/admin/services",  label: "Services",       icon: ScissorsIcon },
  { to: "/admin/hours",     label: "Business Hours", icon: Clock },
  { to: "/admin/blocked-dates", label: "Blocked Dates", icon: Ban },
]

export function AdminLayout() {
  const { user } = useAuth()

  return (
    <div className="container py-8">
      <div className="flex gap-8">
        {/* sidebar */}
        <nav className="hidden md:flex flex-col gap-1 w-48 shrink-0">
          {/* branding / identity */}
          <div className="flex items-center gap-2 px-3 mb-5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Scissors className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold leading-none truncate">Vendos Salon</p>
              <p className="text-[10px] text-muted-foreground leading-none mt-0.5 truncate">
                {user?.name ?? "Admin"}
              </p>
            </div>
          </div>

          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-1">
            Menu
          </p>

          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* mobile nav */}
        <div className="md:hidden w-full mb-4">
          <div className="flex gap-2 flex-wrap">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-input text-muted-foreground"
                  )
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>

        {/* content */}
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
