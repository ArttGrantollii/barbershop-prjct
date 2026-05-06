import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { BusinessHours } from "@/types"

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

type DayState = { open_time: string; close_time: string; is_closed: boolean }

function toInputTime(t: string) {
  return t.substring(0, 5)
}

export default function AdminHoursPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<Record<number, DayState>>({})

  const { data: hours = [], isLoading } = useQuery<BusinessHours[]>({
    queryKey: ["admin-hours"],
    queryFn: async () => (await api.get("/api/v1/admin/business-hours")).data,
  })

  useEffect(() => {
    if (!hours.length) return
    const init: Record<number, DayState> = {}
    hours.forEach((h) => {
      init[h.day_of_week] = {
        open_time: toInputTime(h.open_time),
        close_time: toInputTime(h.close_time),
        is_closed: h.is_closed,
      }
    })
    setRows(init)
  }, [hours])

  const saveMutation = useMutation({
    mutationFn: ({ day, body }: { day: number; body: object }) =>
      api.put(`/api/v1/admin/business-hours/${day}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-hours"] })
      toast({ title: "Hours updated" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const update = (day: number, k: keyof DayState, v: string | boolean) =>
    setRows((r) => ({ ...r, [day]: { ...r[day], [k]: v } }))

  const save = (day: number) => {
    const row = rows[day]
    saveMutation.mutate({ day, body: row })
  }

  return (
    <div>
      <h1 className="text-xl font-bold tracking-tight mb-6">Business Hours</h1>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 7 }, (_, i) => i).map((day) => {
            const row = rows[day]
            if (!row) return null
            return (
              <div key={day} className={cn("flex items-center gap-4 p-4 rounded-xl border", row.is_closed && "opacity-60")}>
                <span className="w-28 text-sm font-medium shrink-0">{DAY_NAMES[day]}</span>

                <label className="flex items-center gap-2 shrink-0 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={row.is_closed}
                    onChange={(e) => update(day, "is_closed", e.target.checked)}
                    className="h-4 w-4 rounded"
                  />
                  <span className="text-sm text-muted-foreground">Closed</span>
                </label>

                {!row.is_closed && (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">Open</span>
                      <input
                        type="time"
                        value={row.open_time}
                        onChange={(e) => update(day, "open_time", e.target.value)}
                        className="border border-input rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">Close</span>
                      <input
                        type="time"
                        value={row.close_time}
                        onChange={(e) => update(day, "close_time", e.target.value)}
                        className="border border-input rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                  </>
                )}

                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto"
                  onClick={() => save(day)}
                  disabled={saveMutation.isPending}
                >
                  Save
                </Button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
