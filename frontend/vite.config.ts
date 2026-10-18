import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// a API (FastAPI) roda na 8010; a 8000 já está em uso nesta máquina
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8010' }
  }
});
