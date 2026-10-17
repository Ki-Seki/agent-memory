import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// The page is served by `mem ui` under /next/ and shipped inside the Python package.
// `npm run dev` proxies the API to a running `mem ui` (set MEM_UI to its address).
export default defineConfig({
  base: "/next/",
  plugins: [tailwindcss(), svelte()],
  resolve: { alias: { $lib: fileURLToPath(new URL("./src/lib", import.meta.url)) } },
  build: { outDir: "../src/agent_memory/webui_next", emptyOutDir: true, assetsDir: "assets", sourcemap: false },
  server: {
    proxy: {
      // mem ui only answers its own host and origin, so the proxy speaks as the page served by mem ui would
      "/api": {
        target: process.env.MEM_UI || "http://127.0.0.1:8790",
        changeOrigin: true,
        configure: (proxy) => proxy.on("proxyReq", (req) => req.removeHeader("origin")),
      },
    },
  },
});
