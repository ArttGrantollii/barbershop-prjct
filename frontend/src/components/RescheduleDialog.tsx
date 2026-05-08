import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDayKey, salonTime } from "@/lib/datetime"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Booking, Staff, TimeSlot } from "@/types"

interface Props {
  booking: Booking
  open: boolean
  admin?: boolean
  onClose: () => void
}

export function RescheduleDialog({ booking, open, admin = false, onClose }: Props) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone

  // Local state — reset when the dialog opens for a different booking.
  const [date, setDate] = useState("")
  const [slot, setSlot] = useState<TimeSlot | null>(null)
  const [staffId, setStaffId] = useState(booking.staff_id)

  useEffect(() => {
    if (!open) return
    setDate("")
    setSlot(null)
    setStaffId(booking.staff_id)
  }, [open, booking.id])

  // ESC closes; lock body scroll while open. Two well-known a11y niceties
  // for modal dialogs.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  // Earliest selectable date is the salon's today, not the browser's.
  const today = salonDayKey(new Date(), tz)

  const { data: staffOptions = [], isLoading: staffLoading } = useQuery<Staff[]>({
    queryKey: ["staff", booking.service_id],
    queryFn: async () => (await api.get(`/api/v1/staff/by-service/${booking.service_id}`)).data,
    enabled: open,
  })

  const { data: slots, isLoading: slotsLoading } = useQuery<TimeSlot[]>({
    queryKey: ["slots", booking.service_id, date, staffId],
    queryFn: async () =>
      (await api.get("/api/v1/availability", {
        params: { service_id: booking.service_id, date, staff_id: staffId },
      })).data,
    enabled: open && !!date && !!staffId,
  })

  const rescheduleMutation = useMutation({
    mutationFn: async (newStart: string) => {
      const path = admin
        ? `/api/v1/admin/bookings/${booking.id}/reschedule`
        : `/api/v1/bookings/${booking.id}/reschedule`
      const { data } = await api.post(
        path,
        { start_time: newStart, staff_id: staffId },
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["slots"] })
      toast({ title: "Booking rescheduled" })
      onClose()
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not reschedule. Please try again."
      toast({ variant: "destructive", title: "Reschedule failed", description: msg })
    },
  })

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/10 backdrop-blur-sm px-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="reschedule-title"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg bg-background border border-border max-h-[90vh] overflow-y-auto"
      >
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-1">Reschedule</p>
            <h2 id="reschedule-title" className="font-display text-2xl uppercase">
              {booking.service?.name ?? "Appointment"}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-2 hover:bg-secondary transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* body */}
        <div className="p-6 flex flex-col gap-6">
          <div>
            <label className="text-[10px] tracking-widest uppercase text-muted-foreground block mb-2">
              Stylist
            </label>
            {staffLoading ? (
              <div className="border border-border p-4 text-xs text-muted-foreground tracking-widest uppercase">
                Loading stylists...
              </div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-px bg-border">
                {(staffOptions.length ? staffOptions : booking.staff ? [booking.staff] : []).map((staff) => {
                  const active = staffId === staff.id
                  return (
                    <button
                      key={staff.id}
                      onClick={() => {
                        setStaffId(staff.id)
                        setSlot(null)
                      }}
                      className={cn(
                        "bg-background text-left px-4 py-3 transition-colors hover:bg-secondary",
                        active && "bg-foreground text-background hover:bg-foreground",
                      )}
                    >
                      <p className="text-xs font-medium uppercase tracking-widest">{staff.name}</p>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="reschedule-date" className="text-[10px] tracking-widest uppercase text-muted-foreground block mb-2">
              New Date
            </label>
            <input
              id="reschedule-date"
              type="date"
              min={today}
              value={date}
              onChange={(e) => { setDate(e.target.value); setSlot(null) }}
              className="border border-border bg-transparent text-foreground text-sm px-4 py-3 outline-none focus:border-foreground transition-colors w-full max-w-xs [color-scheme:dark]"
            />
          </div>

          {date && (
            <div>
              <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-3">New Time</p>
              {slotsLoading ? (
                <div className="border border-border p-4 text-xs text-muted-foreground tracking-widest uppercase">
                  Loading slots…
                </div>
              ) : !slots?.length ? (
                <div className="border border-border p-4 text-xs text-muted-foreground tracking-widest uppercase">
                  No availability for this date.
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-px bg-border">
                  {slots.map((s) => {
                    // Don't let the user "reschedule" onto the booking's own
                    // current time — backend would reject, but this is clearer.
                    const isCurrent =
                      new Date(s.start_time).getTime() === new Date(booking.start_time).getTime()
                    const isAvailable = s.status === "available" && !isCurrent
                    const isSelected = slot?.start_time === s.start_time
                    return (
                      <button
                        key={s.start_time}
                        disabled={!isAvailable}
                        onClick={() => setSlot(s)}
                        title={isCurrent ? "This is the current booking time" : undefined}
                        className={cn(
                          "bg-background px-3 py-3 text-xs tracking-wider uppercase transition-colors",
                          isAvailable && !isSelected && "hover:bg-secondary cursor-pointer",
                          isSelected && "bg-foreground text-background",
                          !isAvailable && "text-muted-foreground/40 cursor-not-allowed",
                          isCurrent && "line-through",
                        )}
                      >
                        {salonTime(s.start_time, tz)}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* footer */}
        <div className="flex gap-0 border-t border-border">
          <button
            onClick={onClose}
            disabled={rescheduleMutation.isPending}
            className="flex-1 px-5 py-3 text-xs tracking-widest uppercase border-r border-border hover:bg-secondary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            disabled={!slot || rescheduleMutation.isPending}
            onClick={() => slot && rescheduleMutation.mutate(slot.start_time)}
            className="flex-1 px-5 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-30"
          >
            {rescheduleMutation.isPending ? "Saving…" : "Confirm Change"}
          </button>
        </div>
      </div>
    </div>
  )
}
