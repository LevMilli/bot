# Tower-by-tower checklist status (steps 458-745)

Updated Nov 13, 2026. Pretend money only. Rule for this pass: only non-behavior work (logging, counters, cards, tests, docs, dormant shells). Anything that would change how an existing tower buys, sells, sizes or settles is a proposal for Levi. More 15m is frozen.

Key:
- Done: built or written in this pass.
- Splits / Risk room / Freshness: answered by the new Result splits, Risk room or Freshness inspector building.
- Upgrades team (Bx): one of the 22 upgrades being built as a shadow twin by another agent.
- Kept: a rule that already holds in code and has a test; nothing to build.
- Proposal: needs a behavior change; listed for Levi.
- Waits: needs time (50 results, 30 days) or new data before it can be done.

## Sports gap (458-469)
| Step | Status |
|---|---|
| 458 README and inventory match the code | Done: 92¢ cap, 4 buys per check, 3-hour pre-game, 6-point floor; pinned by `test_plan_docs.py` |
| 459 College basketball | Upgrades team (B10) |
| 460 Replay the close-game band | Waits: needs A20 time machine replay |
| 461-462 Polymarket second opinion | Upgrades team (B11) |
| 463-465 Grade hard-stop and 5-minute shadows | Waits: the shadow rows already log; grading needs 30 rows; turning one on is a proposal |
| 466-467 ESPN delay, skip when stale | Proposal (the skip is a behavior change); the delay itself needs ESPN timestamps logged |
| 468 Results by league | Splits (market cut maps KXNFLGAME, KXNBAGAME... to league names) |
| 469 Pause a cold league and show it | The desk learning skip already pauses cold buckets; Splits flags "clearly losing" leagues; auto-pause per league is a proposal |

## Kalshi S&P (470-481)
| Step | Status |
|---|---|
| 470-471 Real fair price, logged 30 days | Upgrades team (B21) |
| 472 80-92¢ band win rate | Calibration lab already measures S&P bands |
| 473 How often the model-flip sale saved money | Splits (exit cut: model flip vs held to result) |
| 474 News calendar covers 2027 | Waits: 2027 dates; check when the calendar is published |
| 475-477 Loss limit, kill switch distance, scan times on the card | Proposal: card text for an existing tower; small but touches the S&P card path |
| 478 Results by scan time | Splits (hour cut: 12:00 and 13:00 CT groups) |
| 479 Never buy the same contract twice | Kept (existing S&P tests) |
| 480 Fills vs tape at each scan time | Waits: needs B19 recordings |
| 481 Do 3 scans help | Waits: 50 results; Splits hour cut is the input |

## BTC 15m (482-493)
| Step | Status |
|---|---|
| 482 Inventory doc to current settings | Done: $35 cushion, 70-92¢, 4¢ spread, 3 contracts, 3 buys; pinned by `test_plan_docs.py` |
| 483-484 Fee once per order, tape check | Upgrades team (B4) |
| 485-486 5-minute time rule twin | Upgrades team (B3) |
| 487 BTC vs ETH | Splits (market cut: KXBTC15M vs KXETH15M) |
| 488 Accurate vs speed lane | Waits: the lane is not stored on each trade; storing it is a logging change inside BTC 15m (proposal) |
| 489-490 Replay take profit and the candle rule | Upgrades team (B5) and A20 |
| 491 News block count | Proposal (needs a counter inside BTC 15m) |
| 492 Grade the edge 0.08 twin | Scorekeeper grades it once it has 50 results |
| 493 Next window status on the card | Freshness inspector shows the next run for every building |

## Commodity 15m (494-505)
| Step | Status |
|---|---|
| 494-496 85¢ twins | Upgrades team (B2) |
| 497-498 Fee once per order, tape check | Upgrades team (B4) |
| 499 Metal vs energy | Splits (market cut per series: gold, silver, WTI...) |
| 500 Pause the weakest series | Splits flags it; the pause is a proposal |
| 501-502 Cushion floors, Pyth basis | Waits: needs A20 replay |
| 503 New commodities | Waits: needs a live source |
| 504 Win rate and average win vs loss | Splits shows both for every group |
| 505 Why a high win rate can lose | Done: `plans/TOWER_PLAIN_WORDS.md`; Splits flags "wins often, loses money" |

