export type UserRole = "customer" | "admin"

export interface User {
  id: string
  name: string
  email: string
  phone: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Service {
  id: string
  name: string
  description: string | null
  duration_minutes: number
  price: string
  is_active: boolean
}

export type BookingStatus = "confirmed" | "cancelled" | "completed"

export interface ServiceSummary {
  id: string
  name: string
  duration_minutes: number
  price: string
}

export interface UserSummary {
  id: string
  name: string
  email: string
  phone: string | null
}

export interface Booking {
  id: string
  user_id: string
  service_id: string
  start_time: string
  end_time: string
  status: BookingStatus
  notes: string | null
  cancellation_reason: string | null
  created_at: string
  service: ServiceSummary | null
  user: UserSummary | null
}

export interface BusinessHours {
  id: string
  day_of_week: number
  open_time: string
  close_time: string
  is_closed: boolean
}

export interface BlockedDate {
  id: string
  date: string
  reason: string | null
}

export interface BookingPage {
  items: Booking[]
  total: number
  limit: number
  offset: number
}

export type SlotStatus = "available" | "held" | "booked"

export interface TimeSlot {
  start_time: string
  end_time: string
  status: SlotStatus
}
