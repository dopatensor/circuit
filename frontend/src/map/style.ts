// A pure-black map style built from free OpenStreetMap vector tiles (OpenFreeMap, no
// key needed). Only what helps you find your way: water, parks, roads and place names.
// If the tiles can't load (offline, blocked network) the map still works: black
// background, pins on top.
import type { StyleSpecification } from "maplibre-gl";

const TILES = import.meta.env.VITE_MAP_TILES ?? "https://tiles.openfreemap.org/planet";
const GLYPHS =
  import.meta.env.VITE_MAP_GLYPHS ?? "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

export const ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> ' +
  '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">© OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

export function darkStyle(): StyleSpecification {
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {
      osm: { type: "vector", url: TILES, attribution: ATTRIBUTION },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#000000" } },
      {
        id: "park",
        type: "fill",
        source: "osm",
        "source-layer": "park",
        paint: { "fill-color": "#06140c" },
      },
      {
        id: "water",
        type: "fill",
        source: "osm",
        "source-layer": "water",
        paint: { "fill-color": "#07101f" },
      },
      {
        id: "roads-minor",
        type: "line",
        source: "osm",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["minor", "service", "tertiary"]]],
        paint: { "line-color": "#16181d", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 16, 3] },
      },
      {
        id: "roads-major",
        type: "line",
        source: "osm",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["primary", "secondary", "trunk", "motorway"]]],
        paint: { "line-color": "#262a33", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.8, 16, 5] },
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
        paint: { "text-color": "#6b7280", "text-halo-color": "#000000", "text-halo-width": 1.2 },
      },
    ],
  };
}
