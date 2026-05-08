import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { parseISO, isPast } from "date-fns"
import { Calendar, CalendarClock, Clock, ChevronLeft, ChevronRight, Search, X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { RescheduleDialog } from "@/components/RescheduleDialog"
import { salonDateShort, salonTime } from "@/lib/datetime"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking, BookingPage, BookingStatus } from "@/types"

const PAGE_SIZE = 20

const FILTERS: { label: string; value: BookingStatus | undefined }[] = [
  { label: "All",       value: undefined      },
  { label: "Confirmed", value: "confirmed"    },
  { label: "Completed", value: "completed"    },
  { label: "Cancelled", value: "cancelled"    },
  { label: "No-show",   value: "no_show"      },
]

function StatusLabel({ status }: { status: BookingStatus }) {
  return (
    <span className={cn(
      "text-[10px] tracking-widest uppercase",
      status === "confirmed" && "text-foreground",
      status === "cancelled" && "text-destructive/70",
      status === "completed" && "text-muted-foreground",
      status === "no_show"   && "text-destructive/70",
    )}>
      {status === "no_show" ? "no-show" : status}
    </span>
  )
}

export default function AdminBookingsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone

  // Filter state. `searchInput` is the controlled value of the text box;
  // `searchTerm` is the debounced version we actually send to the API,
  // so a fast typist doesn't fire a request per keystroke.
  const [statusFilter, setStatusFilter] = useState<BookingStatus | undefined>(undefined)
  const [searchInput, setSearchInput] = useState("")
  const [searchTerm, setSearchTerm] = useState("")
  const [startFrom, setStartFrom] = useState("")
  const [startTo, setStartTo] = useState("")
  const [page, setPage] = useState(0)
  const [rescheduleBooking, setRescheduleBooking] = useState<Booking | null>(null)

  // Debounce: commit `searchInput` to `searchTerm` after 300ms of idle typing.
  useEffect(() => {
    const id = setTimeout(() => setSearchTerm(searchInput.trim()), 300)
    return () => clearTimeout(id)
  }, [searchInput])

  // Any filter change should reset to page 0 — otherwise the user might land
  // on an empty page (e.g. searching while on page 5 of an unfiltered list).
  useEffect(() => {
    setPage(0)
  }, [statusFilter, searchTerm, startFrom, startTo])

  const offset = page * PAGE_SIZE

  const { data, isLoading } = useQuery<BookingPage>({
    queryKey: ["admin-bookings", statusFilter, searchTerm, startFrom, startTo, page],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
      if (statusFilter) params.set("status", statusFilter)
      if (searchTerm)   params.set("q", searchTerm)
      if (startFrom)    params.set("start_from", startFrom)
      if (startTo)      params.set("start_to", startTo)
      return (await api.get(`/api/v1/admin/bookings?${params}`)).data
    },
  })

  const bookings = data?.items ?? []
  const total    = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const from = total === 0 ? 0 : offset + 1
  const to   = Math.min(offset + PAGE_SIZE, total)

  const hasActiveFilters = !!searchTerm || !!startFrom || !!startTo
  function clearAllFilters(): void {
    setSearchInput("")
    setSearchTerm("")
    setStartFrom("")
    setStartTo("")
  }

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/cancel`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      toast({ title: "Booking cancelled" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/complete`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      toast({ title: "Marked as completed" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const noShowMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/no-show`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      toast({ title: "Marked as no-show" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <h1 className="font-display text-5xl uppercase">Bookings</h1>
      </div>

      {/* search + date range */}
      <div className="border border-border mb-px">
        <div className="grid sm:grid-cols-[1fr_auto_auto] gap-px bg-border">
          <div className="bg-background flex items-center gap-2 px-4 py-2.5">
            <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by customer name or email…"
              className="bg-transparent text-sm outline-none flex-1 placeholder:text-muted-foreground/40"
              aria-label="Search bookings"
            />
          </div>
          <div className="bg-background flex items-center gap-2 px-4 py-2.5">
            <span className="text-[10px] tracking-widest uppercase text-muted-foreground shrink-0">From</span>
            <input
              type="date"
              value={startFrom}
              onChange={(e) => setStartFrom(e.target.value)}
              max={startTo || undefined}
              className="bg-transparent text-sm outline-none [color-scheme:dark]"
              aria-label="From date"
            />
          </div>
          <div className="bg-background flex items-center gap-2 px-4 py-2.5">
            <span className="text-[10px] tracking-widest uppercase text-muted-foreground shrink-0">To</span>
            <input
              type="date"
              value={startTo}
              onChange={(e) => setStartTo(e.target.value)}
              min={startFrom || undefined}
              className="bg-transparent text-sm outline-none [color-scheme:dark]"
              aria-label="To date"
            />
          </div>
        </div>
        {hasActiveFilters && (
          <div className="flex items-center justify-between gap-3 px-4 py-2 border-t border-border bg-secondary">
            <span className="text-[10px] tracking-widest uppercase text-muted-foreground">
              {total} match{total === 1 ? "" : "es"}
            </span>
            <button
              onClick={clearAllFilters}
              className="flex items-center gap-1.5 text-[10px] tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3 w-3" /> Clear
            </button>
          </div>
        )}
      </div>

      {/* status tabs */}
      <div className="flex gap-0 border border-border mb-8">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => setStatusFilter(f.value)}
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
                      <a
                        href={`mailto:${booking.user?.email ?? ""}`}
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {booking.user?.email}
                      </a>
                      {booking.user?.phone && (
                        <a
                          href={`tel:${booking.user.phone}`}
                          className="text-xs text-muted-foreground hover:text-foreground transition-colors tabular-nums"
                        >
                          {booking.user.phone}
                        </a>
                      )}
                      <StatusLabel status={booking.status} />
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground tracking-wider">
                      <span className="text-foreground font-medium uppercase">{booking.service?.name ?? "—"}</span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {salonDateShort(start, tz)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {salonTime(start, tz)}
                      </span>
                      {booking.service && (
                        <span>{booking.service.duration_minutes} min · ${Number(booking.service.price).toFixed(2)}</span>
                      )}
                      {booking.staff && <span>{booking.staff.name}</span>}
                    </div>
                    {booking.cancellation_reason && (
                      <p className="text-xs text-muted-foreground italic">{booking.cancellation_reason}</p>
                    )}
                  </div>

                  {booking.status === "confirmed" && (
                    <div className="flex gap-2 shrink-0 flex-wrap">
                      {!past ? (
                        <>
                          <button
                            onClick={() => setRescheduleBooking(booking)}
                            className="flex items-center gap-2 px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
                          >
                            <CalendarClock className="h-3.5 w-3.5" />
                            Reschedule
                          </button>
                          <button
                            onClick={() => cancelMutation.mutate(booking.id)}
                            disabled={cancelMutation.isPending}
                            className="px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => noShowMutation.mutate(booking.id)}
                          disabled={noShowMutation.isPending}
                          className="px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                        >
                          No-show
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
      {rescheduleBooking && (
        <RescheduleDialog
          booking={rescheduleBooking}
          open={!!rescheduleBooking}
          admin
          onClose={() => setRescheduleBooking(null)}
        />
      )}
    </div>
  )
}
