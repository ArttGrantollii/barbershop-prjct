import { NavLink, Outlet } from "react-router-dom"
import { Ban, CalendarDays, Clock, LayoutDashboard, Settings } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"
import { Logo } from "@/components/Logo"

const navItems = [
  { to: "/admin/dashboard",     label: "Dashboard",      icon: LayoutDashboard },
  { to: "/admin/bookings",      label: "Bookings",       icon: CalendarDays },
  { to: "/admin/services",      label: "Services",       icon: Settings },
  { to: "/admin/hours",         label: "Hours",          icon: Clock },
  { to: "/admin/blocked-dates", label: "Blocked Dates",  icon: Ban },
]

export function AdminLayout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      {/* sidebar */}
      <aside className="hidden md:flex flex-col w-52 shrink-0 border-r border-border">
        <div className="p-6 border-b border-border">
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-1">Admin</p>
          <p className="text-sm font-medium uppercase tracking-widest truncate">{user?.name?.split(" ")[0] ?? "Admin"}</p>
        </div>

        <nav className="flex flex-col flex-1 py-4">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-6 py-3.5 text-xs tracking-widest uppercase transition-colors",
                  isActive
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )
              }
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-6 border-t border-border">
          <Logo className="h-6 w-auto opacity-50" />
        </div>
      </aside>

      {/* mobile nav */}
      <div className="md:hidden w-full absolute top-16 left-0 z-30 bg-background border-b border-border">
        <div className="container flex gap-0 overflow-x-auto">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-4 py-3 text-[10px] tracking-widest uppercase whitespace-nowrap border-r border-border transition-colors",
                  isActive
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                )
              }
            >
              <Icon className="h-3 w-3 shrink-0" />
              {label}
            </NavLink>
          ))}
        </div>
      </div>

      {/* content */}
      <main className="flex-1 min-w-0 md:p-10 p-6 pt-14 md:pt-10">
        <Outlet />
      </main>
    </div>
  )
}
