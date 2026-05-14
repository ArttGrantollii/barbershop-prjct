import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { BusinessHours } from "@/types"

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

type DayState = { open_time: string; close_time: string; is_closed: boolean }

function toInputTime(t: string) {
  return t.substring(0, 5)
}

const timeInputStyles = "bg-transparent border border-border text-foreground text-sm px-3 py-2 outline-none focus:border-foreground transition-colors [color-scheme:dark]"

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

  const save = (day: number) => saveMutation.mutate({ day, body: rows[day] })

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <h1 className="font-display text-5xl uppercase">Business Hours</h1>
      </div>

      {isLoading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading…</div>
      ) : (
        <div className="flex flex-col gap-0 border border-border">
          {Array.from({ length: 7 }, (_, i) => i).map((day, idx) => {
            const row = rows[day]
            if (!row) return null
            const invalidRange = !row.is_closed && row.close_time <= row.open_time
            return (
              <div
                key={day}
                className={cn(
                  "flex flex-wrap items-center gap-4 px-6 py-5",
                  idx < 6 && "border-b border-border",
                  row.is_closed && "opacity-50"
                )}
              >
                <span className="w-24 text-xs tracking-widest uppercase font-medium shrink-0">
                  {DAY_NAMES[day]}
                </span>

                <label className="flex items-center gap-2.5 shrink-0 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={row.is_closed}
                    onChange={(e) => update(day, "is_closed", e.target.checked)}
                    className="h-3.5 w-3.5 accent-foreground"
                  />
                  <span className="text-xs tracking-widest uppercase text-muted-foreground">Closed</span>
                </label>

                {!row.is_closed && (
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] tracking-widest uppercase text-muted-foreground">Open</span>
                      <input
                        type="time"
                        value={row.open_time}
                        onChange={(e) => update(day, "open_time", e.target.value)}
                        className={timeInputStyles}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] tracking-widest uppercase text-muted-foreground">Close</span>
                      <input
                        type="time"
                        value={row.close_time}
                        onChange={(e) => update(day, "close_time", e.target.value)}
                        className={timeInputStyles}
                      />
                    </div>
                  </div>
                )}

                <button
                  onClick={() => save(day)}
                  disabled={saveMutation.isPending || invalidRange}
                  title={invalidRange ? "Close time must be after open time" : undefined}
                  className="ml-auto text-xs tracking-widest uppercase border border-border px-5 py-2 hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
