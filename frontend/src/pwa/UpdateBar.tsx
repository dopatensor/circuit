import { useRegisterSW } from "virtual:pwa-register/react";

/** A new version was deployed: one tap reloads into it. */
export function UpdateBar() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      // Check for a new version every hour while the app stays open.
      if (registration) setInterval(() => void registration.update(), 60 * 60 * 1000);
    },
  });
  if (!needRefresh) return null;
  return (
    <button
      onClick={() => void updateServiceWorker(true)}
      className="min-h-11 w-full bg-fg px-4 text-left text-sm text-bg md:rounded-xl"
    >
      Update available, tap to refresh
    </button>
  );
}
