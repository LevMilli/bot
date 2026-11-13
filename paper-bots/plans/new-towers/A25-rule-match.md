# A25. Rule-match checker

## What
For every Kalshi and Polymarket pair the lean towers use (Fed watch, Poly sports lean, Soccer & tennis lean), checks that both sides settle on the same source, the same deadline and the same definition (overtime, extra time, retirements, postponements).

## How often
Once when a pair is first seen, then once a day while it is open.

## Output
`rule_match.json`: each pair as match, mismatch or needs a person, with the two rule lines side by side.

## Edge and floor
None. Log-only. Using it as a "skip on mismatch" gate in a tower is a behavior change, so it goes to Levi as a proposal after 2 weeks of rows.

## Steps
1. Read the Kalshi market rules and the Polymarket market text for each pair already in the lean towers' research logs.
2. Match on a short list of fields: settle source, deadline, overtime or extra-time rule, retirement or walkover rule.
3. Anything not clearly matched is "needs a person", never "match".

## Risks
Rule text is messy; some pairs will always need a person.
