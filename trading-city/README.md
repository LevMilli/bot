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
| `npm test` | Look-rule tests (closed towers black, practice towers hidden, totals include losses) |
| `python test_city_headers.py` | CSP / framing regression for the city shell |

## City page files

Keep the front end small and easy to edit:

| File | What it holds |
| --- | --- |
| `src/data/cityRules.ts` | Every look rule in plain functions: roof color, lit windows, tower height cap, banner numbers, stale stamp, quiet hours, CSV |
| `src/data/format.ts` | Who stands in the city (`towerInCity`) and who is closed (`towerClosed`) |
| `src/hud/CityBanner.tsx` | Banner: real money off, desk today, lifetime, stop left, open of 12, risk of $100, clock, data age, legend, guide |
| `src/hud/TowerRail.tsx` | Tower list, search box, plain-words card per tower, hidden lot |
| `src/scene/Tower.tsx` | The 3D towers (black when closed, roof by today's result) |
| `public/guide.html` | Plain user guide, linked from the banner |

The card numbers come from `paper-bots/city_card.py` (read only; it never changes a tower).
`/apex-city/health` answers `{"ok": true}` when the page is built.
