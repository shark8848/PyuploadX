import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: process.env.UPLOAD_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/healthz": {
        target: process.env.UPLOAD_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "vendor-react", test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/ },
            {
              name: "vendor-antd",
              test: /node_modules[\\/](antd|@ant-design|@rc-component|rc-)[\\/]/,
            },
          ],
        },
      },
    },
  },
});
