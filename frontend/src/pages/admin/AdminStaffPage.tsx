import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CalendarOff, Check, Pencil, Plus, Trash2, X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useBusinessInfo } from "@/hooks/useBusinessInfo"
import { salonDateTimeInputToUtcIso, salonDateTimeInputValue } from "@/lib/datetime"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Service, StaffBlockedTime, StaffWithServices, StaffWorkingHours } from "@/types"

type StaffForm = {
  name: string
  phone: string
  photo_url: string
  display_order: string
  service_ids: string[]
}

const emptyForm: StaffForm = {
  name: "",
  phone: "",
  photo_url: "",
  display_order: "0",
  service_ids: [],
}

const fieldStyles =
  "bg-transparent border border-border text-foreground text-sm px-3 py-2 outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/40 w-full"

const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

type HoursDraft = Record<number, { open_time: string; close_time: string; is_closed: boolean }>

function defaultHoursDraft(): HoursDraft {
  return dayLabels.reduce((acc, _label, day) => {
    acc[day] = { open_time: "09:00", close_time: "17:00", is_closed: false }
    return acc
  }, {} as HoursDraft)
}

function toTimeInput(value: string | undefined) {
  return value ? value.slice(0, 5) : ""
}

function toPayload(form: StaffForm) {
  return {
    name: form.name.trim(),
    phone: form.phone.trim() || null,
    photo_url: form.photo_url.trim() || null,
    display_order: Number.parseInt(form.display_order || "0", 10),
    service_ids: form.service_ids,
  }
}

function toStaffPatch(form: StaffForm) {
  const payload = toPayload(form)
  return {
    name: payload.name,
    phone: payload.phone,
    photo_url: payload.photo_url,
    display_order: payload.display_order,
  }
}

function toggleService(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]
}

