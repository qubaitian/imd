import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: { terminal: ['@xterm/xterm', '@xterm/addon-fit'], markdown: ['markdown-it', 'dompurify'] },
      },
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
});
