import "maplibre-gl/dist/maplibre-gl.css";
import { maplibregl } from "./setup";
import { useEffect, useRef, useState } from "react";
import { isDarkTheme, mapStyle } from "./style";

export type HeatCell = { lat: number; lng: number; weight: number };

const SOURCE = "gaps";

/** A heat layer of grid cells: brighter blue where the gap is bigger (one hue; on a
 *  black map, more is lighter). Weights are 0-1. */
export function HeatMap({
  center,
  cells,
  onUnavailable,
}: {
  center: { lat: number; lng: number };
  cells: HeatCell[];
  onUnavailable: () => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    if (!container.current) return;
    // The heat source and layer are part of the style from the start: MapLibre's
    // "load" event waits for every source, and never comes if the street tiles can't
    // be reached, which would leave the map without its heat.
    const style = mapStyle();
    style.sources[SOURCE] = { type: "geojson", data: { type: "FeatureCollection", features: [] } };
    style.layers.push({
      id: "gap-heat",
      type: "heatmap",
      source: SOURCE,
      paint: {
        "heatmap-weight": ["get", "weight"],
        "heatmap-intensity": 2,
        // Big enough that neighbouring 2 km cells merge into areas.
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 10, 40, 14, 160],
        "heatmap-opacity": 0.85,
        // One hue. More gap = more contrast with the map: lighter on the dark theme,
        // darker on the light one.
        "heatmap-color": isDarkTheme()
          ? ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(24,79,149,0)", 0.08, "rgba(24,79,149,0.6)", 0.35, "#2f8cff", 0.9, "#a9d0ff"]
          : ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(127,176,240,0)", 0.08, "rgba(127,176,240,0.6)", 0.35, "#5b93e0", 0.9, "#1f4f99"],
      },
    });
    let m: maplibregl.Map;
    try {
      m = new maplibregl.Map({
        container: container.current,
        style,
        center: [center.lng, center.lat],
        zoom: 11,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        cooperativeGestures: true, // one finger scrolls the page on phones
      });
    } catch {
      onUnavailable(); // no WebGL on this device
      return;
    }
    map.current = m;
    m.touchZoomRotate.disableRotation();
    m.on("error", () => {}); // missing tiles: keep the black map and the heat
    return () => {
      m.remove();
      map.current = null;
    };
    // Created once.
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    setSettled(false);
    const apply = () => {
      const source = m.getSource(SOURCE) as maplibregl.GeoJSONSource | undefined;
      if (!source) {
        m.once("styledata", apply); // the style isn't set up yet
        return;
      }
      source.setData({
        type: "FeatureCollection",
        features: cells.map((c) => ({
          type: "Feature",
          properties: { weight: c.weight },
          geometry: { type: "Point", coordinates: [c.lng, c.lat] },
        })),
      });
      if (cells.length > 0) {
        const bounds = new maplibregl.LngLatBounds();
        for (const c of cells) bounds.extend([c.lng, c.lat]);
        m.fitBounds(bounds, { padding: 40, maxZoom: 13, duration: 0 });
      }
      setSettled(true);
    };
    apply();
  }, [cells]);

  return (
    <div className="absolute inset-0" data-heat-settled={settled || undefined}>
      <div ref={container} className="h-full w-full" />
    </div>
  );
}
