import { useState } from "react"
import type { FormEvent } from "react"
import { Link, useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { useToast } from "@/hooks/use-toast"
import { Logo } from "@/components/Logo"

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { toast } = useToast()
  const from = (location.state as { from?: string })?.from ?? "/"

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch {
      toast({ variant: "destructive", title: "Sign in failed", description: "Check your email and password." })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex">
      {/* left panel — branding */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border w-[420px] shrink-0">
        <Logo className="h-8 w-auto self-start" />
        <div>
          <h2 className="font-display text-7xl uppercase leading-none mb-4">Welcome<br />Back.</h2>
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Premium Male Grooming</p>
        </div>
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground">© {new Date().getFullYear()} VENDOS SALON</p>
      </div>

      {/* right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="mb-10">
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Account Access</p>
            <h1 className="font-display text-5xl uppercase">Sign In</h1>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-0 border border-border">
            <div className="flex flex-col gap-1 p-5 border-b border-border">
              <label htmlFor="email" className="text-[10px] tracking-widest uppercase text-muted-foreground">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/50 py-1"
                placeholder="you@example.com"
              />
            </div>
            <div className="flex flex-col gap-1 p-5 border-b border-border">
              <label htmlFor="password" className="text-[10px] tracking-widest uppercase text-muted-foreground">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/50 py-1"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="p-5 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <p className="text-xs tracking-wider text-muted-foreground mt-6 text-center">
            No account?{" "}
            <Link to="/register" className="text-foreground hover:underline underline-offset-4">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
