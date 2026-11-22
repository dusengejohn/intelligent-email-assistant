import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Mirror the nginx setup: forward /api to the local FastAPI dev server
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
