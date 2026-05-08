import { useState } from "react"
import type { ChangeEvent, FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { useToast } from "@/hooks/use-toast"
import { Logo } from "@/components/Logo"

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const { toast } = useToast()

  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "", confirm: "" })
  const [loading, setLoading] = useState(false)

  const set = (k: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (form.password !== form.confirm) {
      toast({ variant: "destructive", title: "Passwords don't match" })
      return
    }
    setLoading(true)
    try {
      await register(form.name, form.email, form.password, form.phone || undefined)
      toast({ title: "Account created", description: "Check your email for a verification link." })
      navigate("/", { replace: true })
    } catch (err: any) {
      if (!err.response) {
        toast({ variant: "destructive", title: "Cannot reach server", description: "The backend is not responding. Make sure Docker is running." })
      } else {
        const detail = err.response.data?.detail
        let msg = "Registration failed. Please try again."
        if (typeof detail === "string") msg = detail
        else if (Array.isArray(detail)) msg = detail.map((d: any) => d.msg ?? String(d)).join(", ")
        toast({ variant: "destructive", title: "Error", description: msg })
      }
    } finally {
      setLoading(false)
    }
  }

  const fields = [
    { key: "name",     label: "Full Name",            type: "text",     auto: "name",         placeholder: "John Doe" },
    { key: "email",    label: "Email Address",         type: "email",    auto: "email",        placeholder: "you@example.com" },
    { key: "phone",    label: "Phone (optional)",      type: "tel",      auto: "tel",          placeholder: "+1 555 000 0000" },
    { key: "password", label: "Password",              type: "password", auto: "new-password", placeholder: "••••••••" },
    { key: "confirm",  label: "Confirm Password",      type: "password", auto: "new-password", placeholder: "••••••••" },
  ] as const

  return (
    <div className="min-h-[calc(100vh-4rem)] flex">
      {/* left panel */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border w-[420px] shrink-0">
        <Logo className="h-8 w-auto self-start" />
        <div>
          <h2 className="font-display text-7xl uppercase leading-none mb-4">Join<br />Us.</h2>
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Book. Arrive. Look sharp.</p>
        </div>
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground">© {new Date().getFullYear()} VENDOS SALON</p>
      </div>

      {/* right panel */}
      <div className="flex-1 flex items-center justify-center p-8 py-16">
        <div className="w-full max-w-sm">
          <div className="mb-10">
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">New Account</p>
            <h1 className="font-display text-5xl uppercase">Register</h1>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-0 border border-border">
            {fields.map(({ key, label, type, auto, placeholder }, i) => (
              <div
                key={key}
                className={`flex flex-col gap-1 p-5 ${i < fields.length - 1 ? "border-b border-border" : ""}`}
              >
                <label htmlFor={key} className="text-[10px] tracking-widest uppercase text-muted-foreground">
                  {label}
                </label>
                <input
                  id={key}
                  type={type}
                  autoComplete={auto}
                  value={form[key]}
                  onChange={set(key)}
                  required={key !== "phone"}
                  placeholder={placeholder}
                  className="bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/50 py-1"
                />
              </div>
            ))}
            <button
              type="submit"
              disabled={loading}
              className="p-5 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Creating account…" : "Create Account"}
            </button>
          </form>

          <p className="text-xs tracking-wider text-muted-foreground mt-6 text-center">
            Already have an account?{" "}
            <Link to="/login" className="text-foreground hover:underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
