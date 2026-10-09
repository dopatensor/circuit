import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import { BrowserRouter } from "react-router";
import App from "./App";
import { AuthProvider } from "./auth";
import { ToastProvider } from "./components/ds";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* Motion: only the small DOM feature set, and "reduce motion" respected everywhere. */}
        <LazyMotion features={domAnimation} strict>
          <MotionConfig reducedMotion="user">
            <ToastProvider>
              <AuthProvider>
                <App />
              </AuthProvider>
            </ToastProvider>
          </MotionConfig>
        </LazyMotion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
