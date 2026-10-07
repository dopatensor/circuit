// Phase 0 placeholder. The real shell (Tailwind, generated API client, persona
// switcher) arrives in Phase 8.
export default function App() {
  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        maxWidth: 640,
        margin: "0 auto",
        padding: "48px 16px",
        lineHeight: 1.5,
      }}
    >
      <h1 style={{ margin: 0 }}>Circuit</h1>
      <p>Match on what you need and what you can offer.</p>
      <p style={{ color: "#64748b" }}>
        Scaffold is running. Backend status: <a href="/health/deps">/health/deps</a>
      </p>
    </main>
  );
}
