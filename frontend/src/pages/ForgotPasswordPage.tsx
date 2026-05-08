import { useState } from "react"
import type { FormEvent } from "react"
import { Link } from "react-router-dom"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"

export default function ForgotPasswordPage() {
  const { toast } = useToast()
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await api.post("/api/v1/auth/forgot-password", { email })
      setSent(true)
    } catch {
      toast({ variant: "destructive", title: "Request failed" })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Account Recovery</p>
          <h1 className="font-display text-5xl uppercase">Reset Password</h1>
        </div>
        {sent ? (
          <div className="border border-border p-6 text-sm text-muted-foreground">
            If that email exists, a reset link has been sent.
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col border border-border">
            <div className="flex flex-col gap-1 p-5 border-b border-border">
              <label htmlFor="email" className="text-[10px] tracking-widest uppercase text-muted-foreground">Email Address</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="bg-transparent text-sm outline-none py-1" />
            </div>
            <button disabled={loading} className="p-5 text-xs tracking-widest uppercase bg-foreground text-background disabled:opacity-50">
              {loading ? "Sending..." : "Send Reset Link"}
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
