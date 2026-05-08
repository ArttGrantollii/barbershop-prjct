import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import type { Variants } from "framer-motion"
import { Ban, CalendarDays, Clock, LayoutDashboard, Settings, Users } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { Logo } from "@/components/Logo"
import { FadeIn, StaggerIn, StaggerChild } from "@/components/ui/FadeIn"
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
  { to: "/admin/staff",         label: "Staff",          desc: "Manage stylists and skills", icon: Users },
  { to: "/admin/hours",         label: "Business Hours", desc: "Set your weekly schedule",   icon: Clock },
  { to: "/admin/blocked-dates", label: "Blocked Dates",  desc: "Close days off",             icon: Ban },
]

function AdminHomePage({ services }: { services: Service[] | undefined }) {
  const { user } = useAuth()

  return (
    <div className="flex flex-col">
      <section className="border-b border-border">
        <div className="container py-16 flex flex-col gap-2">
          <FadeIn>
            <p className="text-xs tracking-widest uppercase text-muted-foreground mb-4">Admin View</p>
          </FadeIn>
          <FadeIn delay={0.05}>
            <h1 className="font-display text-6xl md:text-8xl uppercase tracking-wide">
              Welcome back,<br />{user?.name?.split(" ")[0]}.
            </h1>
          </FadeIn>
          <FadeIn delay={0.1}>
            <p className="text-sm text-muted-foreground mt-4 max-w-sm">
              Manage your salon, bookings, and services from one place.
            </p>
          </FadeIn>
          <FadeIn delay={0.15}>
            <div className="mt-8">
              <Link
                to="/admin/dashboard"
                className="inline-flex items-center gap-3 bg-foreground text-background text-xs tracking-widest uppercase px-8 py-4 hover:bg-foreground/90 transition-colors"
              >
                <LayoutDashboard className="h-3.5 w-3.5" />
                Go to Dashboard
              </Link>
            </div>
          </FadeIn>
        </div>
      </section>

      <section className="container py-16">
        <FadeIn>
          <p className="text-xs tracking-widest uppercase text-muted-foreground mb-8">Quick Access</p>
        </FadeIn>
        <StaggerIn className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border" stagger={0.07}>
          {adminQuickLinks.map(({ to, label, desc, icon: Icon }) => (
            <StaggerChild key={to}>
              <Link
                to={to}
                className="group flex items-start gap-5 p-8 bg-background hover:bg-secondary transition-colors h-full"
              >
                <Icon className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0 group-hover:text-foreground transition-colors" />
                <div className="min-w-0">
                  <p className="text-sm font-medium uppercase tracking-wider">{label}</p>
                  <p className="text-xs text-muted-foreground mt-1">{desc}</p>
                </div>
              </Link>
            </StaggerChild>
          ))}
        </StaggerIn>
      </section>

      {services && services.filter((s) => s.is_active).length > 0 && (
        <section className="border-t border-border py-16">
          <div className="container">
            <FadeIn>
              <div className="flex items-end justify-between mb-8">
                <div>
                  <p className="text-xs tracking-widest uppercase text-muted-foreground mb-2">On the Menu</p>
                  <h2 className="font-display text-4xl uppercase tracking-wide">Active Services</h2>
                </div>
                <Link to="/admin/services" className="text-xs tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors">
                  Manage →
                </Link>
              </div>
            </FadeIn>
            <StaggerIn className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border" stagger={0.06}>
              {services.filter((s) => s.is_active).map((service) => (
                <StaggerChild key={service.id}>
                  <div className="bg-background p-6 flex items-center justify-between gap-4">
                    <p className="text-sm font-medium uppercase tracking-wide truncate">{service.name}</p>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-semibold">${Number(service.price).toFixed(2)}</p>
                      <p className="text-xs text-muted-foreground">{service.duration_minutes} min</p>
                    </div>
                  </div>
                </StaggerChild>
              ))}
            </StaggerIn>
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

  // Hero text animate in
  const heroVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
  }
  const heroItem: Variants = {
    hidden: { opacity: 0, y: 32 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.85, ease: [0.16, 1, 0.3, 1] } },
  }

  return (
    <div className="flex flex-col">
      {/* hero */}
      <section className="relative flex flex-col items-center justify-center text-center min-h-[92vh] px-4 overflow-hidden">

        {/* subtle animated bg rings */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
        >
          <motion.div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border border-border rounded-full"
            animate={{ scale: [1, 1.04, 1], opacity: [0.4, 0.2, 0.4] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] border border-border rounded-full"
            animate={{ scale: [1, 1.03, 1], opacity: [0.2, 0.08, 0.2] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          />
        </motion.div>

        <motion.div
          className="relative flex flex-col items-center"
          variants={heroVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.p variants={heroItem} className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-8">
            Premium Male Grooming
          </motion.p>
          <motion.h1 variants={heroItem} className="font-display text-[clamp(5rem,18vw,16rem)] leading-none uppercase">
            Look<br />Sharp.
          </motion.h1>
          <motion.div variants={heroItem} className="w-12 h-px bg-border my-8" />
          <motion.p variants={heroItem} className="text-sm text-muted-foreground tracking-wider max-w-xs mb-10">
            Expert cuts. Precision grooming. Online booking in seconds.
          </motion.p>
          <motion.div variants={heroItem} className="flex items-center gap-10">
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
          </motion.div>
        </motion.div>

        <motion.div
          className="absolute bottom-0 left-1/2 -translate-x-1/2 w-px h-16 bg-border"
          initial={{ scaleY: 0, originY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.8, delay: 1, ease: [0.16, 1, 0.3, 1] }}
        />
      </section>

      {/* services */}
      <section id="services" className="border-t border-border py-24">
        <div className="container">
          <FadeIn>
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
          </FadeIn>

          <StaggerIn className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border" stagger={0.08}>
            {activeServices.length === 0 ? (
              <div className="bg-background p-12 col-span-full text-center text-muted-foreground text-sm">
                No services available
              </div>
            ) : activeServices.map((service) => (
              <StaggerChild key={service.id}>
                <div className="bg-background p-8 flex flex-col gap-6 group hover:bg-secondary transition-colors h-full">
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
              </StaggerChild>
            ))}
          </StaggerIn>

          <FadeIn delay={0.1}>
            <div className="mt-12 flex justify-center">
              <Link
                to="/book"
                className="bg-foreground text-background text-xs tracking-widest uppercase px-12 py-4 hover:bg-foreground/90 transition-colors"
              >
                Book an Appointment
              </Link>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ethos */}
      <section className="border-t border-border py-24">
        <div className="container">
          <FadeIn>
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-12 text-center">
              The Vendos Experience
            </p>
          </FadeIn>
          <StaggerIn className="grid sm:grid-cols-3 gap-px bg-border" stagger={0.1}>
            {[
              { num: "01", title: "Expert Barbers", desc: "Years of experience delivering precise, stylish cuts that keep you coming back." },
              { num: "02", title: "Easy Booking",   desc: "Book your appointment online 24/7 — no phone calls, no waiting, no hassle." },
              { num: "03", title: "Premium Service", desc: "From classic cuts to full grooming packages. Your style, perfected." },
            ].map((item) => (
              <StaggerChild key={item.num}>
                <div className="bg-background p-10 flex flex-col gap-4 h-full">
                  <span className="font-display text-5xl text-muted-foreground/20">{item.num}</span>
                  <h3 className="text-sm font-semibold uppercase tracking-widest">{item.title}</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
                </div>
              </StaggerChild>
            ))}
          </StaggerIn>
        </div>
      </section>

      {/* cta banner */}
      <section className="border-t border-border py-32">
        <FadeIn y={40}>
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
        </FadeIn>
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
