import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Mock mode reads ../contract/examples/state.json, which sits outside web/.
  server: { fs: { allow: ['..'] } },
  // The tests read clock times and "today", so they run in the team's timezone
  // wherever the machine is.
  test: { environment: 'jsdom', env: { TZ: 'America/Toronto' } },
})
