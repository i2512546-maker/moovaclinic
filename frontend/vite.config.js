import { defineConfig } from 'vite'
import { resolve } from 'path'
import react from '@vitejs/plugin-react'

export default defineConfig(() => {
  const panel = process.env.PANEL || 'kpis'

  return {
    plugins: [react()],
    define: {
      'process.env.NODE_ENV': JSON.stringify('"production"')
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      },
      dedupe: ['react', 'react-dom']
    },
    build: {
      outDir: '../static/react',
      emptyOutDir: false,
      sourcemap: false,
      rollupOptions: {
        input: resolve(__dirname, `src/${panel}.jsx`),
        external: [],
        output: {
          format: 'iife',
          name: `Moova${panel.charAt(0).toUpperCase() + panel.slice(1)}`,
          entryFileNames: `${panel}.js`,
          inlineDynamicImports: true,
          globals: {}
        }
      }
    }
  }
})