import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Clock, Scissors, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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

export default function HomePage() {
  const { data: services } = useServices()

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
