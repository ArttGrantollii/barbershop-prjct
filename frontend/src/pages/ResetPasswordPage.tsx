import { useState } from "react"
import type { FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [loading, setLoading] = useState(false)
  const token = params.get("token") ?? ""

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      toast({ variant: "destructive", title: "Passwords do not match" })
      return
    }
    setLoading(true)
    try {
      await api.post("/api/v1/auth/reset-password", { token, new_password: password })
      toast({ title: "Password updated" })
      navigate("/login", { replace: true })
    } catch (err: any) {
      toast({ variant: "destructive", title: err?.response?.data?.detail ?? "Reset failed" })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Account Recovery</p>
          <h1 className="font-display text-5xl uppercase">New Password</h1>
        </div>
        {!token ? (
          <div className="border border-border p-6 text-sm text-muted-foreground">Reset link is missing a token.</div>
        ) : (
          <form onSubmit={submit} className="flex flex-col border border-border">
            <div className="flex flex-col gap-1 p-5 border-b border-border">
              <label htmlFor="password" className="text-[10px] tracking-widest uppercase text-muted-foreground">Password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="bg-transparent text-sm outline-none py-1" />
            </div>
            <div className="flex flex-col gap-1 p-5 border-b border-border">
              <label htmlFor="confirm" className="text-[10px] tracking-widest uppercase text-muted-foreground">Confirm Password</label>
              <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="bg-transparent text-sm outline-none py-1" />
            </div>
            <button disabled={loading} className="p-5 text-xs tracking-widest uppercase bg-foreground text-background disabled:opacity-50">
              {loading ? "Updating..." : "Update Password"}
            </button>
          </form>
        )}
        <p className="text-xs tracking-wider text-muted-foreground mt-6 text-center">
          <Link to="/login" className="text-foreground hover:underline underline-offset-4">Back to sign in</Link>
        </p>
      </div>
    </div>
  )
}
