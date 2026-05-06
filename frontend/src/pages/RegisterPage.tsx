import { useState } from "react"
import type { ChangeEvent, FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Scissors } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/hooks/use-toast"

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
      navigate("/", { replace: true })
    } catch (err: any) {
      if (!err.response) {
        toast({ variant: "destructive", title: "Cannot reach server", description: "The backend is not responding. Make sure Docker is running." })
      } else {
        const detail = err.response.data?.detail
        let msg = "Registration failed. Please try again."
        if (typeof detail === "string") {
          msg = detail
        } else if (Array.isArray(detail)) {
          msg = detail.map((d: any) => d.msg ?? String(d)).join(", ")
        }
        toast({ variant: "destructive", title: "Error", description: msg })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center">
            <Scissors className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Create an account</h1>
          <p className="text-sm text-muted-foreground">Book appointments and manage your visits</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">Full name</Label>
            <Input id="name" value={form.name} onChange={set("name")} required autoComplete="name" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={form.email} onChange={set("email")} required autoComplete="email" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone">Phone <span className="text-muted-foreground">(optional)</span></Label>
            <Input id="phone" type="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={form.password} onChange={set("password")} required autoComplete="new-password" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirm">Confirm password</Label>
            <Input id="confirm" type="password" value={form.confirm} onChange={set("confirm")} required autoComplete="new-password" />
          </div>
          <Button type="submit" className="mt-2" disabled={loading}>
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-foreground underline underline-offset-4">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
