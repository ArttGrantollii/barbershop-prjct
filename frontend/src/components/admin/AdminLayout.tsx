import { NavLink, Outlet } from "react-router-dom"
import { Calendar, Clock, List, Scissors } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/admin/bookings", label: "Bookings", icon: List },
  { to: "/admin/services", label: "Services", icon: Scissors },
  { to: "/admin/hours", label: "Business Hours", icon: Clock },
  { to: "/admin/blocked-dates", label: "Blocked Dates", icon: Calendar },
]

export function AdminLayout() {
  return (
    <div className="container py-8">
      <div className="flex gap-8">
        {/* sidebar */}
        <nav className="hidden md:flex flex-col gap-1 w-44 shrink-0">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-3">
            Admin
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
                    isActive ? "bg-primary text-primary-foreground border-primary" : "border-input text-muted-foreground"
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