## Memecoin (506-517)
| Step | Status |
|---|---|
| 506-507 Second price check | Upgrades team (B15) |
| 508 How often each exit rule fired | Splits (exit cut) |
| 509 Grade each exit rule | Splits (each exit group has its own total and low end) |
| 510-512 RugCheck recheck, rejection counts | Proposal (counters inside the memecoin script) |
| 513-514 Age window, liquidity floor review | Waits: needs logged candidates |
| 515 Red lock at -$5 | Kept |
| 516-517 Price impact, 1% fee check | Waits: monthly check |

## Sized Kalshi (518-529)
| Step | Status |
|---|---|
| 518 Share the S&P fair | Upgrades team (B21) |
| 519 Kelly-lite stake on the card | Proposal (card text) |
| 520-521 Twin-edge rule, anti-double counts | Waits: 50 results |
| 522-523 1 fill a day, $400 kill | Kept (existing sized tests) |
| 524 Weekly compare with Kalshi S&P | Splits and Scorekeeper both list the two side by side |
| 525 Own book and record | Kept (vault card) |
| 526 Band review | Calibration lab |
| 527 Fills vs tape | Waits: B19 |
| 528 Every scan's decision row | Proposal (logging inside the sized script) |
| 529 Does sizing help | Waits: 50 results |

## More 15m (530-541): frozen
| Step | Status |
|---|---|
| 530 Higher bar under 20¢ | Upgrades team (B1) |
| 531 Replay take profit | Upgrades team (B5) |
| 532-533 Held to end vs sold early, re-buys | Splits (exit cut) reads its book without touching it |
| 534, 538-539 Trust cap, buy window, same-direction cap | Waits: A20 replay |
| 535 By market | Splits (market cut: SOL, XRP, DOGE, BNB, HYPE, S&P, EUR/USD, USD/JPY series) |
| 536 Pause a cold market | Proposal (frozen tower) |
| 537 Open offset vs Kalshi's open | Waits: needs Kalshi's open price logged |
| 540 Tape check and fee tests green | Kept |
| 541 Vault promotion | Waits: 50 results and Levi's OK |

## Coinbase spot (542-553)
| Step | Status |
|---|---|
| 542 Maker-fee twin | Upgrades team (B17) |
| 543 Fee schedule check | Waits: monthly |
| 544 Negative-edge skip count | Proposal (counter inside the script) |
| 545-547 z rule, 25% capture, stops | Splits (exit cut) for stops; replay waits on A20 |
| 548 Nov 13 one-off error | Freshness inspector shows "last run failed" if it repeats |
| 549-550 BTC research only, no shorts | Kept |
| 551-552 Round-trip cost and last move on the card | Proposal (card text) |
| 553 Keep or not | Waits: 50 results |

## BTC carry (554-565)
| Step | Status |
|---|---|
| 554-556 Funding per month, round trip, red months | Proposal (card text); the numbers are in its state file |
| 557-559 Archive check, backup source, compare history | Waits: monthly routine; backup source not picked |
| 560 Negative-funding alert | Proposal |
| 561 Leverage 1 | Kept (`btc_carry` tests) |
| 562-563 Legs and total return on the card | Proposal (card text) |
| 564 Plain explanation | Done: `plans/TOWER_PLAIN_WORDS.md` |
| 565 Yearly review | Waits |

## Sports sharp lag (566-577)
| Step | Status |
|---|---|
| 566 Real sharp feed | Blocked: needs an allowed public feed |
| 567-569 Log every lag, how long, skip old | Proposal (inside the script) |
| 570 0.06 floor after fee | Kept |
| 571 Lag size on the card | Proposal |
| 572 Grade | Waits: 50 results |
| 573-574 Compare with Poly lean, avoid double bets | Risk room flags the same game in 2+ towers; blocking it is a proposal |
| 575 Games per league | Splits (market cut) |
| 576-577 Weekly count, retire rule | Waits |

