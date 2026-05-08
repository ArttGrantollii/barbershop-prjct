import { Link, useLocation, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Calendar, CalendarPlus, Check, Clock } from "lucide-react"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDateLong, salonTime, salonTzAbbr } from "@/lib/datetime"
import { bookingToIcs, downloadIcs } from "@/lib/ics"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking } from "@/types"

// State the BookPage hands us when navigating here. Lets the confirmation
// render instantly without a round-trip; on refresh we fall back to the GET.
interface LocationState {
  booking?: Booking
}

export default function BookingConfirmationPage() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const seeded = (location.state as LocationState | null)?.booking
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone
  const tzAbbr = salonTzAbbr(tz)

  const { data: booking, isLoading, isError } = useQuery<Booking>({
    queryKey: ["booking", id],
    queryFn: async () => (await api.get(`/api/v1/bookings/${id}`)).data,
    enabled: !!id,
    initialData: seeded && seeded.id === id ? seeded : undefined,
  })

  if (isLoading) {
    return (
      <div className="container py-16 max-w-2xl">
        <div className="border border-border p-8 text-xs text-muted-foreground tracking-widest uppercase">
          Loading…
        </div>
      </div>
    )
  }

  if (isError || !booking) {
    return (
      <div className="container py-16 max-w-2xl">
        <div className="border border-border p-12 flex flex-col items-center text-center gap-6">
          <div>
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Not found</p>
            <h1 className="font-display text-4xl uppercase">Booking unavailable</h1>
          </div>
          <p className="text-xs text-muted-foreground tracking-wider max-w-sm">
            We couldn't find this booking. It may have been cancelled, or the link may be wrong.
          </p>
          <Link
            to="/my-bookings"
            className="text-xs tracking-widest uppercase bg-foreground text-background px-8 py-3 hover:bg-foreground/90 transition-colors"
          >
            View my bookings
          </Link>
        </div>
      </div>
    )
  }

  const cancelled = booking.status === "cancelled"

  return (
    <div className="container py-16 max-w-2xl">
      {/* hero — green check + status */}
      <div className="flex flex-col items-center text-center mb-10">
        <div className={cn(
          "h-14 w-14 rounded-full flex items-center justify-center mb-6",
          cancelled
            ? "border border-destructive/30 text-destructive/70"
            : "bg-foreground text-background",
        )}>
          <Check className="h-6 w-6" />
        </div>
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">
          {cancelled ? "Cancelled" : "You're booked"}
        </p>
        <h1 className="font-display text-5xl uppercase leading-none">
          {cancelled ? "Booking cancelled" : "See you soon."}
        </h1>
      </div>

      {/* summary */}
      <div className="border border-border">
        {[
          { label: "Service",   value: booking.service?.name ?? "—" },
          { label: "Stylist",   value: booking.staff?.name ?? "—" },
          { label: "Date",      value: salonDateLong(booking.start_time, tz) },
          { label: "Time",      value: `${salonTime(booking.start_time, tz)}${tzAbbr ? ` ${tzAbbr}` : ""}` },
          { label: "Duration",  value: booking.service ? `${booking.service.duration_minutes} minutes` : "—" },
          { label: "Booking ID", value: booking.id.slice(0, 8) },
        ].map(({ label, value }, i, arr) => (
          <div
            key={label}
            className={cn(
              "flex items-center justify-between px-6 py-4",
              i < arr.length - 1 && "border-b border-border",
            )}
          >
            <span className="text-xs tracking-widest uppercase text-muted-foreground">{label}</span>
            <span className="text-sm font-medium tabular-nums">{value}</span>
          </div>
        ))}
        {booking.service && (
          <div className="flex items-center justify-between px-6 py-5 border-t border-border bg-secondary">
            <span className="text-xs tracking-widest uppercase">Total</span>
            <span className="text-xl font-semibold tracking-wide">
              ${Number(booking.service.price).toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* meta info */}
      <div className="mt-6 flex flex-wrap gap-4 text-xs text-muted-foreground tracking-wider">
        <span className="flex items-center gap-1.5">
          <Calendar className="h-3 w-3" />
          {salonDateLong(booking.start_time, tz)}
        </span>
        <span className="flex items-center gap-1.5">
          <Clock className="h-3 w-3" />
          {salonTime(booking.start_time, tz)}{tzAbbr ? ` ${tzAbbr}` : ""}
        </span>
      </div>

      {/* actions */}
      <div className="mt-10 flex flex-col sm:flex-row gap-3">
        {!cancelled && (
          <button
            onClick={() =>
              downloadIcs(
                `vendos-${booking.id}.ics`,
                bookingToIcs({ booking, salonName: business?.name ?? "Vendos Salon" }),
              )
            }
            className="flex items-center justify-center gap-2 px-6 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors"
          >
            <CalendarPlus className="h-3.5 w-3.5" />
            Add to Calendar
          </button>
        )}
        <Link
          to="/my-bookings"
          className="flex-1 sm:flex-none px-6 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors text-center"
        >
          My Bookings
        </Link>
        <Link
          to="/book"
          className="flex-1 sm:flex-none px-6 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors text-center"
        >
          Book Another
        </Link>
      </div>

      {!cancelled && (
        <p className="mt-8 text-xs text-muted-foreground tracking-wider text-center">
          Need to make a change? You can cancel up to 2 hours before your appointment from{" "}
          <Link to="/my-bookings" className="underline underline-offset-4 hover:text-foreground">
            My Bookings
          </Link>
          .
        </p>
      )}
    </div>
  )
}
