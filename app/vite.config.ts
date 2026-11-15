import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base relativa: o mesmo build funciona no GitHub Pages (subpasta) e aberto localmente.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1600 },
})