function StaffFormFields({
  form,
  services,
  onChange,
}: {
  form: StaffForm
  services: Service[]
  onChange: (next: StaffForm) => void
}) {
  return (
    <>
      <div className="grid sm:grid-cols-2 gap-px bg-border">
        {[
          { key: "name", label: "Name", type: "text", placeholder: "e.g. Arta" },
          { key: "phone", label: "Phone", type: "tel", placeholder: "Optional" },
          { key: "photo_url", label: "Photo URL", type: "url", placeholder: "Optional" },
          { key: "display_order", label: "Display Order", type: "number", placeholder: "0" },
        ].map(({ key, label, type, placeholder }) => (
          <div key={key} className="bg-background flex flex-col gap-1 p-4">
            <label className="text-[10px] tracking-widest uppercase text-muted-foreground">{label}</label>
            <input
              type={type}
              value={form[key as keyof StaffForm] as string}
              onChange={(e) => onChange({ ...form, [key]: e.target.value })}
              placeholder={placeholder}
              required={key === "name"}
              className={fieldStyles}
            />
          </div>
        ))}
      </div>

      <div className="border-t border-border p-4">
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-3">
          Services Offered
        </p>
        {services.length === 0 ? (
          <p className="text-xs text-muted-foreground tracking-wider">Create services before assigning staff.</p>
        ) : (
          <div className="grid sm:grid-cols-2 gap-px bg-border">
            {services.map((service) => {
              const checked = form.service_ids.includes(service.id)
              return (
                <label
                  key={service.id}
                  className={cn(
                    "bg-background flex items-center gap-3 px-4 py-3 text-xs tracking-wider cursor-pointer hover:bg-secondary transition-colors",
                    !service.is_active && "opacity-50",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onChange({ ...form, service_ids: toggleService(form.service_ids, service.id) })}
                    className="h-4 w-4 accent-foreground"
                  />
                  <span className="uppercase">{service.name}</span>
                </label>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}

function StaffScheduleEditor({ staffId }: { staffId: string }) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data: business } = useBusinessInfo()
  const tz = business?.timezone
  const [hoursDraft, setHoursDraft] = useState<HoursDraft>(() => defaultHoursDraft())
  const [blockedDraft, setBlockedDraft] = useState({ start_time: "", end_time: "", reason: "" })

  const { data: workingHours = [] } = useQuery<StaffWorkingHours[]>({
    queryKey: ["admin-staff-working-hours", staffId],
    queryFn: async () => (await api.get(`/api/v1/admin/staff/${staffId}/working-hours`)).data,
    enabled: !!staffId,
  })

  const { data: blockedTimes = [] } = useQuery<StaffBlockedTime[]>({
    queryKey: ["admin-staff-blocked-times", staffId],
    queryFn: async () => (await api.get(`/api/v1/admin/staff/${staffId}/blocked-times`)).data,
    enabled: !!staffId,
  })

  useEffect(() => {
    const next = defaultHoursDraft()
    for (const hours of workingHours) {
      next[hours.day_of_week] = {
        open_time: toTimeInput(hours.open_time) || "09:00",
        close_time: toTimeInput(hours.close_time) || "17:00",
        is_closed: hours.is_closed,
      }
    }
    setHoursDraft(next)
  }, [workingHours])

  const invalidateSchedule = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-staff-working-hours", staffId] })
    queryClient.invalidateQueries({ queryKey: ["admin-staff-blocked-times", staffId] })
    queryClient.invalidateQueries({ queryKey: ["slots"] })
  }

  const saveHoursMutation = useMutation({
    mutationFn: ({ day, values }: { day: number; values: HoursDraft[number] }) =>
      api.put(`/api/v1/admin/staff/${staffId}/working-hours/${day}`, values),
    onSuccess: () => {
      invalidateSchedule()
      toast({ title: "Working hours saved" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const createBlockedMutation = useMutation({
    mutationFn: () => api.post(`/api/v1/admin/staff/${staffId}/blocked-times`, {
      start_time: salonDateTimeInputToUtcIso(blockedDraft.start_time, tz),
      end_time: salonDateTimeInputToUtcIso(blockedDraft.end_time, tz),
      reason: blockedDraft.reason.trim() || null,
    }),
    onSuccess: () => {
      invalidateSchedule()
      setBlockedDraft({ start_time: "", end_time: "", reason: "" })
      toast({ title: "Blocked time added" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const deleteBlockedMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/staff/${staffId}/blocked-times/${id}`),
    onSuccess: () => {
      invalidateSchedule()
      toast({ title: "Blocked time removed" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  return (
    <div className="border-t border-border">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <CalendarOff className="h-3.5 w-3.5" />
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground">Schedule Overrides</p>
      </div>

      <div className="grid gap-px bg-border">
        {dayLabels.map((label, day) => {
          const values = hoursDraft[day]
          return (
            <div key={label} className="bg-background grid md:grid-cols-[80px_1fr_1fr_110px] gap-3 items-center p-4">
              <p className="text-xs tracking-widest uppercase">{label}</p>
              <input
                type="time"
                value={values.open_time}
                disabled={values.is_closed}
                onChange={(e) => setHoursDraft({ ...hoursDraft, [day]: { ...values, open_time: e.target.value } })}
                className={fieldStyles}
              />
              <input
                type="time"
                value={values.close_time}
                disabled={values.is_closed}
                onChange={(e) => setHoursDraft({ ...hoursDraft, [day]: { ...values, close_time: e.target.value } })}
                className={fieldStyles}
              />
              <div className="flex gap-2 items-center justify-end">
                <label className="flex items-center gap-2 text-[10px] tracking-widest uppercase text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={values.is_closed}
                    onChange={(e) => setHoursDraft({ ...hoursDraft, [day]: { ...values, is_closed: e.target.checked } })}
                    className="h-4 w-4 accent-foreground"
                  />
                  Off
                </label>
                <button
                  type="button"
                  onClick={() => saveHoursMutation.mutate({ day, values })}
                  disabled={saveHoursMutation.isPending}
                  className="p-2 border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                  aria-label={`Save ${label} hours`}
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="border-t border-border p-4">
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-3">Blocked Time</p>
        <div className="grid md:grid-cols-[1fr_1fr_1fr_auto] gap-3">
          <input
            type="datetime-local"
            value={blockedDraft.start_time}
            onChange={(e) => setBlockedDraft({ ...blockedDraft, start_time: e.target.value })}
            required
            className={fieldStyles}
          />
          <input
            type="datetime-local"
            value={blockedDraft.end_time}
            onChange={(e) => setBlockedDraft({ ...blockedDraft, end_time: e.target.value })}
            required
            className={fieldStyles}
          />
          <input
            type="text"
            value={blockedDraft.reason}
            onChange={(e) => setBlockedDraft({ ...blockedDraft, reason: e.target.value })}
            placeholder="Reason"
            className={fieldStyles}
          />
          <button
            type="button"
            onClick={() => createBlockedMutation.mutate()}
            disabled={createBlockedMutation.isPending || !blockedDraft.start_time || !blockedDraft.end_time}
            className="px-5 py-2 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      {blockedTimes.length > 0 && (
        <div className="border-t border-border divide-y divide-border">
          {blockedTimes.map((blocked) => (
            <div key={blocked.id} className="flex items-center gap-3 px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs tracking-widest uppercase">
                  {salonDateTimeInputValue(blocked.start_time, tz).replace("T", " ")} - {salonDateTimeInputValue(blocked.end_time, tz).replace("T", " ")}
                </p>
                {blocked.reason && <p className="text-xs text-muted-foreground mt-1">{blocked.reason}</p>}
              </div>
              <button
                type="button"
                onClick={() => deleteBlockedMutation.mutate(blocked.id)}
                disabled={deleteBlockedMutation.isPending}
                className="p-2.5 border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                aria-label="Remove blocked time"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AdminStaffPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<StaffForm>(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<StaffForm>(emptyForm)

  const { data: staff = [], isLoading: staffLoading } = useQuery<StaffWithServices[]>({
    queryKey: ["admin-staff"],
    queryFn: async () => (await api.get("/api/v1/admin/staff")).data,
  })

  const { data: services = [], isLoading: servicesLoading } = useQuery<Service[]>({
    queryKey: ["admin-services"],
    queryFn: async () => (await api.get("/api/v1/admin/services")).data,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-staff"] })
    queryClient.invalidateQueries({ queryKey: ["staff"] })
    queryClient.invalidateQueries({ queryKey: ["slots"] })
  }

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post("/api/v1/admin/staff", body),
    onSuccess: () => {
      invalidate()
      setShowCreate(false)
      setCreateForm(emptyForm)
      toast({ title: "Staff member created" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) => api.patch(`/api/v1/admin/staff/${id}`, body),
    onSuccess: () => {
      invalidate()
      setEditId(null)
      toast({ title: "Staff member updated" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const saveMutation = useMutation({
    mutationFn: async ({ id, form }: { id: string; form: StaffForm }) => {
      await api.patch(`/api/v1/admin/staff/${id}`, toStaffPatch(form))
      await api.put(`/api/v1/admin/staff/${id}/services`, { service_ids: form.service_ids })
    },
    onSuccess: () => {
      invalidate()
      setEditId(null)
      toast({ title: "Staff member updated" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/staff/${id}`),
    onSuccess: () => {
      invalidate()
      toast({ title: "Staff member deleted" })
    },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  function startEdit(member: StaffWithServices) {
    setEditId(member.id)
    setEditForm({
      name: member.name,
      phone: member.phone ?? "",
      photo_url: member.photo_url ?? "",
      display_order: String(member.display_order),
      service_ids: member.service_ids,
    })
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault()
    createMutation.mutate(toPayload(createForm))
  }

  function submitEdit(e: FormEvent, id: string) {
    e.preventDefault()
    saveMutation.mutate({ id, form: editForm })
  }

  const loading = staffLoading || servicesLoading

  return (
    <div>
      <div className="flex items-end justify-between mb-8">
        <div>
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
          <h1 className="font-display text-5xl uppercase">Staff</h1>
        </div>
        <button
          onClick={() => setShowCreate((value) => !value)}
          className="flex items-center gap-2 text-xs tracking-widest uppercase border border-border px-5 py-3 hover:bg-secondary transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Staff
        </button>
      </div>

      {showCreate && (
        <div className="border border-border mb-6">
          <div className="px-6 py-4 border-b border-border">
            <p className="text-xs tracking-widest uppercase text-muted-foreground">New Staff Member</p>
          </div>
          <form onSubmit={submitCreate}>
            <StaffFormFields form={createForm} services={services} onChange={setCreateForm} />
            <div className="flex gap-0 border-t border-border">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="flex-1 px-5 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? "Saving..." : "Create Staff"}
              </button>
              <button
                type="button"
                onClick={() => { setShowCreate(false); setCreateForm(emptyForm) }}
                className="flex-1 px-5 py-3 text-xs tracking-widest uppercase border-l border-border hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading...</div>
      ) : staff.length === 0 ? (
        <div className="border border-border p-12 text-center text-xs text-muted-foreground tracking-widest uppercase">
          No staff configured.
        </div>
      ) : (
        <div className="flex flex-col gap-0 border border-border">
          {staff.map((member, index) => {
            const assigned = services.filter((service) => member.service_ids.includes(service.id))
            return (
              <div
                key={member.id}
                className={cn(index < staff.length - 1 && "border-b border-border", !member.is_active && "opacity-50")}
              >
                {editId === member.id ? (
                  <form onSubmit={(e) => submitEdit(e, member.id)}>
                    <StaffFormFields form={editForm} services={services} onChange={setEditForm} />
                    <StaffScheduleEditor staffId={member.id} />
                    <div className="flex gap-0 border-t border-border">
                      <button
                        type="submit"
                        disabled={saveMutation.isPending}
                        className="flex-1 flex items-center justify-center gap-2 px-5 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
                      >
                        <Check className="h-3 w-3" /> Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditId(null)}
                        className="flex-1 flex items-center justify-center gap-2 px-5 py-3 text-xs tracking-widest uppercase border-l border-border hover:bg-secondary transition-colors"
                      >
                        <X className="h-3 w-3" /> Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="flex items-center gap-4 px-6 py-5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1 flex-wrap">
                        <p className="text-sm font-medium uppercase tracking-widest">{member.name}</p>
                        <span className="text-[10px] tracking-widest uppercase text-muted-foreground">
                          {member.is_active ? "Active" : "Inactive"}
                        </span>
                        <span className="text-[10px] tracking-widest uppercase text-muted-foreground">
                          Order {member.display_order}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground tracking-wider">
                        {assigned.length > 0 ? assigned.map((service) => service.name).join(" / ") : "No services assigned"}
                      </p>
                      {member.phone && <p className="text-xs text-muted-foreground tracking-wider mt-1">{member.phone}</p>}
                    </div>
                    <div className="flex gap-0 shrink-0">
                      <button
                        onClick={() => startEdit(member)}
                        className="p-2.5 border border-border hover:bg-secondary transition-colors"
                        aria-label="Edit staff member"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => updateMutation.mutate({ id: member.id, body: { is_active: !member.is_active } })}
                        disabled={updateMutation.isPending}
                        className="px-4 py-2.5 text-xs tracking-widest uppercase border border-border border-l-0 hover:bg-secondary transition-colors disabled:opacity-50"
                      >
                        {member.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(member.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2.5 border border-border border-l-0 hover:bg-secondary transition-colors disabled:opacity-50"
                        aria-label="Delete staff member"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
