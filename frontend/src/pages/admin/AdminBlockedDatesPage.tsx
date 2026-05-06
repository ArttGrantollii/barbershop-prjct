import { useState } from "react"
import type { FormEvent } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { format, parseISO } from "date-fns"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"
import type { BlockedDate } from "@/types"

export default function AdminBlockedDatesPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [date, setDate] = useState("")
  const [reason, setReason] = useState("")

  const today = new Date().toISOString().split("T")[0]

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
      <h1 className="text-xl font-bold tracking-tight mb-6">Blocked Dates</h1>

      {/* add form */}
      <Card className="mb-6">
        <CardContent className="p-5">
          <p className="font-medium text-sm mb-3">Block a Date</p>
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="flex flex-col gap-1.5 flex-1">
              <Label htmlFor="block-date">Date</Label>
              <Input
                id="block-date"
                type="date"
                min={today}
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="max-w-xs"
              />
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <Label htmlFor="block-reason">Reason <span className="text-muted-foreground">(optional)</span></Label>
              <Input
                id="block-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Public holiday"
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={addMutation.isPending}>
                {addMutation.isPending ? "Saving…" : "Block Date"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : blocked.length === 0 ? (
        <p className="text-sm text-muted-foreground">No blocked dates.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {blocked.map((bd) => (
            <div key={bd.id} className="flex items-center justify-between px-4 py-3 rounded-xl border">
              <div>
                <p className="text-sm font-medium">{format(parseISO(bd.date), "EEEE, MMMM d, yyyy")}</p>
                {bd.reason && <p className="text-xs text-muted-foreground mt-0.5">{bd.reason}</p>}
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => deleteMutation.mutate(bd.id)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
