import { useState } from "react"
import type { Dispatch, SetStateAction, FormEvent } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Pencil, X, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import api from "@/lib/api"
import type { Service } from "@/types"

type ServiceForm = { name: string; description: string; duration_minutes: string; price: string }
const emptyForm: ServiceForm = { name: "", description: "", duration_minutes: "", price: "" }

function ServiceFormFields({ form, onChange }: { form: ServiceForm; onChange: (k: keyof ServiceForm, v: string) => void }) {
  return (
    <div className="grid sm:grid-cols-2 gap-3 mt-3">
      <div className="flex flex-col gap-1.5">
        <Label>Name</Label>
        <Input value={form.name} onChange={(e) => onChange("name", e.target.value)} placeholder="e.g. Haircut" required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Price ($)</Label>
        <Input type="number" min="0" step="0.01" value={form.price} onChange={(e) => onChange("price", e.target.value)} placeholder="25.00" required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Duration (minutes)</Label>
        <Input type="number" min="1" value={form.duration_minutes} onChange={(e) => onChange("duration_minutes", e.target.value)} placeholder="30" required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Description <span className="text-muted-foreground">(optional)</span></Label>
        <Input value={form.description} onChange={(e) => onChange("description", e.target.value)} placeholder="Short description" />
      </div>
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
    setEditForm({
      name: s.name,
      description: s.description ?? "",
      duration_minutes: String(s.duration_minutes),
      price: String(s.price),
    })
  }

  const submitCreate = (e: FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      name: createForm.name,
      description: createForm.description || null,
      duration_minutes: parseInt(createForm.duration_minutes),
      price: parseFloat(createForm.price),
    })
  }

  const submitEdit = (e: FormEvent, id: string) => {
    e.preventDefault()
    updateMutation.mutate({
      id,
      body: {
        name: editForm.name,
        description: editForm.description || null,
        duration_minutes: parseInt(editForm.duration_minutes),
        price: parseFloat(editForm.price),
      },
    })
  }

  const toggleActive = (s: Service) =>
    updateMutation.mutate({ id: s.id, body: { is_active: !s.is_active } })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold tracking-tight">Services</h1>
        <Button size="sm" onClick={() => setShowCreate((v) => !v)}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Service
        </Button>
      </div>

      {/* create form */}
      {showCreate && (
        <Card className="mb-5">
          <CardContent className="p-5">
            <p className="font-medium text-sm">New Service</p>
            <form onSubmit={submitCreate}>
              <ServiceFormFields form={createForm} onChange={setField(setCreateForm)} />
              <div className="flex gap-2 mt-4">
                <Button type="submit" size="sm" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Saving…" : "Create"}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => { setShowCreate(false); setCreateForm(emptyForm) }}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {services.map((service) => (
            <Card key={service.id} className={!service.is_active ? "opacity-60" : ""}>
              <CardContent className="p-4">
                {editId === service.id ? (
                  <form onSubmit={(e) => submitEdit(e, service.id)}>
                    <ServiceFormFields form={editForm} onChange={setField(setEditForm)} />
                    <div className="flex gap-2 mt-4">
                      <Button type="submit" size="sm" disabled={updateMutation.isPending}>
                        <Check className="h-3.5 w-3.5 mr-1" />
                        Save
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => setEditId(null)}>
                        <X className="h-3.5 w-3.5 mr-1" />
                        Cancel
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{service.name}</span>
                        <Badge variant={service.is_active ? "success" : "secondary"} className="text-xs">
                          {service.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {service.duration_minutes} min · ${Number(service.price).toFixed(2)}
                        {service.description && ` · ${service.description}`}
                      </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <Button size="sm" variant="outline" onClick={() => startEdit(service)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => toggleActive(service)} disabled={updateMutation.isPending}>
                        {service.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
