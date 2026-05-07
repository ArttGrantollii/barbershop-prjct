import { useState } from "react"
import type { FormEvent } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { format, parseISO } from "date-fns"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDayKey } from "@/lib/datetime"
import api from "@/lib/api"
import type { BlockedDate } from "@/types"

const inputStyles = "bg-transparent border border-border text-foreground text-sm px-3 py-2.5 outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/40 w-full [color-scheme:dark]"

export default function AdminBlockedDatesPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [date, setDate] = useState("")
  const [reason, setReason] = useState("")

  // Salon-local today, not browser-local — admins managing the salon from
  // another timezone would otherwise see the wrong "earliest blockable" date.
  const { data: business } = useBusinessInfo()
  const today = salonDayKey(new Date(), business?.timezone)

  const { data: blocked = [], isLoading } = useQuery<BlockedDate[]>({
    queryKey: ["admin-blocked-dates"],
    queryFn: async () => (await api.get("/api/v1/admin/blocked-dates")).data,
  })

  const addMutation = useMutation({
    mutationFn: (body: object) => api.post("/api/v1/admin/blocked-dates", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-blocked-dates"] })
      setDate("")
      setReason("")
      toast({ title: "Date blocked" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/blocked-dates/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-blocked-dates"] })
      toast({ title: "Date unblocked" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    addMutation.mutate({ date, reason: reason || null })
  }

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <h1 className="font-display text-5xl uppercase">Blocked Dates</h1>
      </div>

      {/* add form */}
      <div className="border border-border mb-8">
        <div className="px-6 py-4 border-b border-border">
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Block a Date</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="flex flex-col sm:flex-row gap-px bg-border">
            <div className="bg-background flex flex-col gap-1 p-5 flex-1">
              <label htmlFor="block-date" className="text-[10px] tracking-widest uppercase text-muted-foreground">Date</label>
              <input
                id="block-date"
                type="date"
                min={today}
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className={inputStyles}
              />
            </div>
            <div className="bg-background flex flex-col gap-1 p-5 flex-1">
              <label htmlFor="block-reason" className="text-[10px] tracking-widest uppercase text-muted-foreground">Reason (optional)</label>
              <input
                id="block-reason"
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Public holiday"
                className={inputStyles}
              />
            </div>
          </div>
          <div className="border-t border-border">
            <button
              type="submit"
              disabled={addMutation.isPending}
              className="w-full px-6 py-4 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
            >
              {addMutation.isPending ? "Saving…" : "Block Date"}
            </button>
          </div>
        </form>
      </div>

      {isLoading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading…</div>
      ) : blocked.length === 0 ? (
        <div className="border border-border p-12 text-center text-xs text-muted-foreground tracking-widest uppercase">No blocked dates.</div>
      ) : (
        <div className="flex flex-col gap-0 border border-border">
          {blocked.map((bd, i) => (
            <div
              key={bd.id}
              className={`flex items-center justify-between px-6 py-5 ${i < blocked.length - 1 ? "border-b border-border" : ""}`}
            >
              <div>
                <p className="text-sm font-medium uppercase tracking-wide">{format(parseISO(bd.date), "EEEE, MMMM d, yyyy")}</p>
                {bd.reason && <p className="text-xs text-muted-foreground tracking-wider mt-1">{bd.reason}</p>}
              </div>
              <button
                onClick={() => deleteMutation.mutate(bd.id)}
                disabled={deleteMutation.isPending}
                className="p-2.5 border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                aria-label="Remove"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
