import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // Node by default (fast); component tests opt into a simulated browser with
    // a `// @vitest-environment jsdom` comment at the top of the file
    setupFiles: ['./src/test-setup.ts'],
  },
  server: {
    // Mirror the nginx setup: forward /api to the local FastAPI dev server
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
