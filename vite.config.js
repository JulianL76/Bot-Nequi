import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

const root = import.meta.dirname;

// Vite compila el frontend a static/dist/ con manifest; django-vite lee ese
// manifest y emite las etiquetas <script>/<link> correctas en cada plantilla.
// En desarrollo (npm run dev) sirve desde localhost:5173 con HMR.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  root: resolve(root, 'frontend'),
  base: '/static/dist/',
  build: {
    outDir: resolve(root, 'static/dist'),
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        app: resolve(root, 'frontend/app.jsx'),
      },
    },
  },
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    // El HTML lo sirve Django; Vite solo entrega los assets.
    origin: 'http://localhost:5173',
  },
});
