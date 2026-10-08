# Picks Bot

A Discord bot that tracks your group's bets: who placed what, what it cost, what it
paid, and who's actually up.

## What it does

| Command | What it does |
| --- | --- |
| `/pick` | Log a pick: platform, one-line description, cost, max payout, optional legs and sport |
| `/leg` | Grade one leg of a parlay as hit, miss or push |
| `/grade` | Look up results for a pick's open legs right now |
| `/result` | Settle a pick as win, loss, push or void (or reopen it). Add `returned` for partial payouts |
| `/open` | Picks still waiting on a result, with total money at risk |
| `/record` | One person's W-L, staked, returned, net, ROI and leg hit rate, plus their last 5 results |
| `/leaderboard` | Everyone ranked by net profit |
| `/edit`, `/delete` | Fix or remove a pick |
| `/export` | Download an Excel file: Kalshi, PrizePicks and Other tabs, a Legs tab, and a Summary tab with a section per person (or pick CSV) |
| `/import` | Add picks from an existing tracker spreadsheet (admins only). Running it twice won't duplicate anything |
| `/claim` | Move picks logged under a name (like imported ones) onto someone's Discord account |
| `/receipts` | Turn slip logging on or off for the channel you run it in (admins only) |
| `/recapchannel` | Post the weekly recap and open-pick reminders in this channel (admins only) |
| `/recap` | The last 7 days: who's up, best hit, worst beat, heartbreaker |
| `/player add` `note` `view` `list` `remove` | Scouting notes on players and teams |
| `/help` | Everything the bot can do |
| 👍 Tail / 👎 Fade buttons | On every open pick card. The card shows how many people are tailing or fading |
| `/tailfade` | Who's best to tail or fade, how your own tails and fades went, or one person's record |
| `/challenge` | Challenge someone head-to-head ("Bills beat the Chiefs", optional stakes). They accept or decline; either of you settles it with a button |
| `/h2h` | Your head-to-head challenge record against someone |
| `/lock` | Submit your lock of the week (one per person per week, change it until it's graded) |
| `/locks` | This week's locks and the all-time lock standings |
| `/lockresult` | Settle or fix a lock |
| `/stats` | Your record split by sport, platform and parlay size |
| `/chart` | A graph of profit over time, for everyone or one person |
| `/odds` | Convert -150, +200, 2.5, 45¢, 5/2 or 60% into break-even %, other formats and payout |
| `/awards` | Monthly awards (posts automatically on the 1st) |
| `/hotroles` | Turn on weekly 🔥 Hot Hand / 🧊 Ice Cold roles (admins; needs Manage Roles) |
| `/bankroll` | Set your bankroll; pick cards then show the bet in units and flag bets over 5 units (private) |
| `/pickem start` | Post upcoming games (NFL, ranked college football, NBA, NHL, MLB, Premier League, MLS) with a button per team. Picks lock at kickoff, grade themselves, and the week's winner is announced (mods) |
| `/pickem mine`, `/pickem standings` | Your picks, and this round's table plus all-time standings |
| `/halloffame` | Big wins get reposted in this channel automatically: 3+ leg parlays that hit, 5x+ payouts, or $100+ profit (admins) |
| `/guide` | Post and pin the how-to guide in the current channel (admins) |
| `/limit` | Set a weekly loss limit; the bot DMs you privately once a week if you pass it |
| **@mention the bot** | Ask about a player, team or matchup; it searches the web and answers |

**Receipts channel.** Run `/receipts` once in the channel where people post slips.
After that, any screenshot posted there gets logged under whoever posted it:

- With an Anthropic API key set, the bot reads the screenshot (platform, legs, cost,
  payout, and the result if the slip is already settled) and logs it on its own.
- Without a key, the bot replies with a **Log this slip** button that opens a short form.

Every logged pick gets **Win / Loss / Push** buttons, so settling is one tap.

**Parlay legs.** Legs entered with a pick are numbered on the pick card. Grade each one
with `/leg` as games finish. When every leg hits, the bot marks the pick a win. When a leg
misses, it marks it a loss, except on PrizePicks, where flex entries can still pay, so it
leaves those for you to settle with `/result`. `/record` and the weekly recap show how
often your legs hit.

**Instant grading.** Every couple of minutes the bot checks open picks from the last 5 days
against the free scoreboard. As soon as a game goes final, moneyline, spread and total legs
are graded, and when that settles the pick, it posts the result in the recap channel. Locks
of the week work the same way.

**Auto-grading.** 48 hours after a pick is logged, any legs still open get looked up and
graded. Moneylines, spreads and game or team totals for the NFL, college football, NBA,
college basketball, WNBA, MLB, NHL and the big soccer leagues are checked for free against
ESPN's public scoreboard (unofficial, so it could change without notice). Player props,
halves, esports, tennis and anything else go to Claude with a web search. The pick is then
settled, and the pick is settled (win if every leg hit, loss if one missed). The
bot posts what it found, with the score or stat for each leg, in the recap channel and
tags the bettor. Legs it can't confirm stay open; it tries again every 12 hours, three
times, then asks a person to settle it. PrizePicks entries with a missed leg are left for
you, since flex payouts vary. Early cash-outs aren't visible to the bot, so fix those with
`/result` and the `returned` amount. The free scoreboard needs no key; the Claude lookups need
`ANTHROPIC_API_KEY` and cost roughly a few cents a pick, and only those count toward the daily limit.

**Weekly recap and reminders.** Run `/recapchannel` in the channel you want them in.
Every Sunday at 8 PM (Central) the bot posts the week's standings, best hit, worst beat
and any parlay that missed by one leg. Every day at noon it pings anyone with a pick open
3+ days, once per pick.

**Locks of the week** get graded the same way as picks, 48 hours after they're submitted,
and the results post in the recap channel. The weekly recap shows how the week's locks went.

**Hot Hand roles** need two things in Discord: the bot's role needs the **Manage Roles**
permission, and it has to sit above the 🔥 Hot Hand and 🧊 Ice Cold roles in Server Settings →
Roles (the bot creates them the first time). They're handed out with the Sunday recap.

**Loss-limit DMs** only arrive if the person allows DMs from server members.

**Player tracker.** `/player note` adds a dated note to a player (and adds the player if
they're new). `/player view` shows the notes plus how the group's legs mentioning that
player have gone. The bot also reads these notes when it answers questions.

**Ask the bot.** @mention it (or reply to one of its answers) with a question like
"how has donk played on LAN lately?" It searches the web, uses your player notes, and
replies in the channel. Each person can ask once every 20 seconds, and the server gets 40
questions a day; both limits can be changed (see below).

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
- `ANTHROPIC_API_KEY`: optional. Needed for automatic slip reading and for questions.

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
- **Questions cost more than slips**, roughly a few cents each, because the bot runs up to
  5 web searches and uses a stronger model. The daily limit keeps the total in check.
- **Optional settings** (add as variables on Railway):
  `ASK_DAILY_LIMIT` (default 40), `ASK_COOLDOWN_SECONDS` (20), `ASK_MODEL`
  (`claude-sonnet-5-5`), `TIMEZONE` (`America/Chicago`), `RECAP_DAY` (`sunday`),
  `RECAP_HOUR` (20), `REMIND_HOUR` (12), `REMIND_AFTER_DAYS` (3),
  `AUTOGRADE_AFTER_HOURS` (48; 0 turns auto-grading off), `AUTOGRADE_DAILY_LIMIT` (30),
  `HOF_MIN_PROFIT` (100), `HOF_MIN_MULTIPLE` (5).
- **Partial payouts** (a flex play that pays reduced, or a cash-out): use
  `/result` with the `returned` amount instead of the buttons.
