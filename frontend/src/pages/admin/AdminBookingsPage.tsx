import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO, isPast } from "date-fns"
import { Calendar, Clock, ChevronLeft, ChevronRight } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { BookingPage, BookingStatus } from "@/types"

const PAGE_SIZE = 20

const FILTERS: { label: string; value: BookingStatus | undefined }[] = [
  { label: "All",       value: undefined      },
  { label: "Confirmed", value: "confirmed"    },
  { label: "Cancelled", value: "cancelled"    },
  { label: "Completed", value: "completed"    },
]

function StatusLabel({ status }: { status: BookingStatus }) {
  return (
    <span className={cn(
      "text-[10px] tracking-widest uppercase",
      status === "confirmed" && "text-foreground",
      status === "cancelled" && "text-destructive/70",
      status === "completed" && "text-muted-foreground",
    )}>
      {status}
    </span>
  )
}

export default function AdminBookingsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<BookingStatus | undefined>(undefined)
  const [page, setPage] = useState(0)

  const offset = page * PAGE_SIZE

  const { data, isLoading } = useQuery<BookingPage>({
    queryKey: ["admin-bookings", statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
      if (statusFilter) params.set("status", statusFilter)
      return (await api.get(`/api/v1/admin/bookings?${params}`)).data
    },
  })

  const bookings = data?.items ?? []
  const total    = data?.total ?? 0
  const pageCount = Math.ceil(total / PAGE_SIZE)
  const from = total === 0 ? 0 : offset + 1
  const to   = Math.min(offset + PAGE_SIZE, total)

  function handleFilterChange(value: BookingStatus | undefined) {
    setStatusFilter(value)
    setPage(0)
  }

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/cancel`, {}),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["admin-bookings"] }); toast({ title: "Booking cancelled" }) },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/complete`, {}),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["admin-bookings"] }); toast({ title: "Marked as completed" }) },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <h1 className="font-display text-5xl uppercase">Bookings</h1>
      </div>

      {/* filters */}
      <div className="flex gap-0 border border-border mb-8">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => handleFilterChange(f.value)}
            className={cn(
              "flex-1 px-4 py-3 text-xs tracking-widest uppercase transition-colors border-r border-border last:border-r-0",
              statusFilter === f.value
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading bookings…</div>
      ) : bookings.length === 0 ? (
        <div className="border border-border p-12 text-center text-xs text-muted-foreground tracking-widest uppercase">No bookings found.</div>
      ) : (
        <>
          <div className="flex flex-col gap-0 border border-border">
            {bookings.map((booking, i) => {
              const start = parseISO(booking.start_time)
              const past  = isPast(start)
              return (
                <div
                  key={booking.id}
                  className={cn(
                    "flex flex-col sm:flex-row sm:items-center gap-4 px-6 py-5",
                    i < bookings.length - 1 && "border-b border-border",
                    booking.status !== "confirmed" && "opacity-60"
                  )}
                >
                  <div className="flex-1 flex flex-col gap-1.5 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="text-sm font-medium uppercase tracking-wide">{booking.user?.name ?? "Unknown"}</span>
                      <span className="text-xs text-muted-foreground">{booking.user?.email}</span>
                      <StatusLabel status={booking.status} />
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground tracking-wider">
                      <span className="text-foreground font-medium uppercase">{booking.service?.name ?? "—"}</span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {format(start, "EEE, MMM d yyyy")}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {format(start, "h:mm a")}
                      </span>
                      {booking.service && (
                        <span>{booking.service.duration_minutes} min · ${Number(booking.service.price).toFixed(2)}</span>
                      )}
                    </div>
                    {booking.cancellation_reason && (
                      <p className="text-xs text-muted-foreground italic">{booking.cancellation_reason}</p>
                    )}
                  </div>

                  {booking.status === "confirmed" && (
                    <div className="flex gap-2 shrink-0">
                      {!past && (
                        <button
                          onClick={() => cancelMutation.mutate(booking.id)}
                          disabled={cancelMutation.isPending}
                          className="px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      )}
                      <button
                        onClick={() => completeMutation.mutate(booking.id)}
                        disabled={completeMutation.isPending}
                        className="px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                      >
                        Complete
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* pagination */}
          <div className="flex items-center justify-between mt-6 text-xs text-muted-foreground tracking-wider">
            <span>{from}–{to} of {total} booking{total !== 1 ? "s" : ""}</span>
            <div className="flex items-center gap-0 border border-border">
              <button
                onClick={() => setPage((p) => p - 1)}
                disabled={page === 0}
                className="px-4 py-2 border-r border-border hover:bg-secondary transition-colors disabled:opacity-30"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <span className="px-5 py-2 uppercase tracking-widest">
                {page + 1} / {pageCount}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= pageCount - 1}
                className="px-4 py-2 border-l border-border hover:bg-secondary transition-colors disabled:opacity-30"
                aria-label="Next page"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
