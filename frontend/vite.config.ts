import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Optional: uncomment to proxy API calls through Vite dev server
      // '/identify_reciter': 'http://127.0.0.1:8000',
    },
  },
})
