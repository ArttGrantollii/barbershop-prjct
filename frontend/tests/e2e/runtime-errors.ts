import type { Page } from "@playwright/test"

export function collectRuntimeErrors(page: Page) {
  const errors: string[] = []

  page.on("pageerror", (error) => {
    errors.push(error.message)
  })

  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text())
    }
  })

  return errors
}
