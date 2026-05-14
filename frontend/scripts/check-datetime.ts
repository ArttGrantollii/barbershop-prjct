import assert from "node:assert/strict"

import { salonDateTimeInputToUtcIso, salonDateTimeInputValue } from "../src/lib/datetime.js"

assert.equal(
  salonDateTimeInputToUtcIso("2026-01-15T09:30", "America/New_York"),
  "2026-01-15T14:30:00.000Z",
)
assert.equal(
  salonDateTimeInputToUtcIso("2026-07-15T09:30", "America/New_York"),
  "2026-07-15T13:30:00.000Z",
)
assert.equal(
  salonDateTimeInputToUtcIso("2026-05-14T10:00", "Europe/Warsaw"),
  "2026-05-14T08:00:00.000Z",
)
assert.equal(
  salonDateTimeInputValue("2026-07-15T13:30:00.000Z", "America/New_York"),
  "2026-07-15T09:30",
)

console.log("Datetime timezone checks passed")
