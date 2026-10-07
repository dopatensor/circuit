import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig(({ mode }) => {
  // In dev and preview the frontend calls the backend through a proxy, so the browser
  // only ever talks to one origin. API_PROXY_TARGET lets tests point at another API.
  const env = loadEnv(mode, ".", "");
  const backend = env.API_PROXY_TARGET || "http://localhost:8000";
  const proxy = { "/api": backend, "/health": backend };

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: "prompt", // show "Update available" instead of reloading by itself
        injectRegister: false, // registered in src/pwa/UpdateBar.tsx
        includeAssets: ["favicon.svg", "apple-touch-icon.png", "robots.txt"],
        manifest: {
          name: "Circuit",
          short_name: "Circuit",
          description: "Find people who need what you offer, and offer what you need.",
          start_url: "/", // redirects to your main tab
          scope: "/",
          display: "standalone",
          orientation: "portrait",
          theme_color: "#000000",
          background_color: "#000000",
          icons: [
            { src: "/pwa-192.png", sizes: "192x192", type: "image/png" },
            { src: "/pwa-512.png", sizes: "512x512", type: "image/png" },
            { src: "/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          ],
        },
        workbox: {
          // The app shell: precached, so the app opens instantly and offline.
          globPatterns: ["**/*.{js,css,html,svg,png}"],
          // The map library (~280 KB gzipped) isn't pre-downloaded on install: founders
          // never open the map. It's cached the first time someone does (below).
          globIgnores: ["**/MapView-*"],
          navigateFallback: "/index.html",
          navigateFallbackDenylist: [/^\/api\//, /^\/health/, /^\/docs/],
          cleanupOutdatedCaches: true,
          runtimeCaching: [
            {
              urlPattern: ({ url }) => url.pathname.startsWith("/assets/MapView-"),
              handler: "CacheFirst", // file names change with every build, so never stale
              options: { cacheName: "circuit-map", expiration: { maxEntries: 6 } },
            },
            {
              // API data that stays readable offline (network first, cache as fallback):
              // your matches, jobs and applications. Nothing else from /api is cached,
              // and never auth. (This function is copied into the service worker as
              // text, so it can't use variables from this file.)
              urlPattern: ({ url, request }) =>
                request.method === "GET" &&
                /^\/api\/(matches|jobs|applications\/me)(\/|$)/.test(url.pathname),
              handler: "NetworkFirst",
              options: {
                cacheName: "circuit-api", // cleared on sign-out and persona switch
                networkTimeoutSeconds: 5,
                expiration: { maxEntries: 80, maxAgeSeconds: 7 * 24 * 3600 },
                cacheableResponse: { statuses: [200] },
                plugins: [
                  {
                    // Store responses under the bare URL, so the Authorization header
                    // (the token) is never written into the cache.
                    cacheKeyWillBeUsed: async ({ request }) => request.url,
                  },
                ],
              },
            },
          ],
        },
      }),
    ],
    server: { host: true, proxy }, // host: reachable from a phone on the same Wi-Fi
    preview: { host: true, proxy },
    build: { target: "es2022" },
  };
});
