import "maplibre-gl/dist/maplibre-gl.css";
import { maplibregl } from "./setup";
import { useEffect, useRef, useState } from "react";
import { mapStyle } from "./style";

export type Pin = { id: string; name: string; lat: number; lng: number; hiring: boolean };

/** The map with one button per startup. Pins are real buttons (named for screen
 *  readers and tests), coloured only by hiring (neon green) or not (grey). */
export function MapView({
  center,
  zoom,
  pins,
  selectedId,
  onSelect,
  onUnavailable,
  fitKey,
}: {
  center: { lat: number; lng: number };
  zoom: number;
  pins: Pin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onUnavailable: () => void;
  /** When this changes (new results or filters), the map zooms to fit all pins. */
  fitKey: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef(new Map<string, { marker: maplibregl.Marker; el: HTMLButtonElement }>());
  const [ready, setReady] = useState(false);
  const [settled, setSettled] = useState(false); // fitted and not moving (tests wait for it)
  const fitted = useRef(false);

  useEffect(() => {
    if (!container.current) return;
    try {
      map.current = new maplibregl.Map({
        container: container.current,
        style: mapStyle(),
        center: [center.lng, center.lat],
        zoom,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch {
      onUnavailable(); // no WebGL on this device
      return;
    }
    map.current.touchZoomRotate.disableRotation();
    map.current.on("error", () => {}); // missing tiles or fonts: keep the black map + pins
    setReady(true);
    return () => {
      map.current?.remove();
      map.current = null;
      markers.current.clear();
    };
    // Created once; later centre/zoom changes are applied below.
  }, []);

  // Show every pin: fit the map to them whenever the results change. Without pins,
  // centre on the search point.
  useEffect(() => {
    if (!ready || !map.current) return;
    if (pins.length === 0) {
      map.current.easeTo({ center: [center.lng, center.lat], zoom, duration: 300 });
      return;
    }
    map.current.resize(); // measure the box as it is now, so the fit is right
    const bounds = new maplibregl.LngLatBounds();
    for (const p of pins) bounds.extend([p.lng, p.lat]);
    const narrow = (container.current?.clientWidth ?? 800) < 600;
    setSettled(false);
    map.current.once("moveend", () => setSettled(true));
    map.current.fitBounds(bounds, {
      // Room for the floating bar at the top; tighter sides on phones.
      padding: { top: 90, bottom: 40, left: narrow ? 30 : 60, right: narrow ? 30 : 60 },
      maxZoom: 14,
      duration: fitted.current ? 300 : 0, // the first view appears in place
    });
    fitted.current = true;
    // Only when the result set changes, not on every pin re-render.
  }, [ready, fitKey]);

  // Pins: one real button each, with a 24px tap area around a small dot. They're
  // created in small batches, one per frame, so a budget phone never freezes.
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const style = (el: HTMLButtonElement, pin: Pin) => {
      el.setAttribute("aria-label", `${pin.name}, ${pin.hiring ? "hiring" : "not hiring"}`);
      const dot = el.firstElementChild as HTMLElement;
      dot.className = [
        "block rounded-full border-2 border-panel transition-transform",
        pin.hiring ? "size-4 bg-accent" : "size-3.5 bg-muted",
        pin.id === selectedId ? "scale-150 outline-2 outline-fg" : "",
      ].join(" ");
    };
    const create = (pin: Pin) => {
      // MapLibre owns the wrapper's classes (they position it); we style the button.
      const wrapper = document.createElement("div");
      const el = document.createElement("button");
      el.type = "button";
      el.className = "flex size-6 cursor-pointer items-center justify-center";
      el.appendChild(document.createElement("span"));
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(pin.id);
      });
      wrapper.appendChild(el);
      const marker = new maplibregl.Marker({ element: wrapper }).setLngLat([pin.lng, pin.lat]).addTo(m);
      markers.current.set(pin.id, { marker, el });
      style(el, pin);
    };

    const wanted = new Set(pins.map((p) => p.id));
    for (const [id, entry] of markers.current) {
      if (!wanted.has(id)) {
        entry.marker.remove();
        markers.current.delete(id);
      }
    }
    const todo: Pin[] = [];
    for (const pin of pins) {
      const entry = markers.current.get(pin.id);
      if (entry) style(entry.el, pin);
      else todo.push(pin);
    }
    let frame = 0;
    const batch = () => {
      for (const pin of todo.splice(0, 25)) create(pin);
      if (todo.length) frame = requestAnimationFrame(batch);
    };
    batch();
    return () => cancelAnimationFrame(frame);
  }, [pins, selectedId, ready, onSelect]);

  // MapLibre's CSS makes the map element position: relative, so an outer box does the
  // positioning and the map fills it.
  return (
    <div className="absolute inset-0" data-map-settled={settled || undefined}>
      <div ref={container} className="h-full w-full" />
    </div>
  );
}
