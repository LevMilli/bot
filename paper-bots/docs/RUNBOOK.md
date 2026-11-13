# Desk runbook

Plain steps for keeping the paper desk healthy. Pretend money only. Real money
stays off, and nothing in this runbook changes how a tower trades.

Last reviewed: 2026-11-13. Review it on the first Friday of each month: walk
each section, remove any step that no longer matches the code, and update the
date (plan step 197).

## The two services

- **Trading service** (`SERVICE_ROLE=trading`): runs `paper-bots/desk_service.py`.
  It holds the paper books on the `/data` volume and runs the 60-second timer.
- **Discord bot**: runs `bot.py`. It serves the staff pages and Apex City and
  asks the trading service for every desk call.

## Is the desk healthy? (one page)

1. Open the trading service's `/healthz`. No key is needed. Healthy looks like:
   - `"ok": true`, `"paper_only": true`, `"timer_alive": true`
   - `"last_pass_age_s"` under 120 (the timer passes every 60 seconds)
   - `"build"` shows the commit and PR number you expect
   - `"kalshi_gateway"`: `cooldown_left_s` is 0 most of the time
   - `"ops"`: disk `used_frac` under 0.80, memory `frac` under 0.80,
     `clock_drift_s` within 2 seconds, `backup_last.ok` true and from last night
2. Open the Discord bot's `/health.json`. `desk.service_ok` should be true and
   `desk.offline` false. `desk.last_pass_at` is the last pass the bot saw.
3. Read the audit channel. Quiet is good. These notes need a look:
   - `Watchdog: ... hit its time limit`, `failed 2 checks in a row`, `has not finished a check`
   - `Desk watch: the desk timer has missed at least 2 passes`
   - `Desk watch: the trading service is not answering`
   - `Ops: ... is slow today`, `the data disk is 80% full`, memory, clock, backup notes
   Every problem posts once and closes with a "healthy again" or "back" note.
   Many notes in one pass arrive as one "Desk health" message.
4. Each morning, the `Ops daily` line says how many timed towers ran yesterday,
   the clean rate, who was not clean, and who never finished a check.
5. Run the checklist from a checkout: `python3 paper-bots/tools/deploy_check.py local`.

## Deploy checklist (steps 134, 141-143)

1. Tests pass: `cd paper-bots && timeout 1200 python3 -m pytest -q -x -p no:cacheprovider`.
2. Build passes: `cd trading-city && npm ci && npm run build` when the city changed.
3. `python3 paper-bots/tools/deploy_check.py local` prints `All checks passed.`
   It checks every tower has its folder, a snapshot lists every tower, the locked
   floors are not lower, real money is off, and the city build and its offline
   fixture are there.
4. After the merge deploys, run the smoke test:
   `python3 paper-bots/tools/deploy_check.py smoke --desk-url <trading service URL> --city-url <bot URL>/health --sha <merge commit>`
5. Watch the audit channel for 10 minutes. `Desk watch: ... different builds`
   means one service did not take the new build.

The trading service logs `Deploy: build <sha> (PR #N): <title>` at startup, and
the bot logs the same line, so each deploy is tagged with its PR in the logs.

## Roll back a bad deploy (steps 136-137)

1. Fastest: in the host dashboard, open the service, pick the last good
   deployment, and press Redeploy. Do it for both services if both changed.
2. Check `/healthz` shows the old build and `last_pass_age_s` is low again.
3. Then make main match: `paper-bots/tools/rollback.sh <PR number>` (or `last`).
   It opens a revert PR and never merges by itself. Review, test, merge.
4. Write an incident note (see "Incidents" below).

## Backups and restore (steps 126-129)

- Every night after 3 AM Central the desk packs the books on the volume
  (`/data/paper-bots`) into `/data/backups/paper-books-<date>.tar.gz`
  (`PAPER_BACKUP_DIR` changes the folder). It reads every JSON file back right
  away, which is the restore test, and keeps the newest 30.
- A failed or skipped backup posts `Ops: the nightly backup did not finish` or
  `skipped the nightly backup` in the audit channel.
- These backups sit on the same volume. A second location (off the volume) is
  not set up yet; it needs a storage bucket and a key from Levi.

To restore:

1. Pause the desk timer (stop the trading service, or pause every tower from the desk).
2. From a Python shell in `paper-bots`:
   ```python
   import desk_ops
   print(desk_ops.list_backups())
   print(desk_ops.restore_backup("/data/backups/paper-books-2026-11-12.tar.gz", "/data/restore-check"))
   ```
   It only unpacks into an empty folder and refuses a backup that does not read back.
3. Compare the restored files with the live ones. Move the live folder aside
   (`mv /data/paper-bots /data/paper-bots-before-restore`), move the restored
   `paper-bots` folder into place, and start the service.
4. Check `/healthz` and the city. Keep the moved-aside folder until the evening
   report matches.

## On call: a tower stopped trading (step 188)

1. Is it paused? Check the tower card or the pause list. Paused towers are skipped on purpose.
2. Is it a shadow tower? Shadow towers trade only when their gates allow, and
   stay hidden until active. That is not an outage.
3. Look for watchdog notes about that tower. A time limit or two failures
   comes with the last line of the error.
4. Open the tower card. The last error is shown in plain words (#707).
5. Check the Kalshi gateway on `/healthz`. A long `cooldown_left_s` or a jump
   in `count_429` means Kalshi is saying "too many requests"; towers skip until it opens.
6. Check the outside source for that tower in `docs/DATA_SOURCES.md`. If the
   source is down, wait; the tower will pick up on its own.
7. If the tower fails on its own code, fix it in a PR. Never loosen a floor,
   cap or gate to make it trade.

## On call: the numbers look wrong (step 189)

1. Do not edit any book by hand first. Take a copy of the tower folder.
2. Compare the tower's trade log with its state file and the vault card.
3. Check the settlement auditor and scorekeeper research rows for that tower.
4. Losses always count. If a total looks too good, look for a missing loss before anything else.
5. If a state file is damaged, restore that one file from last night's backup
   (see "Backups and restore") and note the gap in an incident note.
6. Fix the cause in a PR with a test that would have caught it.

## On call: the city is blank (step 190)

1. Open the bot's `/health.json`. If `desk.offline` is true, the trading
   service is down: follow "Is the desk healthy?" on the trading service.
2. If the trading service is fine, open the browser console on the city page.
   A script error after a deploy means the city build is broken: roll back.
3. Check the city build is in the image: `trading-city/dist/index.html`
   (`deploy_check.py local` checks this).
4. The offline fixture (`trading-city/dist/fixture-snapshot.json`) should show
   when the desk cannot be reached. If even that is blank, it is a front-end bug.

## Incidents (steps 194-196)

- Each incident gets a short note in `paper-bots/docs/incidents/`, named
  `YYYY-MM-DD-short-name.md`, copied from `TEMPLATE.md`.
- Write the time it started, the time someone noticed, and the time it was
  fixed. `python3 paper-bots/tools/incident_stats.py` shows mean time to notice
  and mean time to fix.
- Once a week (Friday, 15 minutes): read the week's audit notes and incident
  notes, pick the top cause, and open one PR or task to fix it.

## Change log (step 191)

`python3 paper-bots/tools/changelog.py --write` refreshes `docs/CHANGELOG.md`
from main. `--days 7` prints what changed this week. Lines marked "rule" touch
floors, caps, sizing, timers, gates or promotions.
