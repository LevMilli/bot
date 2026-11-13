# A2. Labor tower

## What
Kalshi weekly initial jobless claims (KXJOBLESSCLAIMS), continuing claims and the monthly unemployment rate.

## How often
Every 30 minutes. Never in the last 2 hours before the print (same block as CPI and GDP).

## Fair price
A trend from the last 8 weeks of Labor Department numbers plus seasonal factors, with a spread fitted to past misses around consensus. Re-fit each quarter.

## Edge and floor
Econ floor 0.05 after fee; edges over 0.15 are logged only (trust cap). $25 ticket, max 2 open.

## Steps
1. Log fair vs price for every strike for 2 weeks (about 2 claims prints).
2. Grade logged rows in the what-if lab.
3. Practice book only if positive after fees; 50 results and Levi's OK.
4. The CPI and GDP nowcasts can reuse this model for jobs prints (step 705).

## Risks
Holiday and storm weeks miss badly. Pros watch it closely.
