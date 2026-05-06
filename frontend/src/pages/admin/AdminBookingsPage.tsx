import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO, isPast } from "date-fns"
import { Calendar, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking, BookingStatus } from "@/types"

const FILTERS = ["all", "confirmed", "cancelled", "completed"] as const
type Filter = (typeof FILTERS)[number]

function statusVariant(s: BookingStatus) {
  if (s === "confirmed") return "success"
  if (s === "cancelled") return "destructive"
  return "secondary"
}

export default function AdminBookingsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<Filter>("all")

  const { data: bookings = [], isLoading } = useQuery<Booking[]>({
    queryKey: ["admin-bookings"],
    queryFn: async () => (await api.get("/api/v1/admin/bookings?limit=200")).data,
  })

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

  const displayed = bookings.filter((b) => filter === "all" || b.status === filter)

  return (
    <div>
      <h1 className="text-xl font-bold tracking-tight mb-6">Bookings</h1>

      {/* filters */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm border transition-colors capitalize",
              filter === f ? "bg-primary text-primary-foreground border-primary" : "border-input text-muted-foreground hover:text-foreground"
            )}
          >
            {f}
            <span className="ml-1.5 text-xs opacity-70">
              {f === "all" ? bookings.length : bookings.filter((b) => b.status === f).length}
            </span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading bookings…</p>
      ) : displayed.length === 0 ? (
        <p className="text-sm text-muted-foreground">No bookings found.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {displayed.map((booking) => {
            const start = parseISO(booking.start_time)
            const past = isPast(start)
            return (
              <Card key={booking.id}>
                <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex-1 flex flex-col gap-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{booking.user?.name ?? "Unknown"}</span>
                      <span className="text-muted-foreground text-xs">{booking.user?.email}</span>
                      <Badge variant={statusVariant(booking.status)} className="text-xs">
                        {booking.status}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{booking.service?.name ?? "—"}</span>
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
                      <p className="text-xs text-muted-foreground italic">Reason: {booking.cancellation_reason}</p>
                    )}
                  </div>
                  {booking.status === "confirmed" && (
                    <div className="flex gap-2 shrink-0">
                      {!past && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => cancelMutation.mutate(booking.id)}
                          disabled={cancelMutation.isPending}
                        >
                          Cancel
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => completeMutation.mutate(booking.id)}
                        disabled={completeMutation.isPending}
                      >
                        Complete
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
