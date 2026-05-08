import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import type { TimeSlot } from "@/types"

const WS_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
  .replace(/^https?/, (protocol: string) => (protocol === "https" ? "wss" : "ws"))

export function useSlotWebSocket(
  serviceId: string | undefined,
  date: string | undefined,
  staffId: string = "any",
): { connected: boolean } {
  const queryClient = useQueryClient()
  const [connected, setConnected] = useState(false)
  const stopped = useRef(false)
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!date || !serviceId) {
      setConnected(false)
      return
    }

    stopped.current = false

    function connect(backoff = 0) {
      if (stopped.current) return

      retryTimer.current = setTimeout(() => {
        if (stopped.current) return

        const ws = new WebSocket(`${WS_BASE}/api/v1/ws/slots/${date}`)
        wsRef.current = ws

        ws.onopen = () => setConnected(true)

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data) as {
              type: string
              start_time: string
              staff_id?: string
              status: TimeSlot["status"]
            }
            if (msg.type !== "slot_update") return
            if (staffId !== "any" && msg.staff_id && msg.staff_id !== staffId) return

            // Normalize both timestamps to ms to handle Z vs +00:00 format differences
            const msgMs = new Date(msg.start_time).getTime()

            queryClient.setQueryData<TimeSlot[]>(
              ["slots", serviceId, date, staffId],
              (prev) =>
                prev?.map((slot) =>
                  new Date(slot.start_time).getTime() === msgMs
                    ? { ...slot, status: msg.status }
                    : slot,
                ),
            )
          } catch {
            // ignore malformed messages
          }
        }

        ws.onclose = () => {
          setConnected(false)
          // Exponential backoff: 500ms → 1s → 2s → 4s → 8s max
          if (!stopped.current) connect(Math.min((backoff || 500) * 2, 8_000))
        }

        ws.onerror = () => ws.close()
      }, backoff)
    }

    connect()

    return () => {
      stopped.current = true
      if (retryTimer.current) clearTimeout(retryTimer.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [date, serviceId, staffId, queryClient])

  return { connected }
}
