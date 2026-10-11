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
| `/receipts` | Slip logging: `mode:` on/off in this channel, every channel, or show where it's on (admins only) |
| `/admin check` | Run it in a channel to see why screenshots aren't being logged there |
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
| `/card` | A trading card: overall rating, rarity border (Common → Rare → Epic → Legendary → Mythic), a title that changes with form, six stats and badges. 🔄 Flip shows the scouting report on the back. `style:Profile banner` gives the old wide card |
| `/board` | Tonight's live board: one image of every open slip with games today, updating as games go. `mode:` auto posts it on game nights |
| `/show` | The Sunday Show: this week's storylines written up like a broadcast (also posts with the weekly recap) |
| `/voice join`, `leave`, `say` | The bot joins your voice channel and calls out cashes, one-leg sweats and big wins |
| `/me roast`, `headsup`, `birthday` | Opt in to roasts of your losses, turn private heads-ups on/off, set a birthday shoutout |
| `/me passes`, `legalerts`, `quiet` | Your ghost-slip pass record, leg-by-leg DMs on/off, hours with no DMs |
| `/scout` | Scouting card image for any player: last 10 games across main stats, injury status, the group's history on him |
| `/poster` | Shareable image: this week's cashed slips, or the standings |
| `/admin personality`, `reactions`, `show` | The bot's voice (sidekick, hype man, analyst, trash talker, announcer), cash replies on/off, Sunday Show on/off |
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
| `/play trivia` | A sports trivia question with A-D buttons. First right answer wins coins (one guess each) |
| `/play guess` | Guess the player from a big stat line. Hints cost coins off the prize |
| `/play closest` | Everyone enters a final-score guess for a game (hidden until kickoff). Closest wins coins |
| `/play squares` | A 10x10 football squares board for a game. Grab a random square or pick one; numbers are drawn at kickoff; pays coins each quarter |
| `/play draft start` `pick` `board` | Snake-draft players (NBA or NFL), tonight only or all week; fantasy points from box scores; winner gets coins |
| `/pool wintotals` `awards` `bracket` `survivor` | Season-long pools: over/under on win totals (scored from live standings), award picks, a playoff bracket (later rounds worth more), and player survivor (one player a day has to hit a number) |
| `/futures add`, `/futures list` | Long-term bets with a reminder when they should be settled |
| `/coins shop`, `/coins level` | Spend coins on a name color, a title on your /card or a brag post. Levels come from coins earned by playing |
| `/me bio`, `/me alerts` | Favorite teams and a tagline (shown on /card), and on/off switches for your DMs (team finals, injury alerts, game pings) |
| `/insights jinx` | Whose tails lose the most |
| 📝 **Note** button on pick cards | Add your reasoning and a 1-5 confidence (or use `confidence` on `/pick`). The recap shows the reasoning behind the week's best hit. `/insights confidence` shows whether your 5-stars beat your 1-stars |
| ⚠️ **Wrong grade?** button | Sends the pick and your reason to the mods (audit channel), with one-tap fix buttons |
| `/me lineup save` `use` `list` `delete` | Save a pick you play often and re-log it in one command |
| `/me goal` | A monthly profit goal with a progress bar on `/record` |
| `/me balance` | Log your app balances now and then and see them on a chart (private) |
| `/me cooloff` | Lock yourself out of logging new picks for 24 hours, 3 days, a week or 30 days. Only an admin (`/admin unlock`) can end it early |
| `/me roles` | Pick the sports you follow to get those roles (needs Manage Roles) |
| `/me mydata` | Download everything the bot has on you as a CSV, with a button to delete it all |
| `/admin status` | Version, uptime, last background run, and whether ESPN, Kalshi, Claude and the dashboard are reachable |
| `/admin audit` | Logs every edit, delete, manual settle and disputed grade in the channel you run it in |
| `/admin announce` | Schedule a message for later in this channel |
| `/admin sheets` | Formulas that pull every pick (or the leaderboard) into Google Sheets live, through the dashboard |
| `/admin welcome` | DM new members a short welcome (see below) |
| `/leaderboard rank_by` / `platform` | Rank by units or ROI, or one platform only. ▲▼ show places moved this week |
| `/me settings` | Every personal switch (roasts, heads-ups, leg alerts, digest, DMs, quiet hours, birthday) in one panel of buttons |
| `/me digest` | A morning DM: your open picks, today's games on them, injury news on your players |
| `/admin panel` | Every server switch plus the bot's personality in one panel (admins) |
| `/hot` | The players the group keeps hitting on, and the ones that keep burning you, as one image |
| `/quests` | This week's skill quests (scout a player, make a good pass, write notes) that pay fun coins. None of them reward betting more |
| **@mention the bot** | Ask about a player, team or matchup; it searches the web and answers |

**New in r18.**

- **🧲 Stack alerts.** When two or more people end up on the same player prop the same way, the bot
  says so once ("Moi and Levi are both on Tatum over PRA").
- **Game-day previews.** About an hour before a game that 2+ people (or 3+ legs) ride on, the recap
  channel gets one card: who's on what, and the injury news.
