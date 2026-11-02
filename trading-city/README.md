# APEX-CITY

Interactive neon trading city for the five paper bots on the PIMP desk.
Vite + React Three Fiber SPA, served staff-side at `/apex-city/`.

## Local

```bash
cd trading-city
npm ci
# optional: python bridge.py   # serves /api/pimp-trading.json on :8765
npm run dev
# → http://127.0.0.1:5173/apex-city/
```

## Production

1. `npm ci && npm run build` → `trading-city/dist`
2. Host serves that folder from `bot.py` at `/apex-city/` (legacy `/signal-city/` and `/pimp-city/` still alias the same bundle).
3. Staff opens **APEX-CITY** next to **PIMP-TRADING** on `/staff`, or go to `/apex-city/`.

Live trades still come from staff-gated `/api/pimp-trading.json` (`pimp_desk.snapshot()`).

| Mode | Source |
| --- | --- |
| Live | `/api/pimp-trading.json` |
| Offline fallback | `/apex-city/fixture-snapshot.json` + clear **Offline demo** banner |

Desk ROI rules and per-bot buy/sell/failsafe inventory live in the paper pack: `../paper-bots/DESK_ROI_SYSTEM.md`, `../paper-bots/BUY_SELL_FAILSAFE_INVENTORY.md`. The city surfaces `snapshot.roi_system` + `bot.plans` only — it does not re-parse bot scripts.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server |
| `npm run build` | Production bundle under `dist/` (served at `/apex-city/`) |
| `npm run preview` | Preview the production build |
| `python test_city_headers.py` | CSP / framing regression for the city shell |
