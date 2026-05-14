import { useState } from "react"
import type { Dispatch, SetStateAction, FormEvent } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, Pencil, Plus, X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import type { Service } from "@/types"

type ServiceForm = { name: string; description: string; duration_minutes: string; price: string }
const emptyForm: ServiceForm = { name: "", description: "", duration_minutes: "", price: "" }

const fieldStyles = "bg-transparent border border-border text-foreground text-sm px-3 py-2 outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/40 w-full"

function ServiceFormFields({ form, onChange }: { form: ServiceForm; onChange: (k: keyof ServiceForm, v: string) => void }) {
  return (
    <div className="grid sm:grid-cols-2 gap-px bg-border mt-0">
      {[
        { key: "name",             label: "Name",             type: "text",   placeholder: "e.g. Haircut" },
        { key: "price",            label: "Price ($)",         type: "number", placeholder: "25.00" },
        { key: "duration_minutes", label: "Duration (min)",    type: "number", placeholder: "30" },
        { key: "description",      label: "Description (opt)", type: "text",   placeholder: "Short description" },
      ].map(({ key, label, type, placeholder }) => (
        <div key={key} className="bg-background flex flex-col gap-1 p-4">
          <label className="text-[10px] tracking-widest uppercase text-muted-foreground">{label}</label>
          <input
            type={type}
            value={form[key as keyof ServiceForm]}
            onChange={(e) => onChange(key as keyof ServiceForm, e.target.value)}
            placeholder={placeholder}
            required={key !== "description"}
            min={key === "duration_minutes" ? "1" : type === "number" ? "0" : undefined}
            step={key === "price" ? "0.01" : undefined}
            className={fieldStyles}
          />
        </div>
      ))}
    </div>
  )
}

export default function AdminServicesPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<ServiceForm>(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<ServiceForm>(emptyForm)

  const { data: services = [], isLoading } = useQuery<Service[]>({
    queryKey: ["admin-services"],
    queryFn: async () => (await api.get("/api/v1/admin/services")).data,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-services"] })

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post("/api/v1/admin/services", body),
    onSuccess: () => { invalidate(); setShowCreate(false); setCreateForm(emptyForm); toast({ title: "Service created" }) },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) => api.put(`/api/v1/admin/services/${id}`, body),
    onSuccess: () => { invalidate(); setEditId(null); toast({ title: "Service updated" }) },
    onError: (e: any) => toast({ variant: "destructive", title: e?.response?.data?.detail ?? "Error" }),
  })

  const setField = (setter: Dispatch<SetStateAction<ServiceForm>>) =>
    (k: keyof ServiceForm, v: string) => setter((f) => ({ ...f, [k]: v }))

  const startEdit = (s: Service) => {
    setEditId(s.id)
    setEditForm({ name: s.name, description: s.description ?? "", duration_minutes: String(s.duration_minutes), price: String(s.price) })
  }

  const submitCreate = (e: FormEvent) => {
    e.preventDefault()
    createMutation.mutate({ name: createForm.name, description: createForm.description || null, duration_minutes: parseInt(createForm.duration_minutes), price: parseFloat(createForm.price) })
  }

  const submitEdit = (e: FormEvent, id: string) => {
    e.preventDefault()
    updateMutation.mutate({ id, body: { name: editForm.name, description: editForm.description || null, duration_minutes: parseInt(editForm.duration_minutes), price: parseFloat(editForm.price) } })
  }

  const toggleActive = (s: Service) => updateMutation.mutate({ id: s.id, body: { is_active: !s.is_active } })

  return (
    <div>
      <div className="flex items-end justify-between mb-8">
        <div>
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-2">Admin</p>
          <h1 className="font-display text-5xl uppercase">Services</h1>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="flex items-center gap-2 text-xs tracking-widest uppercase border border-border px-5 py-3 hover:bg-secondary transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Service
        </button>
      </div>

      {/* create form */}
      {showCreate && (
        <div className="border border-border mb-6">
          <div className="px-6 py-4 border-b border-border">
            <p className="text-xs tracking-widest uppercase text-muted-foreground">New Service</p>
          </div>
          <form onSubmit={submitCreate}>
            <ServiceFormFields form={createForm} onChange={setField(setCreateForm)} />
            <div className="flex gap-0 border-t border-border">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="flex-1 px-5 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? "Saving…" : "Create Service"}
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

      {isLoading ? (
        <div className="border border-border p-6 text-xs text-muted-foreground tracking-widest uppercase">Loading…</div>
      ) : (
        <div className="flex flex-col gap-0 border border-border">
          {services.map((service, i) => (
            <div
              key={service.id}
              className={cn(
                i < services.length - 1 && "border-b border-border",
                !service.is_active && "opacity-50"
              )}
            >
              {editId === service.id ? (
                <form onSubmit={(e) => submitEdit(e, service.id)}>
                  <ServiceFormFields form={editForm} onChange={setField(setEditForm)} />
                  <div className="flex gap-0 border-t border-border">
                    <button
                      type="submit"
                      disabled={updateMutation.isPending}
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
                    <div className="flex items-center gap-3 mb-1">
                      <p className="text-sm font-medium uppercase tracking-widest">{service.name}</p>
                      <span className={cn(
                        "text-[10px] tracking-widest uppercase",
                        service.is_active ? "text-foreground/60" : "text-muted-foreground/40"
                      )}>
                        {service.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground tracking-wider">
                      {service.duration_minutes} min · ${Number(service.price).toFixed(2)}
                      {service.description && ` · ${service.description}`}
                    </p>
                  </div>
                  <div className="flex gap-0 shrink-0">
                    <button
                      onClick={() => startEdit(service)}
                      className="p-2.5 border border-border hover:bg-secondary transition-colors"
                      aria-label="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => toggleActive(service)}
                      disabled={updateMutation.isPending}
                      className="px-4 py-2.5 text-xs tracking-widest uppercase border border-border border-l-0 hover:bg-secondary transition-colors disabled:opacity-50"
                    >
                      {service.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
