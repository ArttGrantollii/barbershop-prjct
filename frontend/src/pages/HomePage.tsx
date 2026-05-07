import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Ban, CalendarDays, Clock, LayoutDashboard, Settings } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { Logo } from "@/components/Logo"
import api from "@/lib/api"
import type { Service } from "@/types"

function useServices() {
  return useQuery<Service[]>({
    queryKey: ["services"],
    queryFn: async () => (await api.get("/api/v1/services")).data,
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
      <section className="border-b border-border">
        <div className="container py-16 flex flex-col gap-2">
          <p className="text-xs tracking-widest uppercase text-muted-foreground mb-4">Admin View</p>
          <h1 className="font-display text-6xl md:text-8xl uppercase tracking-wide">
            Welcome back,<br />{user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-sm text-muted-foreground mt-4 max-w-sm">
            Manage your salon, bookings, and services from one place.
          </p>
          <div className="mt-8">
            <Link
              to="/admin/dashboard"
              className="inline-flex items-center gap-3 bg-foreground text-background text-xs tracking-widest uppercase px-8 py-4 hover:bg-foreground/90 transition-colors"
            >
              <LayoutDashboard className="h-3.5 w-3.5" />
              Go to Dashboard
            </Link>
          </div>
        </div>
      </section>

      <section className="container py-16">
        <p className="text-xs tracking-widest uppercase text-muted-foreground mb-8">Quick Access</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
          {adminQuickLinks.map(({ to, label, desc, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="group flex items-start gap-5 p-8 bg-background hover:bg-secondary transition-colors"
            >
              <Icon className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0 group-hover:text-foreground transition-colors" />
              <div className="min-w-0">
                <p className="text-sm font-medium uppercase tracking-wider">{label}</p>
                <p className="text-xs text-muted-foreground mt-1">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {services && services.filter((s) => s.is_active).length > 0 && (
        <section className="border-t border-border py-16">
          <div className="container">
            <div className="flex items-end justify-between mb-8">
              <div>
                <p className="text-xs tracking-widest uppercase text-muted-foreground mb-2">On the Menu</p>
                <h2 className="font-display text-4xl uppercase tracking-wide">Active Services</h2>
              </div>
              <Link to="/admin/services" className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors">
                Manage →
              </Link>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
              {services.filter((s) => s.is_active).map((service) => (
                <div key={service.id} className="bg-background p-6 flex items-center justify-between gap-4">
                  <p className="text-sm font-medium uppercase tracking-wide truncate">{service.name}</p>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-semibold">${Number(service.price).toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground">{service.duration_minutes} min</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <footer className="border-t border-border py-8 mt-auto">
        <div className="container flex items-center justify-between">
          <Logo className="h-7 w-auto" />
          <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} VENDOS SALON</p>
        </div>
      </footer>
    </div>
  )
}

// ── Customer home ─────────────────────────────────────────────────────────────

function CustomerHomePage({ services }: { services: Service[] | undefined }) {
  const activeServices = services?.filter((s) => s.is_active) ?? []

  return (
    <div className="flex flex-col">
      {/* hero */}
      <section className="relative flex flex-col items-center justify-center text-center min-h-[92vh] px-4">
        <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-8">
          Premium Male Grooming
        </p>
        <h1 className="font-display text-[clamp(5rem,18vw,16rem)] leading-none uppercase">
          Look<br />Sharp.
        </h1>
        <div className="w-12 h-px bg-border my-8" />
        <p className="text-sm text-muted-foreground tracking-wider max-w-xs mb-10">
          Expert cuts. Precision grooming. Online booking in seconds.
        </p>
        <div className="flex items-center gap-10">
          <Link
            to="/book"
            className="bg-foreground text-background text-xs tracking-widest uppercase px-10 py-4 hover:bg-foreground/90 transition-colors"
          >
            Book Now
          </Link>
          <a
            href="#services"
            className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
          >
            Our Services ↓
          </a>
        </div>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-px h-16 bg-border" />
      </section>

      {/* services */}
      <section id="services" className="border-t border-border py-24">
        <div className="container">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-12">
            <div>
              <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">What We Offer</p>
              <h2 className="font-display text-5xl md:text-7xl uppercase">Our Services</h2>
            </div>
            <Link
              to="/book"
              className="self-start md:self-end text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
            >
              Book Now →
            </Link>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
            {activeServices.length === 0 ? (
              <div className="bg-background p-12 col-span-full text-center text-muted-foreground text-sm">
                No services available
              </div>
            ) : activeServices.map((service) => (
              <div key={service.id} className="bg-background p-8 flex flex-col gap-6 group hover:bg-secondary transition-colors">
                <div className="flex-1">
                  <h3 className="text-sm font-semibold uppercase tracking-widest mb-3">{service.name}</h3>
                  {service.description && (
                    <p className="text-xs text-muted-foreground leading-relaxed">{service.description}</p>
                  )}
                </div>
                <div className="flex items-center justify-between pt-6 border-t border-border text-xs">
                  <span className="text-muted-foreground tracking-wider uppercase">{service.duration_minutes} min</span>
                  <span className="font-semibold tracking-wider">${Number(service.price).toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-12 flex justify-center">
            <Link
              to="/book"
              className="bg-foreground text-background text-xs tracking-widest uppercase px-12 py-4 hover:bg-foreground/90 transition-colors"
            >
              Book an Appointment
            </Link>
          </div>
        </div>
      </section>

      {/* ethos */}
      <section className="border-t border-border py-24">
        <div className="container">
          <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-12 text-center">
            The Vendos Experience
          </p>
          <div className="grid sm:grid-cols-3 gap-px bg-border">
            {[
              { num: "01", title: "Expert Barbers", desc: "Years of experience delivering precise, stylish cuts that keep you coming back." },
              { num: "02", title: "Easy Booking", desc: "Book your appointment online 24/7 — no phone calls, no waiting, no hassle." },
              { num: "03", title: "Premium Service", desc: "From classic cuts to full grooming packages. Your style, perfected." },
            ].map((item) => (
              <div key={item.num} className="bg-background p-10 flex flex-col gap-4">
                <span className="font-display text-5xl text-muted-foreground/30">{item.num}</span>
                <h3 className="text-sm font-semibold uppercase tracking-widest">{item.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* cta banner */}
      <section className="border-t border-border py-32">
        <div className="container flex flex-col items-center text-center gap-8">
          <h2 className="font-display text-[clamp(3rem,10vw,8rem)] uppercase leading-none">
            Ready?
          </h2>
          <p className="text-sm text-muted-foreground tracking-wider max-w-xs">
            Book your appointment today and experience the difference.
          </p>
          <Link
            to="/book"
            className="bg-foreground text-background text-xs tracking-widest uppercase px-12 py-4 hover:bg-foreground/90 transition-colors"
          >
            Book Now
          </Link>
        </div>
      </section>

      {/* footer */}
      <footer className="border-t border-border py-12">
        <div className="container grid sm:grid-cols-3 gap-10 text-xs text-muted-foreground">
          <div className="flex flex-col gap-4">
            <Logo className="h-8 w-auto self-start" />
            <p className="text-[10px] tracking-widest uppercase">Premium Barbershop</p>
          </div>
          <div className="flex flex-col gap-3">
            <p className="text-[10px] tracking-widest uppercase text-foreground mb-1">Hours</p>
            <p>Mon – Sat: 9:00 AM – 6:00 PM</p>
            <p>Sunday: Closed</p>
          </div>
          <div className="flex flex-col gap-3">
            <p className="text-[10px] tracking-widest uppercase text-foreground mb-1">Quick Links</p>
            <Link to="/book" className="hover:text-foreground transition-colors">Book Appointment</Link>
            <Link to="/login" className="hover:text-foreground transition-colors">Sign In</Link>
          </div>
        </div>
        <div className="container mt-10 pt-6 border-t border-border">
          <p className="text-[10px] tracking-widest uppercase text-muted-foreground">
            © {new Date().getFullYear()} VENDOS SALON. All rights reserved.
          </p>
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
