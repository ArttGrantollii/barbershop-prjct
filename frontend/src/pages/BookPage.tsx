import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { format, parseISO } from "date-fns"
import { Check, ChevronRight, Clock, Scissors } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Service, TimeSlot } from "@/types"

type Step = 1 | 2 | 3

function StepIndicator({ step, current }: { step: number; current: Step }) {
  const done = current > step
  const active = current === step
  return (
    <div className="flex items-center gap-2">
      <div className={cn(
        "h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors",
        done && "bg-primary text-primary-foreground border-primary",
        active && "border-primary text-primary",
        !done && !active && "border-muted-foreground/30 text-muted-foreground"
      )}>
        {done ? <Check className="h-3.5 w-3.5" /> : step}
      </div>
      <span className={cn("text-sm hidden sm:block", active ? "font-medium" : "text-muted-foreground")}>
        {step === 1 ? "Service" : step === 2 ? "Date & Time" : "Confirm"}
      </span>
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
      toast({ title: "Booking confirmed!", description: "Check your email for details." })
      navigate("/my-bookings")
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Could not complete booking. Please try again."
      toast({ variant: "destructive", title: "Booking failed", description: msg })
    },
  })

  return (
    <div className="container py-10 max-w-2xl">
      <h1 className="text-2xl font-bold tracking-tight mb-2">Book an Appointment</h1>
      <p className="text-muted-foreground mb-8">Choose your service, date, and time.</p>

      {/* steps */}
      <div className="flex items-center gap-3 mb-10">
        <StepIndicator step={1} current={step} />
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
        <StepIndicator step={2} current={step} />
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
        <StepIndicator step={3} current={step} />
      </div>

      {/* step 1 — service */}
      {step === 1 && (
        <div className="flex flex-col gap-4">
          {servicesLoading ? (
            <p className="text-muted-foreground text-sm">Loading services…</p>
          ) : (
            services?.filter((s) => s.is_active).map((service) => (
              <button
                key={service.id}
                onClick={() => { setSelectedService(service); setStep(2) }}
                className={cn(
                  "text-left w-full rounded-xl border p-5 hover:border-primary transition-colors",
                  selectedService?.id === service.id && "border-primary bg-primary/5"
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex gap-3 items-start">
                    <div className="h-9 w-9 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                      <Scissors className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-medium">{service.name}</p>
                      {service.description && (
                        <p className="text-sm text-muted-foreground mt-0.5">{service.description}</p>
                      )}
                      <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
                        <Clock className="h-3.5 w-3.5" />
                        {service.duration_minutes} min
                      </p>
                    </div>
                  </div>
                  <span className="font-semibold shrink-0">${Number(service.price).toFixed(2)}</span>
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* step 2 — date & time */}
      {step === 2 && (
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="date">Select a date</Label>
            <Input
              id="date"
              type="date"
              min={today}
              value={selectedDate}
              onChange={(e) => { setSelectedDate(e.target.value); setSelectedSlot(null) }}
              className="max-w-xs"
            />
          </div>

          {selectedDate && (
            <div>
              <p className="text-sm font-medium mb-3">Available times</p>
              {slotsLoading ? (
                <p className="text-muted-foreground text-sm">Loading slots…</p>
              ) : !slots?.length ? (
                <p className="text-muted-foreground text-sm">No availability for this date.</p>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
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
                          slot.status === "cooldown" ? "You recently cancelled this slot — cooldown active" :
                          undefined
                        }
                        className={cn(
                          "rounded-md border px-3 py-2 text-sm font-medium transition-colors text-foreground",
                          isAvailable && !isSelected && "bg-background hover:border-primary hover:bg-primary/5",
                          isSelected && "bg-primary text-primary-foreground border-primary",
                          slot.status === "held"     && "bg-muted/60 text-muted-foreground border-muted cursor-not-allowed line-through",
                          slot.status === "booked"   && "bg-muted text-muted-foreground border-muted cursor-not-allowed opacity-50",
                          slot.status === "cooldown" && "bg-destructive/10 text-destructive/50 border-destructive/20 cursor-not-allowed line-through",
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
            <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
            <Button disabled={!selectedSlot} onClick={() => setStep(3)}>Continue</Button>
          </div>
        </div>
      )}

      {/* step 3 — confirm */}
      {step === 3 && selectedService && selectedSlot && (
        <div className="flex flex-col gap-6">
          <Card>
            <CardContent className="p-6 flex flex-col gap-4">
              <h2 className="font-semibold text-lg">Booking Summary</h2>
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Service</span>
                  <span className="font-medium">{selectedService.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Date</span>
                  <span className="font-medium">{format(new Date(selectedDate), "EEEE, MMMM d, yyyy")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Time</span>
                  <span className="font-medium">{format(parseISO(selectedSlot.start_time), "h:mm a")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Duration</span>
                  <span className="font-medium">{selectedService.duration_minutes} minutes</span>
                </div>
                <div className="flex justify-between border-t pt-2 mt-1">
                  <span className="font-medium">Total</span>
                  <span className="font-bold">${Number(selectedService.price).toFixed(2)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="notes">Notes <span className="text-muted-foreground">(optional)</span></Label>
            <textarea
              id="notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any specific requests or notes for your barber…"
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
            />
          </div>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
            <Button onClick={() => bookMutation.mutate()} disabled={bookMutation.isPending}>
              {bookMutation.isPending ? "Booking…" : "Confirm Booking"}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
