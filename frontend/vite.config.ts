import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

const manualChunkGroups: Record<string, string[]> = {
  "react-vendor": ["react", "react-dom", "react-router-dom"],
  "query-vendor": ["@tanstack/react-query"],
  "motion-vendor": ["framer-motion"],
  "form-vendor": ["react-hook-form", "@hookform/resolvers", "zod"],
  "ui-vendor": [
    "@radix-ui/react-dialog",
    "@radix-ui/react-dropdown-menu",
    "@radix-ui/react-label",
    "@radix-ui/react-select",
    "@radix-ui/react-slot",
    "@radix-ui/react-toast",
  ],
  "utility-vendor": [
    "axios",
    "class-variance-authority",
    "clsx",
    "date-fns",
    "lucide-react",
    "tailwind-merge",
  ],
}

function manualChunks(id: string) {
  const normalizedId = id.replace(/\\/g, "/")

  for (const [chunkName, packages] of Object.entries(manualChunkGroups)) {
    if (packages.some((pkg) => normalizedId.includes(`/node_modules/${pkg}/`))) {
      return chunkName
    }
  }
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks,
      },
    },
  },
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
