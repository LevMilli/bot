# PIMP-CITY

Staff neon city for the five paper bots on the PIMP-TRADING desk. Live JSON comes **only** from `paper-bots.pimp_desk.snapshot()` — never re-parsed in the browser.

## How to run (local / dev)

```bash
# 1) Localhost-only snapshot bridge (binds 127.0.0.1)
python3 trading-city/bridge.py
# → http://127.0.0.1:8765/api/pimp-trading.json

# 2) Vite UI (proxies /api/pimp-trading.json → bridge)
cd trading-city
npm install
npm run dev
# → http://127.0.0.1:5173/pimp-city/
```

Optional: `VITE_SNAPSHOT_URL=http://127.0.0.1:8765/api/pimp-trading.json` if not using the Vite proxy.

## How to run (staff bot)

1. Build once: `cd trading-city && npm ci && npm run build`
2. Start the Discord/dashboard bot as usual.
3. Staff opens **PIMP-CITY** next to **PIMP-TRADING** on `/staff`, or go to `/pimp-city/`.
4. The page is staff-session gated (same cookie as the paper desk) and fetches `/api/pimp-trading.json` with credentials.

## Data rules

| Mode | Source |
| --- | --- |
| Live (happy path) | `GET /api/pimp-trading.json` → `pimp_desk.snapshot()` |
| Local bridge | Same function via `trading-city/bridge.py` on localhost |
| Offline fallback | `/pimp-city/fixture-snapshot.json` + clear **Offline demo** banner |

Never invent fills or P&L when live data is present. Tower 5 (`kalshi-sized`) shows the live offline/absent desk row.

Desk ROI rules and per-bot buy/sell/failsafe inventory live in the paper pack: `../paper-bots/DESK_ROI_SYSTEM.md`, `../paper-bots/BUY_SELL_FAILSAFE_INVENTORY.md`. The city surfaces `snapshot.roi_system` + `bot.plans` only — it does not re-parse bot scripts.

## Scripts

| Script | What |
| --- | --- |
| `npm run dev` | Vite + proxy to bridge |
| `npm run build` | Production bundle under `dist/` (served at `/pimp-city/`) |
| `python3 bridge.py` | Read-only localhost snapshot bridge |
