import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import api from "@/lib/api"

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const [state, setState] = useState<"loading" | "success" | "error">("loading")
  const token = params.get("token") ?? ""

  useEffect(() => {
    if (!token) {
      setState("error")
      return
    }
    api.post("/api/v1/auth/verify-email", { token })
      .then(() => setState("success"))
      .catch(() => setState("error"))
  }, [token])

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Account</p>
          <h1 className="font-display text-5xl uppercase">Verify Email</h1>
        </div>
        <div className="border border-border p-6 text-sm text-muted-foreground">
          {state === "loading" && "Verifying your email..."}
          {state === "success" && "Email verified. You can continue using your account."}
          {state === "error" && "This verification link is invalid or expired."}
        </div>
        <p className="text-xs tracking-wider text-muted-foreground mt-6 text-center">
          <Link to="/login" className="text-foreground hover:underline underline-offset-4">Back to sign in</Link>
        </p>
      </div>
    </div>
  )
}
