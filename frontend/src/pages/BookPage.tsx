import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, Clock, Timer } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useSlotWebSocket } from "@/hooks/useSlotWebSocket"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDateLong, salonDayKey, salonTime, salonTzAbbr } from "@/lib/datetime"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Service, TimeSlot } from "@/types"

interface HoldResponse {
  start_time: string
  end_time: string
  expires_in_seconds: number
}

// Local snapshot of the slot the user has reserved on the server. The ref
// also acts as the source of truth for the unmount cleanup, so it can read
// the latest hold without going through the React state closure.
interface HeldSlot {
  serviceId: string
  startTime: string
}

type Step = 1 | 2 | 3

function StepBar({ step }: { step: Step }) {
  const steps = ["Service", "Date & Time", "Confirm"]
  return (
    <div className="flex items-center gap-0 border border-border mb-12">
      {steps.map((label, i) => {
        const n = (i + 1) as Step
        const done = step > n
        const active = step === n
        return (
          <div
            key={label}
            className={cn(
              "flex-1 flex items-center gap-3 px-5 py-4 text-xs tracking-widest uppercase transition-colors",
              i < steps.length - 1 && "border-r border-border",
              active && "bg-foreground text-background",
              done && "text-muted-foreground",
              !active && !done && "text-muted-foreground/40"
            )}
          >
            <span className={cn(
              "h-5 w-5 flex items-center justify-center border text-[10px] shrink-0",
              active && "border-background",
              done && "border-muted-foreground",
              !active && !done && "border-muted-foreground/30"
            )}>
              {done ? <Check className="h-3 w-3" /> : n}
            </span>
            <span className="hidden sm:block">{label}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function BookPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Component layout follows a strict order so future edits don't reintroduce
  // temporal-dead-zone bugs:
  //   1. local state
  //   2. external hooks (no dependencies on local data)
  //   3. derived constants
  //   4. data queries
  //   5. mutations
  //   6. effects (may reference everything above)

  // 1. state
  const [step, setStep] = useState<Step>(1)
  const [selectedService, setSelectedService] = useState<Service | null>(null)
  const [selectedDate, setSelectedDate] = useState("")
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
  const [notes, setNotes] = useState("")
  const [holdExpiresAt, setHoldExpiresAt] = useState<number | null>(null)
  const [nowTick, setNowTick] = useState(() => Date.now())
  // Ref so the unmount cleanup always sees the latest hold without a
  // re-render cycle, and so the WS effect below can identify "this update
  // is reflecting our own action" without a stale closure.
  const heldSlotRef = useRef<HeldSlot | null>(null)

  // 2. external hooks
  const { data: business } = useBusinessInfo()
  const { connected: wsConnected } = useSlotWebSocket(selectedService?.id, selectedDate)

  // 3. derived constants. `today` is the salon's local date — using browser-local
  // would let a user in a far-east timezone briefly see "tomorrow's" date as the
  // earliest selectable when it's already that day at the salon.
  const tz = business?.timezone
  const tzAbbr = salonTzAbbr(tz)
  const today = salonDayKey(new Date(), tz)

  // 4. data queries
  const { data: services, isLoading: servicesLoading } = useQuery<Service[]>({
    queryKey: ["services"],
    queryFn: async () => (await api.get("/api/v1/services")).data,
  })

  const { data: slots, isLoading: slotsLoading } = useQuery<TimeSlot[]>({
    queryKey: ["slots", selectedService?.id, selectedDate],
    queryFn: async () =>
      (await api.get("/api/v1/availability", { params: { service_id: selectedService!.id, date: selectedDate } })).data,
    enabled: !!selectedService && !!selectedDate,
  })

  // 5. mutations
  const holdMutation = useMutation({
    mutationFn: async (input: { service_id: string; start_time: string }) => {
      const { data } = await api.post<HoldResponse>("/api/v1/availability/hold", input)
      return { input, data }
    },
    onSuccess: ({ input, data }) => {
      heldSlotRef.current = { serviceId: input.service_id, startTime: input.start_time }
      setHoldExpiresAt(Date.now() + data.expires_in_seconds * 1000)
      setStep(3)
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not reserve this slot. It may have just been taken."
      toast({ variant: "destructive", title: "Slot unavailable", description: msg })
      setSelectedSlot(null)
      // Refetch slots so the grid reflects whatever truth caused the 409.
      queryClient.invalidateQueries({ queryKey: ["slots"] })
    },
  })

  const bookMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/api/v1/bookings", {
        service_id: selectedService!.id,
        start_time: selectedSlot!.start_time,
        notes: notes || null,
      })
      return data
    },
    onSuccess: (booking) => {
      // The backend deleted the hold key on successful create; nothing to release.
      heldSlotRef.current = null
      setHoldExpiresAt(null)
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["slots"] })
      // Hand the response to the confirmation page via router state so it
      // renders instantly without a refetch. The page falls back to GET
      // /bookings/:id on a hard refresh.
      navigate(`/bookings/${booking.id}/confirmation`, { state: { booking } })
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not complete booking. Please try again."
      toast({ variant: "destructive", title: "Booking failed", description: msg })
    },
  })

  // Best-effort hold release. Used by back-button, unmount cleanup, and
  // hold-expiry. Never throws — the backend TTL guarantees eventual cleanup
  // even if this fails, so we don't want a network blip to surface as a
  // user-visible error during navigation.
  async function releaseHeldSlot(): Promise<void> {
    const held = heldSlotRef.current
    if (!held) return
    heldSlotRef.current = null
    setHoldExpiresAt(null)
    try {
      await api.delete("/api/v1/availability/hold", {
        data: { service_id: held.serviceId, start_time: held.startTime },
      })
    } catch {
      // intentional no-op — backend TTL handles it
    }
  }

  // 6. effects.

  // Live countdown for the hold timer on step 3. Tick every second so the
  // displayed remaining time stays accurate. Only runs while a hold is active.
  useEffect(() => {
    if (!holdExpiresAt) return
    const id = setInterval(() => setNowTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [holdExpiresAt])

  // Hold-expiry watchdog: when the timer hits zero, release locally, kick the
  // user back to step 2, and tell them why. Setting an exact-duration timeout
  // is more efficient than checking expiry on every tick.
  useEffect(() => {
    if (!holdExpiresAt) return
    const ms = holdExpiresAt - Date.now()
    const expire = () => {
      heldSlotRef.current = null
      setHoldExpiresAt(null)
      setSelectedSlot(null)
      setStep(2)
      toast({
        variant: "destructive",
        title: "Hold expired",
        description: "Your slot reservation expired. Please pick another time.",
      })
      queryClient.invalidateQueries({ queryKey: ["slots"] })
    }
    if (ms <= 0) {
      expire()
      return
    }
    const id = setTimeout(expire, ms)
    return () => clearTimeout(id)
  }, [holdExpiresAt, toast, queryClient])

  // Best-effort release on component unmount (navigation away). Reads from
  // the ref so the cleanup sees the latest hold even if it changed since
  // mount. Booking-success path nulls the ref first so we don't double-release.
  useEffect(() => {
    return () => {
      const held = heldSlotRef.current
      if (!held) return
      heldSlotRef.current = null
      api
        .delete("/api/v1/availability/hold", {
          data: { service_id: held.serviceId, start_time: held.startTime },
        })
        .catch(() => {})
    }
  }, [])

  // If the user's selected slot got taken by *someone else* via the WS update,
  // deselect it. Skip when this slot is the one WE'RE holding/booking — the
  // backend broadcasts to everyone in the room including ourselves, and that
  // self-echo would otherwise misfire as "someone else took your slot".
  useEffect(() => {
    if (!selectedSlot || !slots) return
    const heldStart = heldSlotRef.current?.startTime
    if (
      heldStart &&
      new Date(heldStart).getTime() === new Date(selectedSlot.start_time).getTime()
    ) {
      return
    }
    const live = slots.find((s) => s.start_time === selectedSlot.start_time)
    if (live && live.status !== "available") {
      setSelectedSlot(null)
      if (step === 3) setStep(2)
      toast({
        variant: "destructive",
        title: "Slot taken",
        description: "That time was just booked by someone else. Please pick another.",
      })
    }
  }, [slots, selectedSlot, step, toast])

  const remainingSec = holdExpiresAt
    ? Math.max(0, Math.floor((holdExpiresAt - nowTick) / 1000))
    : 0
  const remainingMmSs = `${Math.floor(remainingSec / 60)}:${String(remainingSec % 60).padStart(2, "0")}`

  return (
    <div className="container py-16 max-w-3xl">
      <div className="mb-10">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">Appointment</p>
        <h1 className="font-display text-6xl uppercase">Book Now</h1>
      </div>

      <StepBar step={step} />

      {/* step 1 — service */}
      {step === 1 && (
        <div>
          <p className="text-xs tracking-widest uppercase text-muted-foreground mb-6">Choose a Service</p>
          {servicesLoading ? (
            <div className="border border-border p-8 text-xs text-muted-foreground tracking-widest uppercase">Loading services…</div>
          ) : (
            <div className="flex flex-col gap-0 border border-border">
              {services?.filter((s) => s.is_active).map((service, i, arr) => (
                <button
                  key={service.id}
                  onClick={() => { setSelectedService(service); setStep(2) }}
                  className={cn(
                    "group text-left w-full p-6 flex items-center justify-between gap-6 hover:bg-secondary transition-colors",
                    i < arr.length - 1 && "border-b border-border",
                    selectedService?.id === service.id && "bg-secondary"
                  )}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium uppercase tracking-widest mb-1">{service.name}</p>
                    {service.description && (
                      <p className="text-xs text-muted-foreground leading-relaxed">{service.description}</p>
                    )}
                    <p className="flex items-center gap-1.5 text-xs text-muted-foreground mt-2">
                      <Clock className="h-3 w-3" />
                      {service.duration_minutes} min
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-lg font-semibold tracking-wide">${Number(service.price).toFixed(2)}</p>
                    <p className="text-[10px] tracking-widest uppercase text-muted-foreground group-hover:text-foreground transition-colors mt-1">Select →</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* step 2 — date & time */}
      {step === 2 && (
        <div className="flex flex-col gap-8">
          <div>
            <p className="text-xs tracking-widest uppercase text-muted-foreground mb-4">Select a Date</p>
            <input
              type="date"
              min={today}
              value={selectedDate}
              onChange={(e) => { setSelectedDate(e.target.value); setSelectedSlot(null) }}
              className="border border-border bg-transparent text-foreground text-sm px-4 py-3 outline-none focus:border-foreground transition-colors w-full max-w-xs [color-scheme:dark]"
            />
          </div>

          {selectedDate && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <p className="text-xs tracking-widest uppercase text-muted-foreground">Available Times</p>
                {wsConnected && (
                  <span className="flex items-center gap-1.5 text-[10px] tracking-widest uppercase text-muted-foreground">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-foreground opacity-50" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-foreground" />
                    </span>
                    Live
                  </span>
                )}
              </div>
              {slotsLoading ? (
                <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading slots…</div>
              ) : !slots?.length ? (
                <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">No availability for this date.</div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-px bg-border">
                  {slots.map((slot) => {
                    const isAvailable = slot.status === "available"
                    const isSelected = selectedSlot?.start_time === slot.start_time
                    return (
                      <button
                        key={slot.start_time}
                        disabled={!isAvailable}
                        onClick={() => setSelectedSlot(slot)}
                        title={
                          slot.status === "held"     ? "Currently held by someone" :
                          slot.status === "booked"   ? "Already booked" :
                          slot.status === "cooldown" ? "Cooldown active — recently cancelled" :
                          undefined
                        }
                        className={cn(
                          "bg-background px-3 py-4 text-xs tracking-wider uppercase transition-colors",
                          isAvailable && !isSelected && "hover:bg-secondary text-foreground cursor-pointer",
                          isSelected && "bg-foreground text-background",
                          slot.status === "held"     && "text-muted-foreground/40 cursor-not-allowed line-through",
                          slot.status === "booked"   && "text-muted-foreground/30 cursor-not-allowed",
                          slot.status === "cooldown" && "text-destructive/40 cursor-not-allowed line-through",
                        )}
                      >
                        {salonTime(slot.start_time, tz)}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => setStep(1)}
              className="px-8 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
            >
              Back
            </button>
            <button
              disabled={!selectedSlot || holdMutation.isPending}
              onClick={() => {
                if (!selectedService || !selectedSlot) return
                holdMutation.mutate({
                  service_id: selectedService.id,
                  start_time: selectedSlot.start_time,
                })
              }}
              className="px-8 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-30"
            >
              {holdMutation.isPending ? "Reserving…" : "Continue"}
            </button>
          </div>
        </div>
      )}

      {/* step 3 — confirm */}
      {step === 3 && selectedService && selectedSlot && (
        <div className="flex flex-col gap-8">
          <div className="flex items-center justify-between gap-4 border border-border bg-secondary px-5 py-3">
            <div className="flex items-center gap-2.5 text-xs tracking-widest uppercase text-muted-foreground">
              <Timer className="h-3.5 w-3.5" />
              Slot reserved for you
            </div>
            <span className="text-sm font-medium tabular-nums">{remainingMmSs}</span>
          </div>

          <div>
            <p className="text-xs tracking-widest uppercase text-muted-foreground mb-6">Booking Summary</p>
            <div className="border border-border">
              {[
                { label: "Service",  value: selectedService.name },
                { label: "Date",     value: salonDateLong(selectedSlot.start_time, tz) },
                { label: "Time",     value: `${salonTime(selectedSlot.start_time, tz)}${tzAbbr ? ` ${tzAbbr}` : ""}` },
                { label: "Duration", value: `${selectedService.duration_minutes} minutes` },
              ].map(({ label, value }, i, arr) => (
                <div
                  key={label}
                  className={cn(
                    "flex items-center justify-between px-6 py-4",
                    i < arr.length - 1 && "border-b border-border"
                  )}
                >
                  <span className="text-xs tracking-widest uppercase text-muted-foreground">{label}</span>
                  <span className="text-sm font-medium">{value}</span>
                </div>
              ))}
              <div className="flex items-center justify-between px-6 py-5 border-t border-border bg-secondary">
                <span className="text-xs tracking-widest uppercase">Total</span>
                <span className="text-xl font-semibold tracking-wide">${Number(selectedService.price).toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="notes" className="text-xs tracking-widest uppercase text-muted-foreground block mb-4">
              Notes <span className="text-muted-foreground/50">(optional)</span>
            </label>
            <textarea
              id="notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any specific requests for your barber…"
              className="w-full border border-border bg-transparent text-sm text-foreground px-4 py-3 outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/40 resize-none"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => {
                releaseHeldSlot()
                setStep(2)
              }}
              disabled={bookMutation.isPending}
              className="px-8 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors disabled:opacity-50"
            >
              Back
            </button>
            <button
              onClick={() => bookMutation.mutate()}
              disabled={bookMutation.isPending}
              className="px-8 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
            >
              {bookMutation.isPending ? "Booking…" : "Confirm Booking"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
