// Compila cada panel por separado como un unico archivo IIFE que incluye
// React y recharts (las plantillas Jinja no cargan React por su cuenta).
// Resultado: ../static/react/kpis.js y ../static/react/moovatrack.js
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const aqui = dirname(fileURLToPath(import.meta.url))
const paneles = [
  { nombre: 'kpis', entrada: 'src/kpis.jsx', global: 'MoovaKpis' },
  { nombre: 'moovatrack', entrada: 'src/moovatrack.jsx', global: 'MoovaTrack' },
]

for (const p of paneles) {
  await build({
    root: aqui,
    configFile: false,
    plugins: [react()],
    // El modo "lib" no reemplaza NODE_ENV: sin esto React entra en modo desarrollo.
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    build: {
      outDir: resolve(aqui, '../static/react'),
      emptyOutDir: false,
      sourcemap: false,
      lib: {
        entry: resolve(aqui, p.entrada),
        name: p.global,
        formats: ['iife'],
        fileName: () => `${p.nombre}.js`,
      },
    },
  })
}
