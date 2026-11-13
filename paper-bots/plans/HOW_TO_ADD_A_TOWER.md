# How to add a tower (one page, step 997)

Pretend money only. A new tower never touches an existing tower.

1. Write a one-page plan in `plans/new-towers/`: what it trades, how often, the fair price, the edge, and which locked floor it reuses. Floors never go lower than: sports 0.06, BTC 15m 0.05, commodity 15m 0.05, S&P (INX) 0.02, Solana DEX 0.02, Coinbase spot 0.05, BTC carry 0.02, econ 0.05, QQQ 0.02.
2. Make the folder `<id>-paper/` with `bot.py`, `config.json` (`paper_only: true`, `live_orders: false`, `shadow_only: true`), `README.md` and `.gitignore`. `python tools/new_tower.py scaffold <id>` makes a starting folder.
3. Add one row to `new_towers.py`. Copy a row of the same kind:
   - Trading tower: `kind` (weather, econ, crypto, index, sports, macro), `every_sec`, `max_open`, `venue` and `floor`. It gets the $25 ticket and $500 sleeve automatically.
   - Research building (never trades): `research: True`, `kind: "research"`, `max_open: 0`, and `keep` for any file that must survive a deploy.
4. `pimp_desk._install_new_towers` does the rest: timer slot, account file, plans, ROI waivers, starter cash, settlement files.
5. Tests: add `test_<id>.py`. At least: it never buys over its floor, it never invents a price, and `tools/new_tower.py check <id>` is ok.
6. Run the whole suite. It must stay green.
7. Start log-only. A practice book only after 2 weeks of positive logged rows. 50 settled results before it counts. Promotion needs Levi's OK.

City look: shadow towers stay hidden until they trade. Research buildings stand only if they are on the landmark list in `trading-city/src/data/format.ts`.
