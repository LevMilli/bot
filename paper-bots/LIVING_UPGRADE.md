# Living Trading Upgrade — staff map

Paper only. Venue floors stay locked (sports `0.06` / BTC+commodity `0.05` / INX+DEX `0.02`).  
`LIVE_ORDERS_ENABLED` stays False. Never invent fills. Never silent Φ write.

## Spine

| Piece | Module |
| --- | --- |
| Feature store + completions | `desk_living.py` |
| Living board / chips | `desk_living.living_upgrade_board` |
| Masters rail (max 16, deduped) | `desk_master.finalize_living_priority` |
| Insight digests | `helpers/*_digest.json` via `clerk_pulse` |
| City vault swarm/fills | `trading-city` Desk + vault board |

## Staff CLIs (from `paper-bots/`)

```bash
python3 tools/staff_living_status.py              # compact text
python3 tools/staff_living_status.py selfcheck
python3 tools/staff_living_status.py gaps         # dual-control unsigned
python3 tools/staff_living_status.py ruin         # monthly practice page
python3 tools/staff_living_status.py inventory
python3 tools/staff_living_status.py seed         # empty observe digests
python3 tools/staff_living_status.py export
python3 tools/staff_living_status.py pulse        # force clerk pulse refresh
python3 tools/staff_living_status.py pager        # feature-quiet copy
python3 tools/staff_living_status.py hillclimb

python3 tools/staff_sunday_packet.py draft|discord|checklist
python3 tools/staff_injury_ingest.py show|add|clear
python3 tools/staff_calib_tickets.py
python3 tools/staff_hillclimb_pick.py status|list|pick|clear
python3 tools/staff_dual_control.py status|sign|clear
python3 tools/staff_ruin_drill.py status|set|clear
```

## Hire order

Insight swarm ≥ **3:1** vs betting towers before betting expand.  
Seed missing digests with `staff_living_status.py seed` — observe only.

## Hard rules

- Starve: n≥4, factor 0.15
- Meme red lock −$8; INX halt $460
- Kill: M3↑ with M1↓ for 2 Chicago weeks → revert lever
- Soft promote allowlists stay z\|p — never edge / fee floors
