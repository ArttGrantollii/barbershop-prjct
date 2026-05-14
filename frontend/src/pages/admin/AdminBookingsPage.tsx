import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { parseISO, isPast } from "date-fns"
import { Calendar, CalendarClock, Clock, ChevronLeft, ChevronRight, History, Plus, Search, X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { RescheduleDialog } from "@/components/RescheduleDialog"
import { salonDateShort, salonDateTimeInputToUtcIso, salonTime } from "@/lib/datetime"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking, BookingAuditEvent, BookingPage, BookingStatus, Service, StaffWithServices } from "@/types"

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

function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined) return "None"
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  return JSON.stringify(value, null, 2)
}

function AuditValueBlock({ label, values }: { label: string; values: Record<string, unknown> | null }) {
  if (!values || Object.keys(values).length === 0) return null
  return (
    <div className="border border-border px-3 py-2">
      <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-2">{label}</p>
      <dl className="grid gap-2">
        {Object.entries(values).map(([key, value]) => (
          <div key={key} className="grid sm:grid-cols-[140px_1fr] gap-1 text-xs">
            <dt className="uppercase tracking-widest text-muted-foreground">{key.replace(/_/g, " ")}</dt>
            <dd className="font-mono whitespace-pre-wrap break-words">{formatAuditValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
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
  const [historyBookingId, setHistoryBookingId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    customer_name: "",
    customer_email: "",
    customer_phone: "",
    service_id: "",
    staff_id: "",
    date: "",
    time: "",
    status: "confirmed" as "confirmed" | "completed",
    notes: "",
  })

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

  const { data: auditEvents = [], isLoading: isHistoryLoading } = useQuery<BookingAuditEvent[]>({
    queryKey: ["booking-audit-events", historyBookingId],
    enabled: !!historyBookingId,
    queryFn: async () => (await api.get(`/api/v1/admin/bookings/${historyBookingId}/audit-events`)).data,
  })

  const { data: services = [] } = useQuery<Service[]>({
    queryKey: ["admin-services"],
    queryFn: async () => (await api.get("/api/v1/admin/services")).data,
  })

  const { data: staff = [] } = useQuery<StaffWithServices[]>({
    queryKey: ["admin-staff"],
    queryFn: async () => (await api.get("/api/v1/admin/staff")).data,
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

  const createMutation = useMutation({
    mutationFn: () => {
      const start_time = salonDateTimeInputToUtcIso(`${createForm.date}T${createForm.time}`, tz)
      return api.post("/api/v1/admin/bookings", {
        service_id: createForm.service_id,
        staff_id: createForm.staff_id,
        start_time,
        status: createForm.status,
        customer_name: createForm.customer_name,
        customer_email: createForm.customer_email || null,
        customer_phone: createForm.customer_phone || null,
        notes: createForm.notes || null,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      toast({ title: createForm.status === "completed" ? "Walk-in recorded" : "Booking created" })
      setShowCreate(false)
      setCreateForm({
        customer_name: "",
        customer_email: "",
        customer_phone: "",
        service_id: "",
        staff_id: "",
        date: "",
        time: "",
        status: "confirmed",
        notes: "",
      })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const canCreate = !!createForm.customer_name.trim()
    && !!createForm.service_id
    && !!createForm.staff_id
    && !!createForm.date
    && !!createForm.time

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <h1 className="font-display text-5xl uppercase">Bookings</h1>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            New Booking
          </button>
        </div>
      </div>

      {showCreate && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (canCreate) createMutation.mutate()
          }}
          className="border border-border mb-8"
        >
          <div className="grid md:grid-cols-3 gap-px bg-border">
            <input
              value={createForm.customer_name}
              onChange={(e) => setCreateForm((f) => ({ ...f, customer_name: e.target.value }))}
              placeholder="Customer name"
              className="bg-background px-4 py-3 text-sm outline-none"
            />
            <input
              value={createForm.customer_email}
              onChange={(e) => setCreateForm((f) => ({ ...f, customer_email: e.target.value }))}
              placeholder="Email"
              type="email"
              className="bg-background px-4 py-3 text-sm outline-none"
            />
            <input
              value={createForm.customer_phone}
              onChange={(e) => setCreateForm((f) => ({ ...f, customer_phone: e.target.value }))}
              placeholder="Phone"
              className="bg-background px-4 py-3 text-sm outline-none"
            />
            <select
              value={createForm.service_id}
              onChange={(e) => setCreateForm((f) => ({ ...f, service_id: e.target.value, staff_id: "" }))}
              className="bg-background px-4 py-3 text-sm outline-none"
            >
              <option value="">Service</option>
              {services.filter((s) => s.is_active).map((service) => (
                <option key={service.id} value={service.id}>{service.name}</option>
              ))}
            </select>
            <select
              value={createForm.staff_id}
              onChange={(e) => setCreateForm((f) => ({ ...f, staff_id: e.target.value }))}
              className="bg-background px-4 py-3 text-sm outline-none"
            >
              <option value="">Stylist</option>
              {staff
                .filter((person) => person.is_active && (!createForm.service_id || person.service_ids.includes(createForm.service_id)))
                .map((person) => (
                  <option key={person.id} value={person.id}>{person.name}</option>
                ))}
            </select>
            <select
              value={createForm.status}
              onChange={(e) => setCreateForm((f) => ({ ...f, status: e.target.value as "confirmed" | "completed" }))}
              className="bg-background px-4 py-3 text-sm outline-none"
            >
              <option value="confirmed">Scheduled booking</option>
              <option value="completed">Completed walk-in</option>
            </select>
            <input
              type="date"
              value={createForm.date}
              onChange={(e) => setCreateForm((f) => ({ ...f, date: e.target.value }))}
              className="bg-background px-4 py-3 text-sm outline-none [color-scheme:dark]"
            />
            <input
              type="time"
              value={createForm.time}
              onChange={(e) => setCreateForm((f) => ({ ...f, time: e.target.value }))}
              className="bg-background px-4 py-3 text-sm outline-none [color-scheme:dark]"
            />
            <input
              value={createForm.notes}
              onChange={(e) => setCreateForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Notes"
              className="bg-background px-4 py-3 text-sm outline-none"
            />
          </div>
          <div className="flex justify-end gap-2 p-3 border-t border-border">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canCreate || createMutation.isPending}
              className="px-4 py-2 text-xs tracking-widest uppercase bg-foreground text-background disabled:opacity-40"
            >
              Save
            </button>
          </div>
        </form>
      )}

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
              const customerName = booking.user?.name ?? booking.customer_name ?? "Walk-in"
              const customerEmail = booking.user?.email ?? booking.customer_email
              const customerPhone = booking.user?.phone ?? booking.customer_phone
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
                      <span className="text-sm font-medium uppercase tracking-wide">{customerName}</span>
                      {customerEmail && (
                        <a
                          href={`mailto:${customerEmail}`}
                          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {customerEmail}
                        </a>
                      )}
                      {customerPhone && (
                        <a
                          href={`tel:${customerPhone}`}
                          className="text-xs text-muted-foreground hover:text-foreground transition-colors tabular-nums"
                        >
                          {customerPhone}
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
                    {booking.notes && (
                      <p className="text-xs text-muted-foreground">
                        <span className="uppercase tracking-widest text-[10px] mr-2">Notes</span>
                        {booking.notes}
                      </p>
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
                  <button
                    onClick={() => setHistoryBookingId((id) => id === booking.id ? null : booking.id)}
                    className="flex items-center gap-2 px-4 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors shrink-0"
                  >
                    <History className="h-3.5 w-3.5" />
                    History
                  </button>
                  {historyBookingId === booking.id && (
                    <div className="sm:basis-full border-t border-border pt-4 mt-1">
                      {isHistoryLoading ? (
                        <p className="text-xs text-muted-foreground tracking-widest uppercase">Loading history...</p>
                      ) : auditEvents.length === 0 ? (
                        <p className="text-xs text-muted-foreground tracking-widest uppercase">No history recorded.</p>
                      ) : (
                        <div className="grid gap-2">
                          {auditEvents.map((event) => {
                            const hasDetails = !!event.previous_values || !!event.new_values
                            return (
                              <div key={event.id} className="text-xs border border-border px-3 py-2">
                                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-3">
                                    <span className="font-medium uppercase tracking-widest">{event.action.replace(/_/g, " ")}</span>
                                    <span className="text-muted-foreground uppercase tracking-widest">{event.actor_role}</span>
                                  </div>
                                  <span className="text-muted-foreground tabular-nums">{salonDateShort(parseISO(event.created_at), tz)} {salonTime(parseISO(event.created_at), tz)}</span>
                                </div>
                                {hasDetails && (
                                  <details className="mt-3">
                                    <summary className="cursor-pointer text-[10px] tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors">
                                      Details
                                    </summary>
                                    <div className="grid md:grid-cols-2 gap-2 mt-3">
                                      <AuditValueBlock label="Previous" values={event.previous_values} />
                                      <AuditValueBlock label="New" values={event.new_values} />
                                    </div>
                                  </details>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
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
