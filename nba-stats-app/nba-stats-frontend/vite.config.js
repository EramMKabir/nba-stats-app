import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import process from "node:process";

const contentSecurityPolicyPlugin = (apiBaseUrl, mode) => {
  const connectSources = new Set(["'self'"]);

  if (apiBaseUrl) {
    try {
      connectSources.add(new URL(apiBaseUrl).origin);
    } catch {
      // A relative API URL is already covered by 'self'.
    }
  }

  if (mode === "development") {
    connectSources.add("http://localhost:*");
    connectSources.add("ws://localhost:*");
  }

  const policy = [
    "default-src 'self'",
    "base-uri 'self'",
    `connect-src ${[...connectSources].join(" ")}`,
    "font-src 'self' data:",
    "frame-src 'none'",
    "img-src 'self' data:",
    "object-src 'none'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
  ].join("; ");

  return {
    name: "content-security-policy",
    transformIndexHtml: {
      order: "pre",
      handler() {
        return [{
          tag: "meta",
          attrs: {
            "http-equiv": "Content-Security-Policy",
            content: policy,
          },
          injectTo: "head-prepend",
        }];
      },
    },
  };
};

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: '/',
    root: process.cwd(),
    plugins: [
      react(),
      contentSecurityPolicyPlugin(env.VITE_PYTHON_API_BASE_URL, mode),
    ],
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./testSetup.js",
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules")) {
              return id.toString().split("node_modules/")[1].split('/')[0].toString();
            }
          },
        },
      },
    },
  };
});
