import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 5173-5176 are taken by other class apps on this machine, so the desk pins 5177.
// The backend (http://localhost:8017) allows this origin in its CORS list.
export default defineConfig({
  plugins: [react()],
  server: { port: 5177, strictPort: true, open: true },
})
