# SIGNAL-CITY

Interactive neon trading city for the five paper bots on the PIMP desk.
Vite + React Three Fiber SPA, served staff-side at `/signal-city/`.

## Local

```bash
cd trading-city
npm ci
# optional: python bridge.py   # serves /api/pimp-trading.json on :8765
npm run dev
# → http://127.0.0.1:5173/signal-city/
```

## Production

1. `npm ci && npm run build` → `trading-city/dist`
2. Host serves that folder from `bot.py` at `/signal-city/` (legacy `/pimp-city/` still aliases the same bundle).
3. Staff opens **SIGNAL-CITY** next to **PIMP-TRADING** on `/staff`, or go to `/signal-city/`.

Live trades still come from staff-gated `/api/pimp-trading.json` (`pimp_desk.snapshot()`).

| Mode | Source |
| --- | --- |
| Live | `/api/pimp-trading.json` |
| Offline fallback | `/signal-city/fixture-snapshot.json` + clear **Offline demo** banner |

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server |
| `npm run build` | Production bundle under `dist/` (served at `/signal-city/`) |
| `npm run preview` | Preview the production build |
| `python test_city_headers.py` | CSP / framing regression for the city shell |