## Fed watch (578-589)
| Step | Status |
|---|---|
| 578-579 Second source, both agree | Upgrades team (B22) |
| 580 Log prices 30 days out | Proposal |
| 581 Next meeting on the card | Proposal (card text) |
| 582 Per meeting | Splits (market cut per series) |
| 583-584 Rule match | Plan written: A25 rule-match checker |
| 585 Daily gap size | What-if lab gap stats |
| 586-587 Max 1 open, idea-bank | Kept |
| 588 Plain explanation | Done |
| 589 Floor trade count | Waits: quarterly |

## Exclusive set (590-601)
| Step | Status |
|---|---|
| 590-599 | Already log-only; extra counters (sets per day, how long, fill check) are logging inside the script: proposal |
| 596 Stay log-only | Kept |
| 600 INX floor kept out | Kept (exclusive-set tests use 0.06 / 0.05) |
| 601 Parlay monitor | Waits: A24 |

## Point spread and Game total (602-613)
| Step | Status |
|---|---|
| 602 Series check | Waits: public API check |
| 603-607 Fair models, 30 days logged, grade | Waits: needs a model; log-only already |
| 608 0.06 floor | Kept |
| 609 No stacking with Sports gap | Risk room flags it |
| 610-611 Game count, best edge on card | Proposal (card text) |
| 612 Retire unlisted series | Waits |
| 613 Plain explanation | Done |

## Weather high (614-625)
| Step | Status |
|---|---|
| 614-615, 624 Lows, more cities, rain and snow | Upgrades team (B7, B8) |
| 616, 623 Per city grade, pause cold city | Splits (market cut per city series); the pause is a proposal |
| 617-619 Forecast vs final, afternoon lock | What-if lab already grades pre-window rows |
| 620 Max 7, one per city-day | Kept |
| 621 Feeds calibration lab | Kept (weather is a calibration family) |
| 622 High so far on the card | Proposal (card text) |
| 625 Station rules | Waits: seasonal |

## Gas weekly (626-637)
| Step | Status |
|---|---|
| 626 Monthly gas | Upgrades team (B9) |
| 627-628 21 days of history | Waits: time |
| 629 Backup AAA reading | Blocked: no second allowed source picked |
| 630 AAA and projection on the card | Proposal (card text) |
| 631 Max 2 | Kept |
| 632-635 Daily fair log, grade, holidays, compare | Research log already holds fair vs ask; grading waits on 50 |
| 636 Plain explanation | Done |
| 637 Floor review | Waits |

## Crypto ladder (638-649)
| Step | Status |
|---|---|
| 638-639 More coins, realized vol | Upgrades team (B6) |
| 640 Grade each coin | Splits (market cut) |
| 641-642, 648 Skips and max 2 | Kept |
| 643 Next print on the card | Freshness inspector shows next run; print time is a proposal |
| 644 No stacking with BTC 15m | Risk room flags Bitcoin in 2+ towers |
| 645 Smile freshness | Waits: needs the smile time logged |
| 646 Grade | Waits |
| 647 By hours before print | Splits hour cut is the closest; hours-to-print needs the print time per trade |
| 649 Plain explanation | Done |

## Nasdaq (650-661)
| Step | Status |
|---|---|
| 650 Hourly book | Plan written: A7 |
| 651 Share the model | Upgrades team (B21) |
| 652-653 Quote age, regular hours | Kept |
| 654 Strikes vs ranges | Splits (market cut: KXNASDAQ100U vs KXNASDAQ100) |
| 655 No stacking with S&P | Risk room shows S&P and Nasdaq groups side by side |
| 656 Level and VXN on the card | Proposal (card text) |
| 657-660 Grade, fills, fee share, cutoff | Waits |
| 661 Plain explanation | Done |

