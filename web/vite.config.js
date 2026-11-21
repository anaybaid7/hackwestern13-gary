import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Mock mode reads ../contract/examples/state.json, which sits outside web/.
  server: { fs: { allow: ['..'] } },
  test: { environment: 'jsdom' },
})
