import { Link, useNavigate } from "react-router-dom"
import { Scissors, Menu, X } from "lucide-react"
import { useState } from "react"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate("/")
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Scissors className="h-4 w-4" />
          Vendos Salon
        </Link>

        {/* desktop */}
        <nav className="hidden md:flex items-center gap-6 text-sm">
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

        <div className="hidden md:flex items-center gap-2">
          {user ? (
            <>
              <span className="text-sm text-muted-foreground">{user.name}</span>
              <Button variant="outline" size="sm" onClick={handleLogout}>Sign out</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild><Link to="/login">Sign in</Link></Button>
              <Button size="sm" asChild><Link to="/register">Register</Link></Button>
            </>
          )}
        </div>

        {/* mobile toggle */}
        <button className="md:hidden" onClick={() => setOpen((o) => !o)}>
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* mobile menu */}
      <div className={cn("md:hidden border-t", open ? "block" : "hidden")}>
        <nav className="container flex flex-col gap-3 py-4 text-sm">
          <Link to="/" onClick={() => setOpen(false)} className="text-muted-foreground">Home</Link>
          {user?.role !== "admin" && (
            <Link to="/book" onClick={() => setOpen(false)} className="text-muted-foreground">Book</Link>
          )}
          {user && user.role !== "admin" && (
            <Link to="/my-bookings" onClick={() => setOpen(false)} className="text-muted-foreground">My Bookings</Link>
          )}
          {user?.role === "admin" && (
            <Link to="/admin" onClick={() => setOpen(false)} className="text-muted-foreground">Admin</Link>
          )}
          <div className="pt-2 border-t flex gap-2">
            {user ? (
              <Button variant="outline" size="sm" onClick={() => { handleLogout(); setOpen(false) }}>Sign out</Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" asChild><Link to="/login" onClick={() => setOpen(false)}>Sign in</Link></Button>
                <Button size="sm" asChild><Link to="/register" onClick={() => setOpen(false)}>Register</Link></Button>
              </>
            )}
          </div>
        </nav>
      </div>
    </header>
  )
}
