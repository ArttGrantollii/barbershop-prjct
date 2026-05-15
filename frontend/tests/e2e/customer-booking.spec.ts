import { expect, test } from "@playwright/test"
import { collectRuntimeErrors } from "./runtime-errors"

const user = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Route Tester",
  email: "route@example.com",
  phone: "1234567890",
  role: "customer",
  is_active: true,
  is_email_verified: true,
  created_at: "2026-05-14T12:00:00.000Z",
}

const service = {
  id: "00000000-0000-4000-8000-000000000002",
  name: "Haircut",
  description: "Classic haircut",
  duration_minutes: 30,
  price: "25.00",
  is_active: true,
}

const staff = {
  id: "00000000-0000-4000-8000-000000000003",
  name: "Main Chair",
  phone: null,
  photo_url: null,
  is_active: true,
  display_order: 0,
}

const slot = {
  start_time: "2026-05-20T14:00:00.000Z",
  end_time: "2026-05-20T14:30:00.000Z",
  status: "available",
}

const booking = {
  id: "00000000-0000-4000-8000-000000000004",
  user_id: user.id,
  service_id: service.id,
  staff_id: staff.id,
  customer_name: user.name,
  customer_email: user.email,
  customer_phone: user.phone,
  start_time: slot.start_time,
  end_time: slot.end_time,
  status: "confirmed",
  notes: null,
  cancellation_reason: null,
  created_at: "2026-05-14T12:00:00.000Z",
  service,
  user,
  staff: { id: staff.id, name: staff.name, photo_url: staff.photo_url },
}

test("customer can complete the booking flow without doubled API paths", async ({ page }) => {
  const apiUrls: string[] = []
  const runtimeErrors = collectRuntimeErrors(page)

  await page.addInitScript(() => {
    window.localStorage.setItem("access_token", "access-token")
    window.localStorage.setItem("refresh_token", "refresh-token")
  })

  await page.route("**/api/v1/auth/me", async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ json: user })
  })
  await page.route("**/api/v1/business-info", async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ json: { name: "Vendos Salon", timezone: "UTC" } })
  })
  await page.route("**/api/v1/services", async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ json: [service] })
  })
  await page.route(`**/api/v1/staff/by-service/${service.id}`, async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ json: [staff] })
  })
  await page.route("**/api/v1/availability?**", async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ json: [slot] })
  })
  await page.route("**/api/v1/availability/hold", async (route) => {
    apiUrls.push(route.request().url())
    if (route.request().method() === "POST") {
      await route.fulfill({
        json: {
          start_time: slot.start_time,
          end_time: slot.end_time,
          staff_id: staff.id,
          expires_in_seconds: 600,
        },
      })
      return
    }
    await route.fulfill({ status: 204 })
  })
  await page.route("**/api/v1/bookings", async (route) => {
    apiUrls.push(route.request().url())
    await route.fulfill({ status: 201, json: booking })
  })

  await page.goto("/book")

  await page.getByRole("button", { name: /Haircut/i }).click()
  await page.locator('input[type="date"]').fill("2026-05-20")
  await page.getByRole("button", { name: /2:00 PM/i }).click()
  await page.getByRole("button", { name: /^Continue$/i }).click()
  await expect(page.getByText("Slot reserved for you")).toBeVisible()
  await page.getByRole("button", { name: /Confirm Booking/i }).click()

  await expect(page).toHaveURL(/\/bookings\/00000000-0000-4000-8000-000000000004\/confirmation/)
  expect(apiUrls.length).toBeGreaterThan(0)
  expect(apiUrls.every((url) => !url.includes("/api/api/v1/"))).toBe(true)
  expect(runtimeErrors).toEqual([])
})
