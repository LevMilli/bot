# Picks Bot

A Discord bot that tracks your group's bets: who placed what, what it cost, what it
paid, and who's actually up.

## What it does

| Command | What it does |
| --- | --- |
| `/pick` | Log a pick: platform, one-line description, cost, max payout, optional legs and sport |
| `/result` | Settle a pick as win, loss, push or void (or reopen it). Add `returned` for partial payouts |
| `/open` | Picks still waiting on a result, with total money at risk |
| `/record` | One person's W-L, staked, returned, net and ROI, plus their last 5 results |
| `/leaderboard` | Everyone ranked by net profit |
| `/edit`, `/delete` | Fix or remove a pick |
| `/export` | Download every pick as a CSV that opens in Excel or Google Sheets |
| `/receipts` | Turn slip logging on or off for the channel you run it in (admins only) |

**Receipts channel.** Run `/receipts` once in the channel where people post slips.
After that, any screenshot posted there gets logged under whoever posted it:

- With an Anthropic API key set, the bot reads the screenshot (platform, legs, cost,
  payout, and the result if the slip is already settled) and logs it on its own.
- Without a key, the bot replies with a **Log this slip** button that opens a short form.

Every logged pick gets **Win / Loss / Push** buttons, so settling is one tap.

**Logging for someone else.** `/pick` takes an optional `member` (another person in the
server) or `label` (any name that isn't a Discord account, like a tipster or a model
whose picks you want to grade separately). Labels show up on the leaderboard like
anyone else.

**Who can change a pick.** The bettor, whoever logged it, or anyone with the
Manage Messages permission.

## Setup (about 10 minutes)

### 1. Create the bot in Discord

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open the **Bot** tab. Click **Reset Token** and copy the token. Keep it private.
3. On the same tab, turn on **Message Content Intent** (the bot needs it to see
   screenshots people post).
4. Open **OAuth2 > URL Generator**. Tick the scopes `bot` and `applications.commands`,
   then these bot permissions: View Channels, Send Messages, Embed Links, Attach Files,
   Read Message History.
5. Open the generated URL in your browser and add the bot to your server.

### 2. Run it

You need Python 3.10 or newer.

```
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

- `DISCORD_TOKEN`: the token from step 1.
- `GUILD_ID`: your server's ID, so the slash commands show up right away. (In Discord:
  Settings > Advanced > Developer Mode on, then right-click your server > Copy Server ID.)
- `ANTHROPIC_API_KEY`: optional. Only needed for automatic slip reading.

Then start it:

```
python bot.py
```

### 3. Turn on the receipts channel

In your receipts channel, run `/receipts`. Post a slip to test it.

## Keep it online without your computer

The bot only works while `bot.py` is running, so to have it online all the time it
needs to run on a cloud host instead of your own machine. The included `Dockerfile`
tells the host how to run it. Any host works as long as it gives you two things: a
process that stays on all the time, and a persistent disk for the picks database.

Whichever host you use:

1. Put this folder on the host (most connect to a GitHub repository; keep the repo
   **private**, and never upload your `.env` file).
2. Add `DISCORD_TOKEN`, `GUILD_ID` and (optionally) `ANTHROPIC_API_KEY` as
   environment variables in the host's settings. These replace the `.env` file.
3. Attach a persistent volume mounted at `/data` (1 GB is plenty). The bot keeps
   `picks.db` there. **Without the volume, every redeploy wipes your picks.**
4. Run exactly **one** copy of the bot. Two copies would both answer every slip.

Two hosts that fit:

- **Railway** (railway.com): set up from the website, no command line needed. Create a
  project from your GitHub repo, add the variables, add a volume at `/data`.
- **Fly.io** (fly.io): cheaper, but set up from the command line (`fly launch`, then
  `fly volumes create` and `fly secrets set`).

Run `/export` now and then to keep your own copy of the picks.

## Good to know

- **All data lives in `picks.db`**: next to `bot.py` on your own computer, or in
  `/data` on a cloud host. Back that file up and you've backed up everything.
- **"Max payout" means the total you get back if it wins**, stake included. A $10 entry
  that pays $50 is cost 10, payout 50, net +$40.
- **Slip reading costs a fraction of a cent per screenshot** on the default model, billed
  to your Anthropic account. It can misread a blurry or cropped slip, so glance at what
  it logged; `/edit` fixes anything it got wrong.
- **Partial payouts** (a flex play that pays reduced, or a cash-out): use
  `/result` with the `returned` amount instead of the buttons.
