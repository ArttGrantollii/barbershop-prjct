import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO } from "date-fns"
import { Check, Clock } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Service, TimeSlot } from "@/types"

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

  const [step, setStep] = useState<Step>(1)
  const [selectedService, setSelectedService] = useState<Service | null>(null)
  const [selectedDate, setSelectedDate] = useState("")
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
  const [notes, setNotes] = useState("")

  const today = new Date().toISOString().split("T")[0]

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

  const bookMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/api/v1/bookings", {
        service_id: selectedService!.id,
        start_time: selectedSlot!.start_time,
        notes: notes || null,
      })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["slots"] })
      toast({ title: "Booking confirmed!" })
      navigate("/my-bookings")
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not complete booking. Please try again."
      toast({ variant: "destructive", title: "Booking failed", description: msg })
    },
  })

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
              <p className="text-xs tracking-widest uppercase text-muted-foreground mb-4">Available Times</p>
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
                        {format(parseISO(slot.start_time), "h:mm a")}
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
              disabled={!selectedSlot}
              onClick={() => setStep(3)}
              className="px-8 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-30"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* step 3 — confirm */}
      {step === 3 && selectedService && selectedSlot && (
        <div className="flex flex-col gap-8">
          <div>
            <p className="text-xs tracking-widest uppercase text-muted-foreground mb-6">Booking Summary</p>
            <div className="border border-border">
              {[
                { label: "Service",  value: selectedService.name },
                { label: "Date",     value: format(new Date(selectedDate + "T12:00:00"), "EEEE, MMMM d, yyyy") },
                { label: "Time",     value: format(parseISO(selectedSlot.start_time), "h:mm a") },
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
              onClick={() => setStep(2)}
              className="px-8 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
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
