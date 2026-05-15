import { expect, test } from "@playwright/test"
import { collectRuntimeErrors } from "./runtime-errors"

const user = {
  id: "00000000-0000-4000-8000-000000000011",
  name: "Route Tester",
  email: "route@example.com",
  phone: "1234567890",
  role: "customer",
  is_active: true,
  is_email_verified: true,
  created_at: "2026-05-14T12:00:00.000Z",
}

test("logout calls the backend and clears local tokens", async ({ page }) => {
  let logoutBody: unknown = null
  const runtimeErrors = collectRuntimeErrors(page)

  await page.addInitScript(() => {
    window.localStorage.setItem("access_token", "access-token")
    window.localStorage.setItem("refresh_token", "refresh-token")
  })

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({ json: user })
  })

  await page.route("**/api/v1/auth/logout", async (route) => {
    logoutBody = route.request().postDataJSON()
    await route.fulfill({ status: 204 })
  })

  await page.goto("/")
  await page.getByRole("button", { name: /Sign out/i }).click()

  await expect(page.locator("header").getByRole("link", { name: /Sign in/i })).toBeVisible()
  await expect.poll(() => logoutBody).toEqual({ refresh_token: "refresh-token" })
  await expect.poll(() => page.evaluate(() => localStorage.getItem("access_token"))).toBeNull()
  await expect.poll(() => page.evaluate(() => localStorage.getItem("refresh_token"))).toBeNull()
  expect(runtimeErrors).toEqual([])
})
