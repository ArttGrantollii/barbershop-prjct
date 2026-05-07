// Salon-local time formatting.
//
// All booking timestamps from the backend are absolute UTC instants. The
// display, however, must always be in the salon's local timezone — otherwise
// a customer in a different timezone sees mistranslated times. We surface
// the salon TZ via /business-info; pass it to these helpers everywhere a
// time or date is rendered.
//
// `tz` may be undefined while business-info is still loading; in that case
// Intl falls back to the browser's local timezone, which matches prior
// behavior so nothing visibly breaks during the load window.

function partsInTz(
  date: Date,
  tz: string | undefined,
  opts: Intl.DateTimeFormatOptions,
): Record<string, string> {
  return new Intl.DateTimeFormat("en-US", { timeZone: tz, ...opts })
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, p) => {
      acc[p.type] = p.value
      return acc
    }, {})
}

function toDate(iso: string | Date): Date {
  return typeof iso === "string" ? new Date(iso) : iso
}

export function salonTime(iso: string | Date, tz: string | undefined): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(toDate(iso))
}

export function salonClockParts(
  iso: string | Date,
  tz: string | undefined,
): { hourMin: string; ampm: string } {
  const parts = partsInTz(toDate(iso), tz, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
  return {
    hourMin: `${parts.hour}:${parts.minute}`,
    ampm: parts.dayPeriod ?? "",
  }
}

export function salonDateLong(iso: string | Date, tz: string | undefined): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(toDate(iso))
}

export function salonDateMedium(iso: string | Date, tz: string | undefined): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(toDate(iso))
}

export function salonDateShort(iso: string | Date, tz: string | undefined): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(toDate(iso))
}

// YYYY-MM-DD in the salon's TZ — string-comparable.
export function salonDayKey(iso: string | Date, tz: string | undefined): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(toDate(iso))
}

export function isSalonToday(iso: string | Date, tz: string | undefined): boolean {
  return salonDayKey(iso, tz) === salonDayKey(new Date(), tz)
}

// Short label like "EST", "PT", "UTC" for tagging displayed times.
export function salonTzAbbr(tz: string | undefined): string {
  if (!tz) return ""
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    timeZoneName: "short",
  }).formatToParts(new Date())
  return parts.find((p) => p.type === "timeZoneName")?.value ?? ""
}
