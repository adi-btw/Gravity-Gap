# Gravity Gap web app

Next.js 15 (App Router) + React 19 + TypeScript + Tailwind v4. All phase-1 physics runs in the browser
(`lib/physics.ts`, a port of `engine/physics.py`), so the regime and pressure × gravity views work without the API.

## Install

```bash
cd web
npm install
```

## Develop

```bash
npm run dev        # http://localhost:3000
```

## Test, lint, build

```bash
npm test           # vitest: physics parity against ../tests/fixtures/physics_reference.json + inline R1-R5
npm run lint       # eslint (next/core-web-vitals + next/typescript)
npm run build      # production build (static pages)
npm start          # serve the production build
```

The parity test reads the shared fixture written by the TL. If it is missing, the fixture suite is skipped with a
message and the inline reference cases still run. A second test checks that `lib/presets.ts` matches
`engine/presets.py`.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend base URL (`uvicorn api.main:app --port 8000`) |

## Layout

- `app/` pages: `/` landing, `/regime` (F2 regime calculator + F3 pressure × gravity, `?tab=pressure`),
  `/explore`, `/bounds`, `/ledger`, `/planner`, `/data` (phase-2 placeholders), `/about`.
- `components/HabitatBar.tsx` (F0): presets and editable g, P, O₂, vent, L. State lives in the URL
  (`?g=<m/s²>&p=<psia>&o2=<fraction>&u=<cm/s>&L=<mm>`) so every link is shareable.
- `components/charts/` hand-rolled SVG charts (no Plotly dependency yet).
- `lib/physics.ts`, `lib/presets.ts` mirror the Python engine; `lib/habitat.ts` parses and serializes URL state.
- Design tokens are CSS variables in `app/globals.css`: dark default, `data-theme="light"` for light.
