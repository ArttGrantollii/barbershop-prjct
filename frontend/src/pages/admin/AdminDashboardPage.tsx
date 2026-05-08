import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { parseISO } from "date-fns"
import { CalendarDays } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import {
  salonClockParts,
  salonDateLong,
  salonTime,
} from "@/lib/datetime"
import api from "@/lib/api"
import type { AdminDashboard } from "@/types"

function StatCard({ label, value, sub }: { label: string; value: string | number; sub: string }) {
  return (
    <div className="bg-background border border-border p-6 flex flex-col gap-3">
      <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground">{label}</p>
      <p className="font-display text-5xl uppercase leading-none">{value}</p>
      <p className="text-xs text-muted-foreground tracking-wider">{sub}</p>
    </div>
  )
}

export default function AdminDashboardPage() {
  const { user } = useAuth()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone
  const now = new Date()

  const greeting = useMemo(() => {
    // Greeting is based on the salon's local hour, not the admin's browser
    // hour — relevant if the admin manages the salon from another timezone.
    const hourStr = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hour: "numeric",
      hour12: false,
    }).format(now)
    const h = parseInt(hourStr, 10)
    if (h < 12) return "Morning"
    if (h < 17) return "Afternoon"
    return "Evening"
  }, [tz])

  const { data: dashboard, isLoading } = useQuery<AdminDashboard>({
    queryKey: ["admin-dashboard"],
    queryFn: () => api.get("/api/v1/admin/dashboard").then((r) => r.data),
    staleTime: 30_000,
  })

  const todayBookings = dashboard?.today_schedule ?? []

  return (
    <div className="flex flex-col gap-10">
      {/* header */}
      <div>
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">
          {salonDateLong(now, tz)}
        </p>
        <h1 className="font-display text-6xl uppercase leading-none">
          {greeting},<br />{user?.name?.split(" ")[0]}.
        </h1>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-px bg-border">
        <StatCard
          label="Today"
          value={isLoading ? "—" : dashboard?.today_bookings_count ?? 0}
          sub={`$${Number(dashboard?.today_revenue ?? 0).toFixed(2)} in revenue`}
        />
        <StatCard
          label="This Week"
          value={isLoading ? "—" : dashboard?.week_bookings_count ?? 0}
          sub="upcoming appointments"
        />
        <StatCard
          label="Confirmed"
          value={dashboard?.confirmed_total ?? "—"}
          sub="all-time bookings"
        />
        <StatCard
          label="Cancelled"
          value={dashboard?.cancelled_total ?? "—"}
          sub="all-time cancellations"
        />
      </div>

      {/* today's schedule */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <p className="text-xs tracking-widest uppercase text-muted-foreground">Today's Schedule</p>
          <p className="text-xs text-muted-foreground">
            {todayBookings.length} appointment{todayBookings.length !== 1 ? "s" : ""}
          </p>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-px bg-border">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-secondary animate-pulse" />
            ))}
          </div>
        ) : todayBookings.length === 0 ? (
          <div className="border border-border p-16 flex flex-col items-center text-center gap-4">
            <CalendarDays className="h-8 w-8 text-muted-foreground/30" />
            <div>
              <p className="text-sm font-medium uppercase tracking-widest mb-1">No appointments today</p>
              <p className="text-xs text-muted-foreground tracking-wider">Enjoy the day off.</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-0 border border-border">
            {todayBookings.map((booking, i) => {
              const start = parseISO(booking.start_time)
              const end   = parseISO(booking.end_time)
              const past  = end < now
              const { hourMin, ampm } = salonClockParts(start, tz)
              return (
                <div
                  key={booking.id}
                  className={`flex items-center gap-6 px-6 py-5 ${i < todayBookings.length - 1 ? "border-b border-border" : ""} ${past ? "opacity-40" : ""}`}
                >
                  <div className="shrink-0 w-14 text-right">
                    <p className="text-sm font-medium tabular-nums">{hourMin}</p>
                    <p className="text-[10px] tracking-widest uppercase text-muted-foreground">{ampm}</p>
                  </div>

                  <div className="w-px h-8 bg-border shrink-0" />

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium uppercase tracking-wide truncate">
                      {booking.user?.name ?? "Unknown"}
                    </p>
                    <p className="text-xs text-muted-foreground tracking-wider truncate">
                      {booking.service?.name ?? "—"}
                      {booking.service && ` · ${booking.service.duration_minutes} min`}
                      {booking.staff && ` · ${booking.staff.name}`}
                    </p>
                  </div>

                  <p className="text-xs text-muted-foreground shrink-0 hidden sm:block tracking-wider">
                    until {salonTime(end, tz)}
                  </p>

                  <div className="shrink-0 text-right">
                    <p className="text-sm font-semibold tracking-wide">
                      ${Number(booking.service?.price ?? 0).toFixed(2)}
                    </p>
                    {past && (
                      <p className="text-[10px] tracking-widest uppercase text-muted-foreground mt-0.5">Done</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
