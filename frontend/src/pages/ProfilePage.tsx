import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/context/AuthContext"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"

const fieldStyles =
  "bg-transparent border border-border text-foreground text-sm px-3 py-2.5 outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/40 w-full"

const labelStyles = "text-[10px] tracking-widest uppercase text-muted-foreground"

function FieldRow({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-border last:border-b-0">
      <span className={labelStyles}>{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // 1. state
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const [pwCurrent, setPwCurrent] = useState("")
  const [pwNew, setPwNew] = useState("")
  const [pwConfirm, setPwConfirm] = useState("")

  // Hydrate the form once auth has loaded the user. Doing this in an effect
  // (rather than as the initial state) keeps the inputs in sync if the user
  // object changes — e.g. after a successful PATCH.
  useEffect(() => {
    if (!user) return
    setName(user.name)
    setPhone(user.phone ?? "")
  }, [user])

  // 2. mutations
  const profileMutation = useMutation({
    mutationFn: async (body: { name?: string; phone?: string | null }) => {
      const { data } = await api.patch("/api/v1/auth/me", body)
      return data
    },
    onSuccess: (updated) => {
      // Push the updated user into the auth-bound query so navbar etc. refresh.
      queryClient.setQueryData(["auth-me"], updated)
      toast({ title: "Profile updated" })
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg ?? String(d)).join(", ")
          : "Could not update profile."
      toast({ variant: "destructive", title: "Update failed", description: msg })
    },
  })

  const passwordMutation = useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) => {
      await api.post("/api/v1/auth/change-password", body)
    },
    onSuccess: () => {
      setPwCurrent("")
      setPwNew("")
      setPwConfirm("")
      toast({ title: "Password changed" })
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg ?? String(d)).join(", ")
          : "Could not change password."
      toast({ variant: "destructive", title: "Password change failed", description: msg })
    },
  })

  function submitProfile(e: FormEvent): void {
    e.preventDefault()
    if (!user) return
    // Only send fields the user actually changed — keeps server validators
    // narrow and lets a partial update pass even if other fields were never
    // populated.
    const body: { name?: string; phone?: string | null } = {}
    if (name !== user.name) body.name = name
    const trimmedPhone = phone.trim()
    if (trimmedPhone !== (user.phone ?? "")) body.phone = trimmedPhone || null
    if (Object.keys(body).length === 0) {
      toast({ title: "Nothing to update" })
      return
    }
    profileMutation.mutate(body)
  }

  function submitPassword(e: FormEvent): void {
    e.preventDefault()
    if (pwNew !== pwConfirm) {
      toast({ variant: "destructive", title: "Passwords don't match" })
      return
    }
    passwordMutation.mutate({ current_password: pwCurrent, new_password: pwNew })
  }

  if (!user) return null

  return (
    <div className="container py-16 max-w-2xl">
      <div className="mb-12">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Account</p>
        <h1 className="font-display text-6xl uppercase">Profile</h1>
      </div>

      {/* read-only identity */}
      <div className="border border-border mb-10">
        <div className="px-6 py-4 border-b border-border bg-secondary">
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Account</p>
        </div>
        <FieldRow label="Email" value={user.email} />
        <FieldRow label="Role" value={user.role} />
      </div>

      {/* editable profile */}
      <form onSubmit={submitProfile} className="border border-border mb-10">
        <div className="px-6 py-4 border-b border-border">
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Personal Info</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-px bg-border">
          <div className="bg-background flex flex-col gap-1 p-5">
            <label htmlFor="prof-name" className={labelStyles}>Full Name</label>
            <input
              id="prof-name"
              type="text"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={fieldStyles}
              required
            />
          </div>
          <div className="bg-background flex flex-col gap-1 p-5">
            <label htmlFor="prof-phone" className={labelStyles}>Phone (optional)</label>
            <input
              id="prof-phone"
              type="tel"
              autoComplete="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 555 000 0000"
              className={fieldStyles}
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={profileMutation.isPending}
          className="w-full px-6 py-4 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50 border-t border-border"
        >
          {profileMutation.isPending ? "Saving…" : "Save Profile"}
        </button>
      </form>

      {/* password */}
      <form onSubmit={submitPassword} className="border border-border">
        <div className="px-6 py-4 border-b border-border">
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Change Password</p>
        </div>
        <div className="grid sm:grid-cols-3 gap-px bg-border">
          {[
            { id: "pw-current", label: "Current",     value: pwCurrent, set: setPwCurrent, ac: "current-password" },
            { id: "pw-new",     label: "New",         value: pwNew,     set: setPwNew,     ac: "new-password" },
            { id: "pw-confirm", label: "Confirm New", value: pwConfirm, set: setPwConfirm, ac: "new-password" },
          ].map(({ id, label, value, set, ac }) => (
            <div key={id} className="bg-background flex flex-col gap-1 p-5">
              <label htmlFor={id} className={labelStyles}>{label}</label>
              <input
                id={id}
                type="password"
                autoComplete={ac}
                value={value}
                onChange={(e) => set(e.target.value)}
                className={fieldStyles}
                required
              />
            </div>
          ))}
        </div>
        <button
          type="submit"
          disabled={passwordMutation.isPending}
          className="w-full px-6 py-4 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50 border-t border-border"
        >
          {passwordMutation.isPending ? "Changing…" : "Change Password"}
        </button>
      </form>
    </div>
  )
}
