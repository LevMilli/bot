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
| `/leaderboard` | Everyone ranked by net profit. Filter by `period` (this season, last 7 days, this month, all time) and `sport` |
| `/edit`, `/delete` | Fix or remove a pick |
| `/undo` | Delete the last pick you logged, within 15 minutes |
| `/exposure` | Every open pick grouped by the game it rides on, with money at risk and who's on it |
| `/history` | Page back through picks, filtered by person, status (open, settled, wins, losses, pushes) and sport |
| `/compare` | Two people side by side: record, net, ROI, win rate, streak, best hit, top sport, badges |
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
| `/pings` | Turn on private DMs 30 minutes before a game on one of your open picks starts, and at halftime with the score (one DM per game) |
| `/today` | Today's games with start times, live scores and finals, for the leagues your group bets on or one you pick |
| `/todaypost` | Post today's games in this channel every morning at 10 AM (admins) |
| `/parlay` | Parlay calculator: `-110 +150 -200` (any odds format) gives combined odds, payout and the chance it hits |
| `/season start`, `/season standings`, `/season list` | Seasons: a fresh leaderboard without deleting anything. `/leaderboard` shows the current season; pick another `period` for the rest |
| `/achievements` | 13 badges, from First Blood to Big Leg Energy. `/record` shows the ones you've earned |
| `/card` | A shareable image of someone's profile: avatar, record, net, ROI, streak, best hit, profit line and badges |
| `/limit` | Set a weekly loss limit; the bot DMs you privately once a week if you pass it |
| `/survivor start`, `pick`, `standings` | NFL survivor pool: pick one team to win each week, each team only once. A loss, tie or skipped week knocks you out. Graded automatically from the scoreboard |
| `/remind`, `/reminders` | DM yourself a reminder (`30m`, `2h`, `6pm`, `tomorrow 9am`, up to 30 days out); list or cancel them |
| `/backups` | Post a full backup (database plus Excel) in this channel every night (admins; keep the channel private) |
| `/settings` | Everything set up in this server: channels, features, data size, version (admins, only you see it) |
| `/sweat` | A live tracker for a pick that edits itself every 2 minutes: each leg's stat against its line with a progress bar, or the game score. Posts when a leg clears or dies. Also the 🥵 button on every pick card |
| `/trend` | A player's last 5/10/20 games against a line, with a chart. Buttons switch the window and nudge the line, a menu switches the stat. Free ESPN game logs, preseason left out |
| `/schedule` | When the games on open picks start, grouped by day, with live scores. Mine or everyone's |
| `/kalshi link`, `/kalshi check` | Link a Kalshi pick to its market (paste the Kalshi link or ticker). It settles itself when Kalshi does, and combo legs tick off as each one settles. Also the 🔗 Kalshi button on Kalshi pick cards |
| `/groupparlay` | This week's group parlay: everyone adds one leg with a button, legs grade themselves, and whoever busts it gets roasted. A new one posts every Monday in the recap channel |
| `/copy` | Log your own copy of someone's pick (or tap 📋 Copy on the card). Copies grade along with the original |
| `/wrapped` | Your season, year or all-time in review, story style: tap through the pages, ending with a shareable image |
| `/pick ... hidden:True` | Log a pick that stays secret (🔒) until it settles, then gets revealed with a timestamp |
| DM the bot a slip | Logs it privately as a hidden pick (needs the Claude key) |
| Right-click → Apps → **Log as pick** / **Copy this pick** | Log any slip screenshot or message, or copy the pick on a card |
| `/insights tendencies` `luck` `heatmap` `badbeats` `records` | Your habits (over vs under, stat types, best and worst players, days), luck vs the odds you took, a calendar of up and down days, legs that missed by a hair, and the server's record book |
| `/calc pp` | PrizePicks payouts for every outcome and the hit rate each pick needs. Buttons switch slip size and Power/Flex |
| `/calc hedge` | How much to hedge to lock profit or get your stake back |
| `/money deposit` `withdraw` `summary` `tax` `undo` | Private: money in and out of each app, and a yearly summary with an Excel file |
| `/coins balance` `daily` `top` `give` | PIMP Coins, play money earned by logging and hitting picks, group games, Prop of the Day and hot takes. Daily claims grow with your streak |
| `/market create` `list` | Yes/no markets on anything, bet with coins. The losing side's coins are split among the winners |
| `/take add` `list` | Put a hot take on the record. The bot brings it back on the date to grade, and keeps everyone's record |
| `/potd here` `now` `set` `standings` | Prop of the Day: every morning the bot picks a star playing tonight, sets the line at their recent median, and everyone votes More or Less |
| `/player avg`, `/player vs` | A player's averages (last 5, last 10, all), and how they've done against one team |
| `/dashboard` | Link to the live web dashboard |
| `/sports box` | A player's last game, full stat line |
| `/sports matchup` | A team's next game: records, venue, kickoff weather for outdoor games, back-to-backs, both injury reports, and which side the group's open picks are on |
| `/sports weather`, `/sports injuries` | Kickoff forecast (free Open-Meteo data) and a team's injury report |
| `/sports standings`, `/sports rankings` | Standings with the playoff line (a menu switches conference), and the college AP top 25 with movement |
| `/sports golf`, `ufc`, `f1`, `cs2` | PGA leaderboard, the UFC card, the F1 weekend, and upcoming CS2 matches from Liquipedia |
| `/sports consensus` | Which side the group is on for today's games, from open picks |
| `/player splits`, `/player minutes` | Home/away and win/loss splits, and a minutes chart to spot role changes |
| `/insights autopsy` `risk` `report` `claudia` `rankings` | What kills your parlays, drawdown and stake sizing, a monthly A-F report card image, Claude's picks vs the group, and power rankings (also in the Sunday recap) |
| `/calc kelly`, `/calc slip` | Kelly bet sizing, and how often each leg on a pick has hit lately |
| `/leaderboard rank_by` / `platform` | Rank by units or ROI, or one platform only. ▲▼ show places moved this week |
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
against the free scoreboard and box scores. As soon as a game goes final, moneyline, spread,
total and player-prop legs are graded (an over that's already cleared is marked hit while the
game is still on). Props cover the NBA, WNBA, NFL, college football and basketball, MLB and NHL:
points, rebounds, assists, PRA and the other combos, 3s, steals, blocks, fantasy score, passing,
rushing and receiving yards, receptions, TDs, anytime TD, tackles, hits, runs, RBIs, home runs,
pitcher strikeouts, outs, shots on goal, saves and more. A player who doesn't play is graded a
push. and when that settles the pick, it posts the result in the recap channel. Locks
of the week work the same way.

