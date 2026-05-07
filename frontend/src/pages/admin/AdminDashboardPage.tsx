import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { addDays, format, isToday, isWithinInterval, parseISO, startOfDay } from "date-fns"
import { CalendarDays } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import api from "@/lib/api"
import type { BookingPage } from "@/types"

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
  const now = new Date()

  const greeting = useMemo(() => {
    const h = now.getHours()
    if (h < 12) return "Morning"
    if (h < 17) return "Afternoon"
    return "Evening"
  }, [])

  const { data: confirmedPage, isLoading: loadingConfirmed } = useQuery<BookingPage>({
    queryKey: ["dashboard", "confirmed"],
    queryFn: () =>
      api.get("/api/v1/admin/bookings", { params: { status: "confirmed", limit: 100 } }).then((r) => r.data),
    staleTime: 30_000,
  })

  const { data: cancelledPage } = useQuery<BookingPage>({
    queryKey: ["dashboard", "cancelled"],
    queryFn: () =>
      api.get("/api/v1/admin/bookings", { params: { status: "cancelled", limit: 1 } }).then((r) => r.data),
    staleTime: 30_000,
  })

  const weekEnd = addDays(startOfDay(now), 7)

  const todayBookings = useMemo(() => {
    if (!confirmedPage) return []
    return confirmedPage.items
      .filter((b) => isToday(parseISO(b.start_time)))
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
  }, [confirmedPage])

  const thisWeekCount = useMemo(() => {
    if (!confirmedPage) return 0
    return confirmedPage.items.filter((b) =>
      isWithinInterval(parseISO(b.start_time), { start: now, end: weekEnd })
    ).length
  }, [confirmedPage])

  const todayRevenue = useMemo(
    () => todayBookings.reduce((sum, b) => sum + Number(b.service?.price ?? 0), 0),
    [todayBookings]
  )

  return (
    <div className="flex flex-col gap-10">
      {/* header */}
      <div>
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">
          {format(now, "EEEE, MMMM d, yyyy")}
        </p>
        <h1 className="font-display text-6xl uppercase leading-none">
          {greeting},<br />{user?.name?.split(" ")[0]}.
        </h1>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-px bg-border">
        <StatCard
          label="Today"
          value={loadingConfirmed ? "—" : todayBookings.length}
          sub={`$${todayRevenue.toFixed(2)} in revenue`}
        />
        <StatCard
          label="This Week"
          value={loadingConfirmed ? "—" : thisWeekCount}
          sub="upcoming appointments"
        />
        <StatCard
          label="Confirmed"
          value={confirmedPage?.total ?? "—"}
          sub="all-time bookings"
        />
        <StatCard
          label="Cancelled"
          value={cancelledPage?.total ?? "—"}
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

        {loadingConfirmed ? (
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
              return (
                <div
                  key={booking.id}
                  className={`flex items-center gap-6 px-6 py-5 ${i < todayBookings.length - 1 ? "border-b border-border" : ""} ${past ? "opacity-40" : ""}`}
                >
                  <div className="shrink-0 w-14 text-right">
                    <p className="text-sm font-medium tabular-nums">{format(start, "h:mm")}</p>
                    <p className="text-[10px] tracking-widest uppercase text-muted-foreground">{format(start, "a")}</p>
                  </div>

                  <div className="w-px h-8 bg-border shrink-0" />

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium uppercase tracking-wide truncate">
                      {booking.user?.name ?? "Unknown"}
                    </p>
                    <p className="text-xs text-muted-foreground tracking-wider truncate">
                      {booking.service?.name ?? "—"}
                      {booking.service && ` · ${booking.service.duration_minutes} min`}
                    </p>
                  </div>

                  <p className="text-xs text-muted-foreground shrink-0 hidden sm:block tracking-wider">
                    until {format(end, "h:mm a")}
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