- **Duplicate guard.** Post the same slip twice and the bot asks before logging it again.
- **Break-even wins.** A slip that wins with no payout entered counts as break-even (not a loss)
  until you add the payout with `/result returned:`.
- **New badges:** 🛡️ Iron Will (3 good passes), 🔮 Sixth Sense (70%+ right on 6+ passes), 🎯 Sniper (8 legs in a row).
- **Dashboard v2.** Overview, Live, Cards and Posters tabs with the same images the bot posts, and it works
  on a phone. Add `?v=1` to the address for the old page.
- **Sturdier background jobs.** If a job fails 5 times in a row, the audit channel hears about it, and
  again when it recovers. `/admin status` shows each job and how many Claude calls ran today.
- **About 40 fixes** from a full read-through: spreads like +150 read as moneylines, re-grading a leg
  re-decides the pick, hidden picks stay hidden on the 🥵 button, live receipts retry a failed edit,
  quiet hours delay the digest instead of skipping it, and more.

**Reading slips for free (r23).** Screenshots are read by a free text scan (Tesseract, installed by the
Dockerfile) first. When it reads every leg, the amount and the payout cleanly, the slip logs without any AI.
When it isn't sure, you get a card showing what it read: tap 🧾 **Log this slip** or ✏️ **Edit**. Optional
second reader: a free Google Gemini key (`GEMINI_API_KEY`, from Google AI Studio, no card needed; on the free
tier Google may use the images to improve its models). Claude is the last resort. `SLIP_READERS` sets the order
(default `scan,gemini,claude`); use `scan,gemini` to never spend Claude credits on slips. Breakdowns and
@mention questions still use Claude. `/admin status` shows which reader handled today's slips.

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

**Social extras.** Mondays post weekly rivals (people who finished next to each other last week;
the winner gets coins). The Sunday recap adds the member of the week and rival results. On the 1st,
last month's top earner gets the 👑 Top Dog role and the awards include a comeback of the month.
The first 20x+ win each month claims the 💰 bounty. 10x+ wins get a banner, 4+ leg parlays lost by
one leg get roasted, and "on this day" posts last year's big hits. Admins can turn game threads on
in `/settings`: when 3+ picks ride on one game the bot opens a thread and posts who cashed at the end.

**Starting lineups and game-day reminders.** With game pings on (`/me alerts`), the bot DMs you at
tip-off whether the players on your NBA props are starting. On Sunday mornings it reminds regulars who
haven't set a lock of the week or a survivor pick (you can turn that off in `/me alerts`).

**Welcome DMs** need one extra switch, because Discord treats member lists as private: in the developer
portal, open your bot's **Bot** tab and turn on **Server Members Intent**, then add the variable
`MEMBERS_INTENT=1` on Railway. Without both, leave welcome DMs off (everything else works without it).

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

**Your own numbers, by asking.** The same @mention answers questions about the group's own records:
"how am I doing on NBA props this month?", "who's best at NFL unders?", "what's Levi's record on
Sundays?" It looks the numbers up in the bot's database (never guesses) and attaches a bar chart
when it compares people or groups.

**Asking about a slip (without logging it).** Post a screenshot with a question, like "@PIMP-BOT what do
you think of this parlay?", "thoughts?", "should I play this?" or "rate my slip", or reply to someone's
screenshot that way. The bot gives a leg-by-leg take (form, matchup, injuries, and the group's own history
on those players), names the weakest leg, and logs nothing. A **🧾 Log this slip** button logs it if you
end up playing it. A screenshot with no words, or with "log", "locked in" and the like, logs as before.
Screenshots of a slip that isn't placed yet (still showing the entry fee box, "Deposit Funds" or "Place
Entry") aren't logged either: the bot offers **🔍 Break it down** or **🧾 Log this slip** instead.

**Slip X-ray.** Every slip breakdown comes with an image: for each player prop, that player's last 10
games as bars with the line drawn across (green beat it, red didn't), plus "8/10 over" and the average.
The same numbers go into the written take. Game lines and players ESPN doesn't log say so instead.

**Ghost slips.** When you ask about your own slip that isn't placed and don't play it, it becomes a 👻
ghost. When its games finish, the bot replies "good pass, it would've missed" or "you passed on this and
it would've hit". `/me passes` shows your pass record (good passes, would've-hits, and the money each way),
and it shows on the back of your `/card`. Logging the slip later, by any route, cancels the ghost.

**Leg-by-leg DMs.** As each leg of your open slips clears ✅ or dies 💀, the bot DMs you, grouped per slip
("1/2 in"). `/me legalerts` turns them off. While the bot is in voice it also calls those out, plus
near-misses on overs ("Brown is at 19. Moi needs 2 more.").

