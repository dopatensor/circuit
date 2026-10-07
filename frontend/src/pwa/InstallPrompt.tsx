import { useEffect, useState } from "react";

// "Add Circuit to your home screen", once, after the second visit, and never again
// once dismissed or installed. iPhones have no install prompt, so they get the short
// manual steps instead.
const VISITS = "circuit.visits";
const DISMISSED = "circuit.install-dismissed";
const COUNTED = "circuit.visit-counted"; // per browser session

type InstallEvent = Event & { prompt: () => Promise<void> };

function storage<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

function countVisit(): number {
  return storage(() => {
    let visits = Number(localStorage.getItem(VISITS) ?? "0");
    if (!sessionStorage.getItem(COUNTED)) {
      visits += 1;
      localStorage.setItem(VISITS, String(visits));
      sessionStorage.setItem(COUNTED, "1");
    }
    return visits;
  }, 0);
}

const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true;

const isIos = () =>
  /iPhone|iPad|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

export function InstallPrompt() {
  const [visits] = useState(countVisit);
  const [dismissed, setDismissed] = useState(() =>
    storage(() => localStorage.getItem(DISMISSED) === "1", true),
  );
  const [installEvent, setInstallEvent] = useState<InstallEvent | null>(null);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault(); // we show our own, quieter prompt
      setInstallEvent(e as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const dismiss = () => {
    storage(() => localStorage.setItem(DISMISSED, "1"), undefined);
    setDismissed(true);
  };

  const ios = isIos();
  if (dismissed || visits < 2 || isStandalone() || (!installEvent && !ios)) return null;

  return (
    <div
      role="dialog"
      aria-label="Add Circuit to your home screen"
      className="flex items-center gap-3 border-t border-line bg-bg px-4 py-3 md:rounded-xl md:border"
    >
      <p className="flex-1 text-sm">
        {ios
          ? "Add Circuit to your home screen: tap Share, then “Add to Home Screen”."
          : "Add Circuit to your home screen."}
      </p>
      {installEvent && (
        <button
          className="min-h-11 rounded-full bg-fg px-4 text-sm font-medium text-bg"
          onClick={async () => {
            await installEvent.prompt();
            dismiss();
          }}
        >
          Add
        </button>
      )}
      <button className="min-h-11 px-2 text-sm text-muted" onClick={dismiss}>
        Not now
      </button>
    </div>
  );
}
