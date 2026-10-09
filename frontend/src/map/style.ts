// A quiet map style built from free OpenStreetMap vector tiles (OpenFreeMap, no key
// needed), in the app's light or dark theme. Only what helps you find your way: water,
// parks, roads and place names. If the tiles can't load (offline, blocked network) the
// map still works: a plain background with the pins on top.
import type { StyleSpecification } from "maplibre-gl";

const TILES = import.meta.env.VITE_MAP_TILES ?? "https://tiles.openfreemap.org/planet";
const GLYPHS =
  import.meta.env.VITE_MAP_GLYPHS ?? "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

export const ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> ' +
  '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">© OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

const PALETTES = {
  light: { bg: "#efece6", park: "#e2e8d8", water: "#d3e1e8", minor: "#ffffff", major: "#dcd6cb", text: "#6e6a63", halo: "#efece6" },
  dark: { bg: "#151513", park: "#18201a", water: "#111a20", minor: "#262623", major: "#34342f", text: "#948f85", halo: "#151513" },
};

/** True when the page is showing the dark theme (system setting or the person's choice). */
export function isDarkTheme() {
  const t = document.documentElement.dataset.theme;
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function mapStyle(): StyleSpecification {
  const c = PALETTES[isDarkTheme() ? "dark" : "light"];
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {
      osm: { type: "vector", url: TILES, attribution: ATTRIBUTION },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": c.bg } },
      {
        id: "park",
        type: "fill",
        source: "osm",
        "source-layer": "park",
        paint: { "fill-color": c.park },
      },
      {
        id: "water",
        type: "fill",
        source: "osm",
        "source-layer": "water",
        paint: { "fill-color": c.water },
      },
      {
        id: "roads-minor",
        type: "line",
        source: "osm",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["minor", "service", "tertiary"]]],
        paint: { "line-color": c.minor, "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 16, 3] },
      },
      {
        id: "roads-major",
        type: "line",
        source: "osm",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["primary", "secondary", "trunk", "motorway"]]],
        paint: { "line-color": c.major, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.8, 16, 5] },
      },
      {
        id: "places",
        type: "symbol",
        source: "osm",
        "source-layer": "place",
        filter: ["in", ["get", "class"], ["literal", ["suburb", "neighbourhood", "quarter", "city", "town"]]],
        layout: {
          "text-field": ["coalesce", ["get", "name:en"], ["get", "name"]],
          "text-font": ["Noto Sans Regular"],
          "text-size": 12,
        },
        paint: { "text-color": c.text, "text-halo-color": c.halo, "text-halo-width": 1.2 },
      },
    ],
  };
}
