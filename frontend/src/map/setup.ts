// MapLibre draws tiles and GeoJSON (the dashboard's heat layer) in a web worker. By
// default it looks for the worker file next to its own code, but the build bundles
// that code into a hashed chunk, so the file isn't there. Vite's "?url" import copies
// the worker into the build and gives us its address.
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl };
