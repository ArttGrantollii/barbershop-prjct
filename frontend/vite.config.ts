import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    // inotify doesn't fire reliably across the Windows → Docker bind mount,
    // so HMR misses edits. Polling is the standard fix for this setup.
    watch: { usePolling: true, interval: 300 },
  },
})
