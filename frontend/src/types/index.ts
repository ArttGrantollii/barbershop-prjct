export type UserRole = "customer" | "admin"

export interface User {
  id: string
  name: string
  email: string
  phone: string | null
  role: UserRole
  is_active: boolean
  is_email_verified: boolean
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

export type BookingStatus = "confirmed" | "cancelled" | "completed" | "no_show"

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

export interface Staff {
  id: string
  name: string
  phone: string | null
  photo_url: string | null
  is_active: boolean
  display_order: number
}

export interface StaffWithServices extends Staff {
  service_ids: string[]
}

export interface StaffWorkingHours {
  id: string
  staff_id: string
  day_of_week: number
  open_time: string
  close_time: string
  is_closed: boolean
}

export interface StaffBlockedTime {
  id: string
  staff_id: string
  start_time: string
  end_time: string
  reason: string | null
}

export interface StaffSummary {
  id: string
  name: string
  photo_url: string | null
}

export interface Booking {
  id: string
  user_id: string | null
  service_id: string
  staff_id: string
  customer_name: string | null
  customer_email: string | null
  customer_phone: string | null
  start_time: string
  end_time: string
  status: BookingStatus
  notes: string | null
  cancellation_reason: string | null
  created_at: string
  service: ServiceSummary | null
  user: UserSummary | null
  staff: StaffSummary | null
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

export interface AdminDashboard {
  today_bookings_count: number
  today_revenue: string
  week_bookings_count: number
  confirmed_total: number
  cancelled_total: number
  today_schedule: Booking[]
}

export type SlotStatus = "available" | "held" | "booked" | "cooldown"

export interface TimeSlot {
  start_time: string
  end_time: string
  status: SlotStatus
}

export type WaitlistStatus = "active" | "booked" | "cancelled"

export interface WaitlistEntry {
  id: string
  user_id: string | null
  service_id: string
  staff_id: string | null
  booking_id: string | null
  customer_name: string
  customer_email: string | null
  customer_phone: string | null
  preferred_date: string | null
  notes: string | null
  status: WaitlistStatus
  created_at: string
  service: ServiceSummary | null
  user: UserSummary | null
  staff: StaffSummary | null
}

export interface BookingAuditEvent {
  id: string
  booking_id: string
  actor_id: string | null
  actor_role: "customer" | "admin" | "system"
  action: string
  previous_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  created_at: string
}
