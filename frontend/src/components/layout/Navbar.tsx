import { Link, useNavigate } from "react-router-dom"
import { Menu, X } from "lucide-react"
import { useState } from "react"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Logo } from "@/components/Logo"

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate("/")
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background">
      <div className="container flex h-16 items-center justify-between">
        {/* logo */}
        <Link to="/" className="flex items-center">
          <Logo className="h-9 w-auto" />
        </Link>

        {/* desktop nav */}
        <nav className="hidden md:flex items-center gap-8 text-xs tracking-widest uppercase">
          <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">Home</Link>
          {user?.role !== "admin" && (
            <Link to="/book" className="text-muted-foreground hover:text-foreground transition-colors">Book</Link>
          )}
          {user && user.role !== "admin" && (
            <Link to="/my-bookings" className="text-muted-foreground hover:text-foreground transition-colors">My Bookings</Link>
          )}
          {user?.role === "admin" && (
            <Link to="/admin" className="text-muted-foreground hover:text-foreground transition-colors">Admin</Link>
          )}
        </nav>

        {/* desktop auth */}
        <div className="hidden md:flex items-center gap-4">
          {user ? (
            <>
              <Link
                to="/profile"
                className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
              >
                {user.name}
              </Link>
              <button
                onClick={handleLogout}
                className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors">
                Sign in
              </Link>
              <Link
                to="/register"
                className="text-xs tracking-widest uppercase bg-foreground text-background px-5 py-2.5 hover:bg-foreground/90 transition-colors"
              >
                Register
              </Link>
            </>
          )}
        </div>

        {/* mobile toggle */}
        <button className="md:hidden text-muted-foreground hover:text-foreground transition-colors" onClick={() => setOpen((o) => !o)}>
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* mobile menu */}
      <div className={cn("md:hidden border-t border-border bg-background", open ? "block" : "hidden")}>
        <nav className="container flex flex-col gap-5 py-8 text-xs tracking-widest uppercase">
          <Link to="/" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">Home</Link>
          {user?.role !== "admin" && (
            <Link to="/book" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">Book</Link>
          )}
          {user && user.role !== "admin" && (
            <Link to="/my-bookings" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">My Bookings</Link>
          )}
          {user?.role === "admin" && (
            <Link to="/admin" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">Admin</Link>
          )}
          <div className="pt-5 border-t border-border flex flex-col gap-4">
            {user ? (
              <>
                <Link to="/profile" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                  Profile
                </Link>
                <button onClick={() => { handleLogout(); setOpen(false) }} className="text-left text-muted-foreground hover:text-foreground transition-colors">Sign out</button>
              </>
            ) : (
              <>
                <Link to="/login" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">Sign in</Link>
                <Link to="/register" onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">Register</Link>
              </>
            )}
          </div>
        </nav>
      </div>
    </header>
  )
}
