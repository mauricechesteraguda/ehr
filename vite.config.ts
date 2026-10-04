// type-10022026-Maurice: Developer-supplied local HTTPS paths, never committed certificates.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import fs from "node:fs";

export default defineConfig(() => {
  const cert = process.env.HTTPS_CERT;
  const key = process.env.HTTPS_KEY;
  return { plugins: [react(), tailwindcss()], server: { https: cert && key ? { cert: fs.readFileSync(cert), key: fs.readFileSync(key) } : undefined, proxy: { "/api": "http://127.0.0.1:8000", "/oauth": "http://127.0.0.1:8000", "/fhir": "http://127.0.0.1:8000", "/.well-known": "http://127.0.0.1:8000" } } };
});
