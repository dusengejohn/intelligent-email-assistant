import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The generator's page. In Docker, FastAPI serves the built files (same origin).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // Node by default; component tests opt into jsdom with `// @vitest-environment jsdom`
    setupFiles: ['./src/test-setup.ts'],
  },
  server: {
    // 5174: the inbox's dev page already uses 5173
    port: 5174,
    strictPort: true,
    // Forward /api to the generator's dev API (uvicorn --port 8001)
    proxy: {
      '/api': 'http://localhost:8001',
    },
  },
})
