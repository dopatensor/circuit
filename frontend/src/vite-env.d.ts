/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/react" />

interface ImportMetaEnv {
  /** Backend origin in production (empty = same origin, through the dev/preview proxy). */
  readonly VITE_API_URL?: string;
  /** Vector tile source (TileJSON URL) for the map; defaults to OpenFreeMap. */
  readonly VITE_MAP_TILES?: string;
  /** Font glyphs for map labels. */
  readonly VITE_MAP_GLYPHS?: string;
}
