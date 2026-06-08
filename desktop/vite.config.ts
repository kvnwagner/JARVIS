import { defineConfig } from "vite";

export default defineConfig({
  base: "./",

  clearScreen: false,

  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true
  },

  envPrefix: ["VITE_", "TAURI_"]
});