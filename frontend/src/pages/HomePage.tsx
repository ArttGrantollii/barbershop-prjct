import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Ban, CalendarDays, Clock, LayoutDashboard, Scissors, Settings, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/context/AuthContext"
import api from "@/lib/api"
import type { Service } from "@/types"

function useServices() {
  return useQuery<Service[]>({
    queryKey: ["services"],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/services")
      return data
    },
  })
}

// ── Admin home ────────────────────────────────────────────────────────────────

const adminQuickLinks = [
  { to: "/admin/dashboard",     label: "Dashboard",      desc: "Stats and today's schedule", icon: LayoutDashboard },
  { to: "/admin/bookings",      label: "Bookings",       desc: "Manage all appointments",    icon: CalendarDays },
  { to: "/admin/services",      label: "Services",       desc: "Add or update offerings",    icon: Settings },
  { to: "/admin/hours",         label: "Business Hours", desc: "Set your weekly schedule",   icon: Clock },
  { to: "/admin/blocked-dates", label: "Blocked Dates",  desc: "Close days off",             icon: Ban },
]

function AdminHomePage({ services }: { services: Service[] | undefined }) {
  const { user } = useAuth()

  return (
    <div className="flex flex-col">
      {/* admin hero */}
      <section className="border-b bg-secondary/20">
        <div className="container py-14 flex flex-col gap-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3">
            Admin View
          </p>
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome back, {user?.name?.split(" ")[0]}
          </h1>
          <p className="text-muted-foreground mt-1 max-w-sm">
            Manage your salon, bookings, and services from one place.
          </p>
          <div className="mt-6">
            <Button asChild>
              <Link to="/admin/dashboard">
                <LayoutDashboard className="h-4 w-4 mr-2" />
                Go to Dashboard
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* quick links */}
      <section className="container py-12">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-5">
          Quick Access
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {adminQuickLinks.map(({ to, label, desc, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="group flex items-start gap-4 p-4 rounded-xl border bg-card hover:bg-accent transition-colors"
            >
              <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                <Icon className="h-4.5 w-4.5 text-primary h-[18px] w-[18px]" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold leading-snug">{label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* services preview */}
      {services && services.filter((s) => s.is_active).length > 0 && (
        <section className="border-t bg-secondary/20 py-12">
          <div className="container">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold tracking-tight">Active Services</h2>
                <p className="text-sm text-muted-foreground mt-0.5">What your customers see when booking</p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/admin/services">Manage</Link>
              </Button>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {services.filter((s) => s.is_active).map((service) => (
                <Card key={service.id}>
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <Scissors className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{service.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {service.duration_minutes} min · ${Number(service.price).toFixed(2)}
                      </p>
                    </div>
                    <Badge variant="secondary" className="text-[10px] shrink-0">Active</Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* footer */}
      <footer className="border-t py-8 mt-auto">
        <div className="container flex flex-col md:flex-row justify-between gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <Scissors className="h-4 w-4" />
            Vendos Salon
          </div>
          <p className="text-xs">© {new Date().getFullYear()} Vendos Salon. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

// ── Customer home ─────────────────────────────────────────────────────────────

function CustomerHomePage({ services }: { services: Service[] | undefined }) {
  return (
    <div className="flex flex-col">
      {/* hero */}
      <section className="container py-24 md:py-36 flex flex-col items-center text-center gap-6">
        <div className="flex items-center gap-2 text-muted-foreground text-sm tracking-widest uppercase">
          <Scissors className="h-4 w-4" />
          <span>Premium Barbershop</span>
        </div>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-2xl leading-tight">
          Look Sharp.<br />Feel Confident.
        </h1>
        <p className="text-muted-foreground max-w-md text-lg">
          Expert cuts and grooming in a relaxed, modern environment. Book your appointment online in seconds.
        </p>
        <div className="flex gap-3">
          <Button size="lg" asChild>
            <Link to="/book">Book Now</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href="#services">Our Services</a>
          </Button>
        </div>
      </section>

      {/* services */}
      <section id="services" className="border-t bg-secondary/30 py-20">
        <div className="container">
          <h2 className="text-2xl font-bold tracking-tight mb-2">Services</h2>
          <p className="text-muted-foreground mb-10">Everything you need to look your best.</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {services?.filter((s) => s.is_active).map((service) => (
              <Card key={service.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-6 flex flex-col gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Scissors className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{service.name}</h3>
                    {service.description && (
                      <p className="text-sm text-muted-foreground mt-1">{service.description}</p>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-sm mt-auto pt-2 border-t">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      {service.duration_minutes} min
                    </span>
                    <span className="font-semibold">${Number(service.price).toFixed(2)}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="mt-10 flex justify-center">
            <Button asChild size="lg">
              <Link to="/book">Book an Appointment</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* why */}
      <section className="container py-20">
        <h2 className="text-2xl font-bold tracking-tight mb-10 text-center">Why Vendos Salon?</h2>
        <div className="grid sm:grid-cols-3 gap-8 text-center">
          {[
            { icon: <Star className="h-6 w-6" />, title: "Expert Barbers", desc: "Years of experience delivering precise, stylish cuts." },
            { icon: <Clock className="h-6 w-6" />, title: "Easy Booking", desc: "Book online 24/7 — no phone calls, no waiting." },
            { icon: <Scissors className="h-6 w-6" />, title: "Premium Service", desc: "From classic cuts to full grooming packages." },
          ].map((item) => (
            <div key={item.title} className="flex flex-col items-center gap-3">
              <div className="h-12 w-12 rounded-full bg-secondary flex items-center justify-center">
                {item.icon}
              </div>
              <h3 className="font-semibold">{item.title}</h3>
              <p className="text-sm text-muted-foreground">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* footer */}
      <footer className="border-t bg-secondary/30 py-10">
        <div className="container flex flex-col md:flex-row justify-between gap-6 text-sm text-muted-foreground">
          <div>
            <div className="flex items-center gap-2 font-semibold text-foreground mb-1">
              <Scissors className="h-4 w-4" />
              Vendos Salon
            </div>
            <p>Premium barbershop services</p>
          </div>
          <div>
            <p className="font-medium text-foreground mb-1">Hours</p>
            <p>Monday – Saturday: 9:00 AM – 6:00 PM</p>
            <p>Sunday: Closed</p>
          </div>
          <div>
            <p className="font-medium text-foreground mb-1">Quick Links</p>
            <div className="flex flex-col gap-1">
              <Link to="/book" className="hover:text-foreground transition-colors">Book Appointment</Link>
              <Link to="/login" className="hover:text-foreground transition-colors">Sign In</Link>
            </div>
          </div>
        </div>
        <div className="container mt-8 pt-6 border-t text-xs text-muted-foreground">
          © {new Date().getFullYear()} Vendos Salon. All rights reserved.
        </div>
      </footer>
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const { user } = useAuth()
  const { data: services } = useServices()

  if (user?.role === "admin") return <AdminHomePage services={services} />
  return <CustomerHomePage services={services} />
}
