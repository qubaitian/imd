import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  test: {
    projects: [
      { extends: true, test: { name: 'modules', include: ['src/**/*.test.js'], exclude: ['src/MarkdownView.test.js'] } },
      { extends: true, resolve: { conditions: ['browser'] }, test: { name: 'components', include: ['src/MarkdownView.test.js'], environment: 'jsdom' } },
    ],
  },
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
