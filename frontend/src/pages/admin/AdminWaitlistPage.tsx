import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CalendarPlus, Check, X } from "lucide-react"
import { parseISO } from "date-fns"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDateShort, salonDateTimeInputToUtcIso } from "@/lib/datetime"
import api from "@/lib/api"
import type { Service, StaffWithServices, WaitlistEntry } from "@/types"

type DraftById = Record<string, { date: string; time: string; staff_id: string }>

export default function AdminWaitlistPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone
  const [drafts, setDrafts] = useState<DraftById>({})
  const [form, setForm] = useState({
    customer_name: "",
    customer_email: "",
    customer_phone: "",
    service_id: "",
    staff_id: "",
    preferred_date: "",
    notes: "",
  })

  const { data: entries = [], isLoading } = useQuery<WaitlistEntry[]>({
    queryKey: ["admin-waitlist"],
    queryFn: async () => (await api.get("/api/v1/admin/waitlist")).data,
  })

  const { data: services = [] } = useQuery<Service[]>({
    queryKey: ["admin-services"],
    queryFn: async () => (await api.get("/api/v1/admin/services")).data,
  })

  const { data: staff = [] } = useQuery<StaffWithServices[]>({
    queryKey: ["admin-staff"],
    queryFn: async () => (await api.get("/api/v1/admin/staff")).data,
  })

  const createMutation = useMutation({
    mutationFn: () => api.post("/api/v1/admin/waitlist", {
      service_id: form.service_id,
      staff_id: form.staff_id || null,
      customer_name: form.customer_name,
      customer_email: form.customer_email || null,
      customer_phone: form.customer_phone || null,
      preferred_date: form.preferred_date || null,
      notes: form.notes || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-waitlist"] })
      toast({ title: "Waitlist entry added" })
      setForm({
        customer_name: "",
        customer_email: "",
        customer_phone: "",
        service_id: "",
        staff_id: "",
        preferred_date: "",
        notes: "",
      })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/api/v1/admin/waitlist/${id}`, { status: "cancelled" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-waitlist"] })
      toast({ title: "Waitlist entry cancelled" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const bookMutation = useMutation({
    mutationFn: ({ id, draft }: { id: string; draft: { date: string; time: string; staff_id: string } }) => {
      const start_time = salonDateTimeInputToUtcIso(`${draft.date}T${draft.time}`, tz)
      return api.post(`/api/v1/admin/waitlist/${id}/book`, {
        start_time,
        staff_id: draft.staff_id,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-waitlist"] })
      queryClient.invalidateQueries({ queryKey: ["admin-bookings"] })
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] })
      toast({ title: "Waitlist entry booked" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const canCreate = !!form.customer_name.trim() && !!form.service_id

  function updateDraft(entry: WaitlistEntry, patch: Partial<{ date: string; time: string; staff_id: string }>) {
    setDrafts((current) => ({
      ...current,
      [entry.id]: {
        date: current[entry.id]?.date ?? entry.preferred_date ?? "",
        time: current[entry.id]?.time ?? "",
        staff_id: current[entry.id]?.staff_id ?? entry.staff_id ?? "",
        ...patch,
      },
    }))
  }

  return (
    <div>
      <div className="mb-8">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
        <h1 className="font-display text-5xl uppercase">Waitlist</h1>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (canCreate) createMutation.mutate()
        }}
        className="border border-border mb-8"
      >
        <div className="grid md:grid-cols-3 gap-px bg-border">
          <input value={form.customer_name} onChange={(e) => setForm((f) => ({ ...f, customer_name: e.target.value }))} placeholder="Customer name" className="bg-background px-4 py-3 text-sm outline-none" />
          <input value={form.customer_email} onChange={(e) => setForm((f) => ({ ...f, customer_email: e.target.value }))} placeholder="Email" type="email" className="bg-background px-4 py-3 text-sm outline-none" />
          <input value={form.customer_phone} onChange={(e) => setForm((f) => ({ ...f, customer_phone: e.target.value }))} placeholder="Phone" className="bg-background px-4 py-3 text-sm outline-none" />
          <select value={form.service_id} onChange={(e) => setForm((f) => ({ ...f, service_id: e.target.value, staff_id: "" }))} className="bg-background px-4 py-3 text-sm outline-none">
            <option value="">Service</option>
            {services.filter((s) => s.is_active).map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
          </select>
          <select value={form.staff_id} onChange={(e) => setForm((f) => ({ ...f, staff_id: e.target.value }))} className="bg-background px-4 py-3 text-sm outline-none">
            <option value="">Any stylist</option>
            {staff.filter((person) => person.is_active && (!form.service_id || person.service_ids.includes(form.service_id))).map((person) => (
              <option key={person.id} value={person.id}>{person.name}</option>
            ))}
          </select>
          <input type="date" value={form.preferred_date} onChange={(e) => setForm((f) => ({ ...f, preferred_date: e.target.value }))} className="bg-background px-4 py-3 text-sm outline-none [color-scheme:dark]" />
          <input value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} placeholder="Notes" className="bg-background px-4 py-3 text-sm outline-none md:col-span-2" />
          <button disabled={!canCreate || createMutation.isPending} className="bg-foreground text-background px-4 py-3 text-xs tracking-widest uppercase disabled:opacity-40">
            Add
          </button>
        </div>
      </form>

      {isLoading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading waitlist...</div>
      ) : entries.length === 0 ? (
        <div className="border border-border p-12 text-center text-xs text-muted-foreground tracking-widest uppercase">No active waitlist entries.</div>
      ) : (
        <div className="border border-border">
          {entries.map((entry, index) => {
            const draft = drafts[entry.id] ?? {
              date: entry.preferred_date ?? "",
              time: "",
              staff_id: entry.staff_id ?? "",
            }
            const availableStaff = staff.filter((person) => person.is_active && person.service_ids.includes(entry.service_id))
            return (
              <div key={entry.id} className={index < entries.length - 1 ? "border-b border-border p-5" : "p-5"}>
                <div className="flex flex-col lg:flex-row gap-5 lg:items-center">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-3 mb-2">
                      <span className="text-sm font-medium uppercase tracking-wide">{entry.customer_name}</span>
                      {entry.customer_email && <a href={`mailto:${entry.customer_email}`} className="text-xs text-muted-foreground hover:text-foreground">{entry.customer_email}</a>}
                      {entry.customer_phone && <a href={`tel:${entry.customer_phone}`} className="text-xs text-muted-foreground hover:text-foreground tabular-nums">{entry.customer_phone}</a>}
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground tracking-wider">
                      <span className="text-foreground font-medium uppercase">{entry.service?.name ?? "Service"}</span>
                      <span>{entry.staff?.name ?? "Any stylist"}</span>
                      {entry.preferred_date && <span>{salonDateShort(parseISO(entry.preferred_date), business?.timezone)}</span>}
                    </div>
                    {entry.notes && <p className="text-xs text-muted-foreground italic mt-2">{entry.notes}</p>}
                  </div>

                  <div className="grid sm:grid-cols-[auto_auto_auto_auto_auto] gap-2">
                    <input type="date" value={draft.date} onChange={(e) => updateDraft(entry, { date: e.target.value })} className="bg-background border border-border px-3 py-2 text-xs outline-none [color-scheme:dark]" />
                    <input type="time" value={draft.time} onChange={(e) => updateDraft(entry, { time: e.target.value })} className="bg-background border border-border px-3 py-2 text-xs outline-none [color-scheme:dark]" />
                    <select value={draft.staff_id} onChange={(e) => updateDraft(entry, { staff_id: e.target.value })} className="bg-background border border-border px-3 py-2 text-xs outline-none">
                      <option value="">Stylist</option>
                      {availableStaff.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
                    </select>
                    <button
                      onClick={() => bookMutation.mutate({ id: entry.id, draft })}
                      disabled={!draft.date || !draft.time || !draft.staff_id || bookMutation.isPending}
                      className="inline-flex items-center justify-center gap-2 px-3 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary disabled:opacity-40"
                    >
                      <CalendarPlus className="h-3.5 w-3.5" />
                      Book
                    </button>
                    <button
                      onClick={() => cancelMutation.mutate(entry.id)}
                      disabled={cancelMutation.isPending}
                      className="inline-flex items-center justify-center gap-2 px-3 py-2 text-xs tracking-widest uppercase border border-border hover:bg-secondary disabled:opacity-40"
                    >
                      {cancelMutation.isPending ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