**Auto-grading.** 48 hours after a pick is logged, any legs still open get looked up and
graded. Moneylines, spreads and game or team totals for the NFL, college football, NBA,
college basketball, WNBA, MLB, NHL and the big soccer leagues are checked for free against
ESPN's public scoreboard (unofficial, so it could change without notice). Player props,
halves, esports, tennis and anything else go to Claude with a web search. The pick is then
settled (win if every leg hit, loss if one missed). The
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

**Injury alerts.** If a player on someone's open prop shows up on ESPN's injury report as Out,
Doubtful, Questionable or Day-To-Day, the bot DMs them once (with a button to turn alerts off).

**Preseason.** Picks on preseason games get a ⚠️ Preseason tag. Admins can leave them off the
leaderboard with the toggle in `/settings`, and `/leaderboard` has a preseason option too.

**Automatic extras.** 🚨 *One leg away* posts when a 3+ leg parlay is down to its last leg. Slips
in the receipts channel get ✅/❌ reactions when they settle (and 🔥 for 5x+). When every leg of a
PrizePicks slip is graded, the bot works out the payout from the standard table (a player who didn't
play drops the slip to a smaller one) and posts a 💵 button to settle it; payouts change, so check your
app. `/today` marks teams on the second night of a back-to-back. Near misses are kept for the bad
beat board and the weekly recap. The leaderboard shows what fading everyone would have made.

**Web dashboard.** In Railway, open the bot's service → **Settings** → **Networking** → **Generate
Domain**. Railway gives the bot a web address and the bot serves a private dashboard there (live
leaderboard, profit chart, open picks, group parlay, coins, record book). Run `/dashboard` for the
link with its key. Anyone with the link can view it, so keep it in the group. Set `DASHBOARD_KEY` to
choose your own key.

**Hot Hand roles** need two things in Discord: the bot's role needs the **Manage Roles**
permission, and it has to sit above the 🔥 Hot Hand and 🧊 Ice Cold roles in Server Settings →
Roles (the bot creates them the first time). They're handed out with the Sunday recap.

**Milestones.** In the recap channel the bot shouts out new badges and 5, 10, 15 and 20-win
streaks. The first time it runs it just notes what everyone already has, so nobody gets a flood.

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

Run `/backups` in a private admin channel and the bot posts a full copy of the database
every night, so even a lost volume costs you at most a day.

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
  `HOF_MIN_PROFIT` (100), `HOF_MIN_MULTIPLE` (5), `TODAY_HOUR` (10, also when Prop of the Day posts),
  `BACKUP_HOUR` (4), `DASHBOARD_KEY` (made up for you if not set).
- **Partial payouts** (a flex play that pays reduced, or a cash-out): use
  `/result` with the `returned` amount instead of the buttons.
