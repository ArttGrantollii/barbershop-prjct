import type { Booking } from "@/types"

// Minimal RFC 5545 (iCalendar) generator for a single confirmed booking.
// Used for the "Add to calendar" download — every major calendar app (Apple
// Calendar, Google Calendar import, Outlook) understands the format.
//
// We deliberately keep this tiny and dependency-free instead of pulling in
// a library: we only ever emit one event, the field set is fixed, and the
// spec's edge cases (recurrence, attendees, alarms) don't apply here.

function pad(n: number): string {
  return String(n).padStart(2, "0")
}

// YYYYMMDDTHHMMSSZ in UTC, the form expected for the DTSTART/DTEND fields.
function toIcsDateTime(date: Date): string {
  return (
    date.getUTCFullYear().toString() +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    "T" +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes()) +
    pad(date.getUTCSeconds()) +
    "Z"
  )
}

// RFC 5545 §3.3.11 — TEXT values must escape backslash, comma, semicolon,
// and newline. Without this, a customer note containing a comma would split
// the property value and corrupt the file.
function icsEscape(s: string): string {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n")
}

export interface IcsParams {
  booking: Booking
  salonName: string
}

export function bookingToIcs({ booking, salonName }: IcsParams): string {
  const start = new Date(booking.start_time)
  const end = new Date(booking.end_time)
  const serviceName = booking.service?.name ?? "Appointment"
  const summary = `${serviceName} — ${salonName}`
  const description = booking.notes
    ? `${booking.notes}\nBooking ID: ${booking.id}`
    : `Booking ID: ${booking.id}`

  // RFC 5545 mandates CRLF line endings. Calendar apps are lenient about LF,
  // but Outlook in particular has rejected LF-only files in the past.
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Vendos Salon//Booking//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${booking.id}@vendos-salon`,
    `DTSTAMP:${toIcsDateTime(new Date())}`,
    `DTSTART:${toIcsDateTime(start)}`,
    `DTEND:${toIcsDateTime(end)}`,
    `SUMMARY:${icsEscape(summary)}`,
    `DESCRIPTION:${icsEscape(description)}`,
    `LOCATION:${icsEscape(salonName)}`,
    "STATUS:CONFIRMED",
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n")
}

export function downloadIcs(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: "text/calendar;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Defer revoke so the click handler has a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
