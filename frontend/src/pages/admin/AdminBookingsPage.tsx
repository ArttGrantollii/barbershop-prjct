import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO, isPast } from "date-fns"
import { Calendar, Clock, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { BookingPage, BookingStatus } from "@/types"

const PAGE_SIZE = 20

const FILTERS = [
  { label: "All",       value: undefined           },
  { label: "Confirmed", value: "confirmed" as const },
  { label: "Cancelled", value: "cancelled" as const },
  { label: "Completed", value: "completed" as const },
]

function statusVariant(s: BookingStatus) {
  if (s === "confirmed") return "success"
  if (s === "cancelled") return "destructive"
  return "secondary"
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
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      })
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      toast({ title: "Booking cancelled" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/bookings/${id}/complete`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      toast({ title: "Marked as completed" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  return (
    <div>
      <h1 className="text-xl font-bold tracking-tight mb-6">Bookings</h1>

      {/* Status filter tabs */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => handleFilterChange(f.value)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm border transition-colors capitalize",
              statusFilter === f.value
                ? "bg-primary text-primary-foreground border-primary"
                : "border-input text-muted-foreground hover:text-foreground"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading bookings…</p>
      ) : bookings.length === 0 ? (
        <p className="text-sm text-muted-foreground">No bookings found.</p>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {bookings.map((booking) => {
              const start = parseISO(booking.start_time)
              const past  = isPast(start)
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
                        <p className="text-xs text-muted-foreground italic">
                          Reason: {booking.cancellation_reason}
                        </p>
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

          {/* Pagination bar */}
          <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
            <span>
              {from}–{to} of {total} booking{total !== 1 ? "s" : ""}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => p - 1)}
                disabled={page === 0}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-xs">
                Page {page + 1} of {pageCount}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= pageCount - 1}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
