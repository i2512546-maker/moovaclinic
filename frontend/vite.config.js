// Configuracion base de Vite. La compilacion de los dos paneles la dirige
// build.mjs (un bundle autocontenido por panel, sin hash en el nombre).
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
