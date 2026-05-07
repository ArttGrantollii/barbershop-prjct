import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { addDays, format, isToday, isWithinInterval, parseISO, startOfDay } from "date-fns"
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  DollarSign,
  XCircle,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/context/AuthContext"
import api from "@/lib/api"
import type { BookingPage } from "@/types"

// ── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  title: string
  value: string | number
  sub: string
  icon: React.ElementType
}

function StatCard({ title, value, sub, icon: Icon }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4 px-5">
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
      </CardHeader>
      <CardContent className="px-5 pb-5 pt-0">
        <p className="text-2xl font-bold leading-none">{value}</p>
        <p className="text-xs text-muted-foreground mt-1.5">{sub}</p>
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const { user } = useAuth()
  const now = new Date()

  const greeting = useMemo(() => {
    const h = now.getHours()
    if (h < 12) return "Good morning"
    if (h < 17) return "Good afternoon"
    return "Good evening"
  }, [])

  // Recent confirmed bookings — sorted start_time DESC so today/future are first
  const { data: confirmedPage, isLoading: loadingConfirmed } = useQuery<BookingPage>({
    queryKey: ["dashboard", "confirmed"],
    queryFn: () =>
      api.get("/api/v1/admin/bookings", { params: { status: "confirmed", limit: 100 } }).then((r) => r.data),
    staleTime: 30_000,
  })

  // Only need the total count for cancelled
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
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">
          {greeting}, {user?.name?.split(" ")[0]}
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {format(now, "EEEE, MMMM d, yyyy")}
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Today"
          value={loadingConfirmed ? "—" : todayBookings.length}
          sub={`$${todayRevenue.toFixed(2)} in revenue`}
          icon={CalendarDays}
        />
        <StatCard
          title="This Week"
          value={loadingConfirmed ? "—" : thisWeekCount}
          sub="upcoming appointments"
          icon={Clock}
        />
        <StatCard
          title="Confirmed"
          value={confirmedPage?.total ?? "—"}
          sub="all-time bookings"
          icon={CheckCircle2}
        />
        <StatCard
          title="Cancelled"
          value={cancelledPage?.total ?? "—"}
          sub="all-time cancellations"
          icon={XCircle}
        />
      </div>

      {/* Today's schedule */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold">Today's Schedule</h2>
          <span className="text-xs text-muted-foreground">
            {todayBookings.length} appointment{todayBookings.length !== 1 ? "s" : ""}
          </span>
        </div>

        {loadingConfirmed ? (
          <div className="flex flex-col gap-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded-xl border bg-muted/30 animate-pulse" />
            ))}
          </div>
        ) : todayBookings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 rounded-xl border border-dashed text-center">
            <CalendarDays className="h-8 w-8 text-muted-foreground/50 mb-3" />
            <p className="text-sm font-medium">No appointments today</p>
            <p className="text-xs text-muted-foreground mt-1">Enjoy the day off!</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {todayBookings.map((booking, idx) => {
              const start = parseISO(booking.start_time)
              const end   = parseISO(booking.end_time)
              const isPast = end < now
              return (
                <div
                  key={booking.id}
                  className={`flex items-center gap-4 px-4 py-3.5 rounded-xl border transition-opacity ${isPast ? "opacity-50" : ""}`}
                >
                  {/* time + index */}
                  <div className="shrink-0 w-10 text-center">
                    <p className="text-xs font-medium text-muted-foreground">{format(start, "h:mm")}</p>
                    <p className="text-[10px] text-muted-foreground">{format(start, "a")}</p>
                  </div>

                  {/* accent line */}
                  <div className="h-10 w-0.5 rounded-full bg-primary/40 shrink-0" />

                  {/* details */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium leading-snug truncate">
                      {booking.user?.name ?? "Unknown"}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {booking.service?.name ?? "—"}
                      {booking.service && ` · ${booking.service.duration_minutes} min`}
                    </p>
                  </div>

                  {/* end time — hidden on mobile */}
                  <p className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                    until {format(end, "h:mm a")}
                  </p>

                  {/* price */}
                  <div className="shrink-0 text-right">
                    <p className="text-sm font-semibold">
                      ${Number(booking.service?.price ?? 0).toFixed(2)}
                    </p>
                    {isPast && (
                      <Badge variant="secondary" className="text-[10px] mt-0.5">Done</Badge>
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
