# Promotion checklist

A practice (shadow) tower joins the vault only when every box below is ticked and Levi
says yes. Promotion is never automatic.

## Before asking

- [ ] At least 50 settled results (`desk_safety.practice_status`). Under 50 it does not count.
- [ ] Promotion card filled in (`desk_safety.promotion_card`): results, wins, losses, win rate,
      cautious win rate (Wilson 95% low end), average win, average loss, fees and total P&L.
      Every loss is on the card.
- [ ] The cautious win rate still clears the break-even rate at the tower's typical price.
- [ ] It reuses a locked floor and the floor is not lower after promotion.
- [ ] Settlement auditor shows no mismatch for this tower.
- [ ] README matches the code.
- [ ] A replay or logged result supports the change (no change on a hunch).

## The ask

- [ ] One PR that moves the tower, with the card pasted in the PR body.
- [ ] Levi's written OK on that PR. No OK, no merge.
- [ ] An audit row with who, when and why.
- [ ] A line in `RULE_CHANGES.md`.

## After

- [ ] Its practice losses stay on the lifetime record.
- [ ] Demotion watch: if the last 30 results win less often than the card's cautious rate,
      `desk_safety.demotion_check` flags it and staff decide whether it goes back to practice.
      Losses from the vault period stay on the record too.
- [ ] Retire watch: a practice tower that cannot reach 50 results in about 6 months is
      flagged by `desk_safety.retire_check`. Its data is archived, not deleted.