**Quiet hours.** `/me quiet start:23 end:8` stops leg alerts, game pings, team finals, lineup and deadline
DMs between those hours (they're skipped, not saved for later). Reminders you set yourself still arrive.
`/me quiet` with nothing turns it off.

**✏️ Fix on a card.** If a screenshot was misread, tap ✏️ Fix on the pick card to correct the legs, cost,
payout or description in one form. Legs you didn't change keep their grades, and a live receipt redraws itself.
(`/edit` keeps grades on unchanged legs too.)

**Housekeeping.** Once a night, an hour after the backup, the bot clears its own scratch data: slip drafts
older than a week, old question counters, expired ghost slips, and leftover alert and receipt markers.
It never touches picks, legs or money logs. On Sundays it also compacts the database. `/admin status`
shows when it last ran.

**Type a slip instead of screenshotting it.** "@PIMP-BOT log Tatum o22.5 PRA, Brown o20.5 pts, $10 to win
$30 on PrizePicks" turns into a confirm card with **🧾 Log this slip**, **✏️ Edit** and **🔍 Break it down**.
Nothing is logged until you tap Log; if the amounts are missing, Log opens the edit form first. Typed legs
with a question ("@PIMP-BOT thoughts on Tatum o22.5 PRA + Brown o20.5?") get the breakdown and X-ray instead.
Ordinary questions that happen to contain numbers ("who covers -3.5 tonight?", "what's my record with -110
favorites?") still go to the normal Q&A.

**"How's my slip doing?"** @mention the bot with that (or "how are my parlays looking") and it replies with
live receipt images of your newest open slips. Questions about your record ("how are my picks doing this
season?") still get a stats answer.

**`/scout <player>`.** A scouting card: the player's last 10 games across their main stats as bars against a line
near their average (or one stat and line you choose), plus injury status, their last game, and how each person
in the group has done on legs with that player.

**Posters.** `/poster` makes a shareable image: this week's cashed slips as a collage, or the standings (season,
this week, or last 30 days) with avatars and ▲▼ movement. Both post automatically with the Sunday Show.

**Help menu and job health.** `/help` opens with a short "start here" and a dropdown to jump to any section.
`/admin status` lists any background job that keeps failing, and the audit channel gets one alert when a job
fails 5 times in a row (and another when it recovers).

**Live receipts.** When a slip screenshot is logged, the bot's reply includes a clean image of the
slip. As games go, the image fills in: progress bars on props, scores on game lines, ✓ and ✗ as legs
finish, and a CASHED or MISSED stamp at the end.

**Heads-up from your own history.** When you log a pick, the bot privately tells you if your own
history says something about it, like "You've hit 2 of 10 Rebounds overs (20%)" or "You've gone
14-5 on NFL picks". Only you see it (an ephemeral message for `/pick`, a DM for screenshots).
`/me headsup` turns it off.

**Reactions and roasts.** When a pick cashes, the bot replies to its card with a line in the
server's voice (written fresh by Claude when the key is set). Losses stay quiet unless that person
opts in with `/me roast`. 10x wins get the big-win banner instead.

**Milestones.** Besides badges and streaks, the recap channel gets: pick #100/250/500/1000, new
personal-best wins, trading card upgrades ("Levi's card just upgraded to EPIC"), pickiversaries
(a year since your first pick) and birthdays set with `/me birthday`.

**Voice.** `/voice join` from inside a voice channel. The bot speaks cashes, one-leg-away sweats, big
wins, new slips and the Sunday Show headline, and leaves on its own 5 minutes after the channel empties.
The bot's role needs **Connect** and **Speak** in that channel. Voice uses the included Dockerfile
(it installs ffmpeg and the audio libraries) and the packages in requirements.txt; `/voice join`
says exactly what's missing if anything is.

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

In your receipts channel, run `/receipts` (pick **On in this channel**). Post a slip to test it.

**Screenshot posted but nothing happened?** Run `/admin check` in that channel. It tells you:
- whether logging is on there (running `/receipts` with no option flips it, so running it twice turns it off)
- which permissions the bot is missing there (it needs View Channel, Send Messages, Read Message History, Embed Links)
- whether the Claude key is set, and the last error when reading a slip failed
- which version is live (check it says r13.1 or later)

Other ways to log a screenshot: @mention the bot in the same message as the picture, reply to a
screenshot with `@PIMP-BOT log`, right-click the message → Apps → **Log as pick**, or `/receipts mode:Every channel`
to catch slips anywhere (pictures that aren't slips are skipped quietly). Editing an old message
doesn't count as a new post, so repost the picture.

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
  `BACKUP_HOUR` (4), `DASHBOARD_KEY` (made up for you if not set),
  `GEMINI_API_KEY` (optional free slip reader), `GEMINI_MODEL` (`gemini-flash-latest`), `SLIP_READERS`
  (`scan,gemini,claude`), `DIGEST_HOUR` (9, when the morning digest DMs go out), `CLAUDE_DAILY_CAP` (off by default; a number
  caps the day's Claude calls, and the extras like fresh roast lines and the Sunday Show go back to
  templates once it's hit, while slip reading keeps working).
- **Partial payouts** (a flex play that pays reduced, or a cash-out): use
  `/result` with the `returned` amount instead of the buttons.
