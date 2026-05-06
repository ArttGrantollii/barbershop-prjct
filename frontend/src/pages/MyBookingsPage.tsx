import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO, isPast } from "date-fns"
import { Calendar, Clock, Scissors } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"
import type { Booking } from "@/types"

function statusVariant(status: Booking["status"]) {
  if (status === "confirmed") return "success"
  if (status === "cancelled") return "destructive"
  return "secondary"
}

export default function MyBookingsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

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
      toast({ title: "Booking cancelled" })
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not cancel. Please try again."
      toast({ variant: "destructive", title: "Error", description: msg })
    },
  })

  if (isLoading) {
    return (
      <div className="container py-10 max-w-2xl">
        <p className="text-muted-foreground text-sm">Loading your bookings…</p>
      </div>
    )
  }

  return (
    <div className="container py-10 max-w-2xl">
      <h1 className="text-2xl font-bold tracking-tight mb-2">My Bookings</h1>
      <p className="text-muted-foreground mb-8">Your upcoming and past appointments.</p>

      {!bookings?.length ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div className="h-12 w-12 rounded-full bg-secondary flex items-center justify-center">
            <Scissors className="h-6 w-6 text-muted-foreground" />
          </div>
          <div>
            <p className="font-medium">No bookings yet</p>
            <p className="text-sm text-muted-foreground mt-1">Book your first appointment to get started.</p>
          </div>
          <Button asChild>
            <a href="/book">Book Now</a>
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {bookings.map((booking) => {
            const startTime = parseISO(booking.start_time)
            const canCancel = booking.status === "confirmed" && !isPast(startTime)
            return (
              <Card key={booking.id}>
                <CardContent className="p-5 flex flex-col sm:flex-row sm:items-center gap-4">
                  <div className="flex-1 flex flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{booking.service?.name ?? "Appointment"}</p>
                      <Badge variant={statusVariant(booking.status)}>
                        {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {format(startTime, "EEEE, MMM d, yyyy")}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {format(startTime, "h:mm a")}
                      </span>
                    </div>
                    {booking.service && (
                      <p className="text-sm text-muted-foreground">
                        {booking.service.duration_minutes} min · ${Number(booking.service.price).toFixed(2)}
                      </p>
                    )}
                    {booking.cancellation_reason && (
                      <p className="text-xs text-muted-foreground italic">Reason: {booking.cancellation_reason}</p>
                    )}
                  </div>
                  {canCancel && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => cancelMutation.mutate(booking.id)}
                      disabled={cancelMutation.isPending}
                    >
                      Cancel
                    </Button>
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
