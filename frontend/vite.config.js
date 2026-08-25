import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Configuração padrão do Vite para um projeto React.
// O servidor de dev sobe em http://localhost:5173 por padrão.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