## Poly sports lean (662-673)
| Step | Status |
|---|---|
| 662 Rule match | Plan written: A25 |
| 663-664 Lag duration, stale quotes | What-if lab gap stats; the stale skip is a proposal |
| 665, 670 Liquidity, spread, pre-game | Kept |
| 666 No stacking | Risk room flags the same side of one game |
| 667 By league | Splits |
| 668-673 Counts, card, fills, window, retire | Waits / proposal (card text) |

## Favorite harvest (674-685)
| Step | Status |
|---|---|
| 674, 681 Off until 50, on only with OK | Kept (stays off) |
| 675 More calibration families | Upgrades team (B13) |
| 676 Cells with 50 sides | Calibration lab table already shows n per cell |
| 677-678 Log what it would have bought, grade | Proposal (logging while off) |
| 679-680 Band, Wilson bound | Kept |
| 682 Max 3 | Kept |
| 683-684 Wins often, loses money; average win vs loss | Splits flags it once it trades |
| 685 Plain explanation | Done |

## 10-year Treasury (686-697)
| Step | Status |
|---|---|
| 686 Other tenors | Upgrades team (B18) |
| 687, 694 Basis vs official number | Waits: weekly routine |
| 688-689, 695 Quote age, settle-day only, max 2 | Kept |
| 690 Skip big data days | Proposal |
| 691, 696 Grade, cutoff | Waits |
| 692 Yield and target on the card | Proposal (card text) |
| 693 By time of day | Splits (hour cut) |
| 697 Plain explanation | Done |

## CPI and GDP nowcast (698-709)
| Step | Status |
|---|---|
| 698-699 Nowcast vs final, re-fit | Waits: needs prints |
| 700-701, 707 Pre-release block, trust cap, max open | Kept |
| 702 Each strike group | Splits (market cut: KXCPI, KXCPICORE, KXCPIYOY, KXCPICOREYOY) |
| 703 Nowcast age on the card | Proposal (card text) |
| 704 PCE | Waits: Kalshi listing |
| 705 Jobs prints | Plan written: A2 labor tower |
| 706 Per print | Splits (market cut per series) |
| 708 Merge into one macro book | Waits: one year |
| 709 Plain explanation | Done |

## Soccer & tennis lean (710-721)
| Step | Status |
|---|---|
| 710 Rule match | Plan written: A25 |
| 711, 715, 718 Trust cap, pre-game, max 6 | Kept |
| 712 By league | Splits |
| 713-714 UFC, golf, esports | Upgrades team (B20); esports shell: `plans/PARKED_SHELLS.md` |
| 716, 719-720 Lag, counts, fills | Waits |
| 717 Upcoming matches on the card | Proposal (card text) |
| 721 Plain explanation | Done |

## QQQ momentum (722-733)
| Step | Status |
|---|---|
| 722 SPY and IWM | Upgrades team (B16) |
| 723 Count all three as one bet | Risk room groups QQQ with the Nasdaq 100; the veto is a proposal |
| 724-725, 729 Flat by close, no back-dated fills, costs | Kept (`test_qqq_momentum.py`) |
| 726 Trailing stop | Splits (exit cut) |
| 727 By check time | Splits (hour cut) |
| 728, 731-732 Range, grade, half days | Waits |
| 730 Range and price on the card | Proposal (card text) |
| 733 Plain explanation | Done |

## Research and support buildings (734-745)
| Step | Status |
|---|---|
| 734 Calibration lab 15-minute families | Upgrades team (B13) |
| 735 Volume buckets | Waits: after B13 |
| 736-737 Auditor covers every tower, alerts | Already reads every desk bot's settled Kalshi trades; an alert is the root agent's email lane |
| 738 Scorekeeper 50-results card | Upgrades team (B14) |
| 739 Cautious low end per tower | Kept: scorecard.json has `low` for every bot |
| 740 Exit lab | Upgrades team (B12) |
| 741 Grade rules that blocked a winner | What-if lab already does this for logged rows |
| 742-743 15m every minute, top 5 levels | Upgrades team (B19) |
| 744 Wall Street screens | Waits: front-end |
| 745 Every building's last and next run | Done: Freshness inspector lists last run, next run and status for every building |
