import { useMemo, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { parseISO, isPast } from "date-fns"
import { Link } from "react-router-dom"
import { Calendar, CalendarPlus, Clock } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { RescheduleDialog } from "@/components/RescheduleDialog"
import { salonDateMedium, salonTime } from "@/lib/datetime"
import { bookingToIcs, downloadIcs } from "@/lib/ics"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking } from "@/types"

type Tab = "upcoming" | "past"

function StatusPill({ status }: { status: Booking["status"] }) {
  return (
    <span className={cn(
      "text-[10px] tracking-widest uppercase px-2.5 py-1 border",
      status === "confirmed"  && "border-foreground/30 text-foreground",
      status === "cancelled"  && "border-destructive/30 text-destructive/70",
      status === "completed"  && "border-muted-foreground/30 text-muted-foreground",
      status === "no_show"    && "border-destructive/30 text-destructive/70",
    )}>
      {status === "no_show" ? "no-show" : status}
    </span>
  )
}

// "Upcoming" = confirmed bookings whose start time is still in the future.
// Everything else (past confirmed, cancelled, completed) is "past" — that
// keeps the upcoming list focused on actionable bookings only.
function isUpcoming(booking: Booking): boolean {
  return booking.status === "confirmed" && !isPast(parseISO(booking.start_time))
}

export default function MyBookingsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone

  const [tab, setTab] = useState<Tab>("upcoming")
  const [rescheduling, setRescheduling] = useState<Booking | null>(null)

  const { data: bookings, isLoading } = useQuery<Booking[]>({
    queryKey: ["my-bookings"],
    queryFn: async () => (await api.get("/api/v1/bookings/my")).data,
  })

  const cancelMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/api/v1/bookings/${id}/cancel`, { reason: null })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["slots"] })
      toast({ title: "Booking cancelled" })
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not cancel. Please try again."
      toast({ variant: "destructive", title: "Error", description: msg })
    },
  })

  const upcoming = useMemo(
    () => (bookings ?? []).filter(isUpcoming).sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [bookings],
  )
  const past = useMemo(
    () => (bookings ?? []).filter((b) => !isUpcoming(b)).sort((a, b) => b.start_time.localeCompare(a.start_time)),
    [bookings],
  )
  const visible = tab === "upcoming" ? upcoming : past

  return (
    <div className="container py-16 max-w-3xl">
      <div className="mb-12">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Your Appointments</p>
        <h1 className="font-display text-6xl uppercase">My Bookings</h1>
      </div>

      {/* tabs */}
      <div className="flex gap-0 border border-border mb-8">
        {([
          { value: "upcoming", label: "Upcoming", count: upcoming.length },
          { value: "past",     label: "Past",     count: past.length     },
        ] as const).map((t, i) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-3 text-xs tracking-widest uppercase transition-colors",
              i === 0 && "border-r border-border",
              tab === t.value
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary",
            )}
          >
            <span>{t.label}</span>
            <span className={cn(
              "text-[10px]",
              tab === t.value ? "text-background/70" : "text-muted-foreground/60",
            )}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="border border-border p-8 text-xs text-muted-foreground tracking-widest uppercase">
          Loading bookings…
        </div>
      ) : visible.length === 0 ? (
        <div className="border border-border">
          <div className="p-16 flex flex-col items-center text-center gap-6">
            <div className="w-12 h-px bg-border" />
            <div>
              <p className="text-sm font-medium uppercase tracking-widest mb-2">
                {tab === "upcoming" ? "No upcoming bookings" : "No past bookings"}
              </p>
              <p className="text-xs text-muted-foreground tracking-wider">
                {tab === "upcoming"
                  ? "Book your next appointment to get started."
                  : "Cancelled and completed bookings will appear here."}
              </p>
            </div>
            {tab === "upcoming" && (
              <Link
                to="/book"
                className="text-xs tracking-widest uppercase bg-foreground text-background px-8 py-3 hover:bg-foreground/90 transition-colors"
              >
                Book Now
              </Link>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-0 border border-border">
          {visible.map((booking, i) => {
            const startTime = parseISO(booking.start_time)
            const canCancel = booking.status === "confirmed" && !isPast(startTime)
            return (
              <div
                key={booking.id}
                className={cn(
                  "p-6 flex flex-col sm:flex-row sm:items-center gap-5",
                  i < visible.length - 1 && "border-b border-border",
                  booking.status !== "confirmed" && "opacity-60"
                )}
              >
                <div className="flex-1 flex flex-col gap-2 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-sm font-medium uppercase tracking-widest">
                      {booking.service?.name ?? "Appointment"}
                    </p>
                    <StatusPill status={booking.status} />
                  </div>

                  <div className="flex flex-wrap gap-4 text-xs text-muted-foreground tracking-wider">
                    <span className="flex items-center gap-1.5">
                      <Calendar className="h-3 w-3" />
                      {salonDateMedium(startTime, tz)}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3" />
                      {salonTime(startTime, tz)}
                    </span>
                  </div>

                  {booking.service && (
                    <p className="text-xs text-muted-foreground tracking-wider">
                      {booking.service.duration_minutes} min · ${Number(booking.service.price).toFixed(2)}
                      {booking.staff && ` · ${booking.staff.name}`}
                    </p>
                  )}

                  {booking.cancellation_reason && (
                    <p className="text-xs text-muted-foreground italic">{booking.cancellation_reason}</p>
                  )}
                </div>

                {canCancel && (
                  <div className="shrink-0 flex gap-2 flex-wrap">
                    <button
                      onClick={() =>
                        downloadIcs(
                          `vendos-${booking.id}.ics`,
                          bookingToIcs({ booking, salonName: business?.name ?? "Vendos Salon" }),
                        )
                      }
                      className="flex items-center gap-1.5 text-xs tracking-widest uppercase border border-border px-4 py-2.5 hover:bg-secondary transition-colors"
                      aria-label="Add to calendar"
                      title="Download .ics calendar event"
                    >
                      <CalendarPlus className="h-3 w-3" />
                      <span className="hidden sm:inline">Calendar</span>
                    </button>
                    <button
                      onClick={() => setRescheduling(booking)}
                      className="text-xs tracking-widest uppercase border border-border px-4 py-2.5 hover:bg-secondary transition-colors"
                    >
                      Reschedule
                    </button>
                    <button
                      onClick={() => cancelMutation.mutate(booking.id)}
                      disabled={cancelMutation.isPending}
                      className="text-xs tracking-widest uppercase border border-border px-4 py-2.5 hover:bg-secondary transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="mt-10 flex justify-center">
        <Link
          to="/book"
          className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
        >
          + Book Another Appointment
        </Link>
      </div>

      {rescheduling && (
        <RescheduleDialog
          booking={rescheduling}
          open={!!rescheduling}
          onClose={() => setRescheduling(null)}
        />
      )}
    </div>
  )
}
