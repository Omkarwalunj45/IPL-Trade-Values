# Name canonicalisation fix

## What was wrong

Player names were spelled differently across datasets. Ball-by-ball data used one
form (`Phil Salt`), the auction file the fuller registered name (`Philip Salt`),
the salary file a third (`Rasikh Dar`). Merges on the raw string dropped those
players silently rather than failing, so they disappeared from the model without
any error being raised.

Three separate failures were happening:

1. **`core.py` had no alias map at all.** `price_model()` and `price_model2()`
   merged auction data against `final_pwar.csv` on a bare `.str.strip()`, so
   every mis-spelled player fell out of the price regression sample.
2. **17 active players were absent from `final_pwar.csv` entirely** — including
   Phil Salt (RCB, Rs 11.5cr) and Rasikh Salam (RCB, Rs 6cr). RCB's optimised XII
   was being built without their first-choice keeper-opener.
3. **Mechanical string damage** that `.str.strip()` cannot see: a doubled internal
   space in `Jasprit  Bumrah`, non-breaking spaces splitting `Raj Bawa` into two
   separate players in `war_final.parquet`, and a mojibake apostrophe in
   `Will O'Rourke`.

## What changed

### New file: `src/names.py`

Single source of truth. Exports `_canon()` (repairs encoding and whitespace),
`ALIAS` (46 verified spelling variants), `one()` and `fix()`.

The `ALIAS` dict previously existed in five separate copies with different
contents, which is how the drift started. All five now import from here.

Names that merely look similar are deliberately excluded: Avinash Singh is not
Akash Singh, Tom Curran is not Sam Curran, Harpreet Brar is not Harpreet Singh,
Matthew Forde is not Matthew Wade, Shiva Singh is not Shivam Singh, Yash Dabas is
not Yash Dayal, Virat Singh is not Sanvir Singh, Divesh Sharma is not Jitesh
Sharma, Mohammed Kaif is not Mohammed Shami, Tejasvi Singh is not Ravi Singh.
Each of those pairs appears simultaneously in the 2026 auction file, which is the
evidence that they are separate registrations.

### Source files

| File | Change |
| --- | --- |
| `src/names.py` | new |
| `src/core.py` | added the missing import; `players()`, `price_model()`, `price_model2()` now canonicalise |
| `src/war3.py`, `src/pipeline.py`, `src/trade_eval.py`, `src/ipl_trade_optimizer.py`, `src/price.py` | local `ALIAS` dict replaced by the shared import; `.str.strip().replace(ALIAS)` upgraded to `fix()` |
| `src/price2.py` | imports `fix` |
| `src/engine.py` | release list now canonicalised |

### Datasets

Canonicalisation applied in place to every name column. `rosters_2027_scored.csv`
had nine players appearing twice (a `squad_2026` row carrying role and salary, and
a `replacement` row carrying the rates); those pairs are now merged into one row
holding both halves, taking it from 216 rows to 207.

## The 17 added rows — read this before quoting them

`final_pwar.csv` goes from 318 to 335 rows. The 17 added players are flagged with
`war_final` in the `source` column (`IPL (war_final)` where recent exposure clears
100 balls, `thin (war_final)` below it) so one grep finds them all.

The label matters: `app.py` filters the Player Rankings tab on `source` containing
"IPL", so a marker without "IPL" in it would have silently hidden these players
from the rankings even though the rows existed.

**Their `pWAR_final` is on a different basis from the other 318 rows.** The script
that generates `final_pwar.csv` is not in this repo, and its projection could not
be reproduced from `war_final.parquet` (best calibration achieved R2 = 0.47,
residual sd ~1.0 WAR — too noisy to publish). Rather than fabricate a number, these
rows take the value straight from `war_final.parquet`: the sum of seasonal WAR
across 2024-2026.

Columns that **were** reproduced exactly, and match the existing rows' definitions:

- `ipl_balls_wtd` = sum of (bf + bb) weighted 3/2/1 for 2026/2025/2024
- `balls_recent` = sum of (bf + bb) weighted 2/1 for 2026/2025
- `ipl_balls_faced`, `ipl_balls_bowled` = 2024-2026 totals

Salt lands at rank 34 of the 209-player rankings view, between Tim David and Josh Inglis, which is a
plausible place for an Rs 11.5cr keeper-opener. The other 16 are marginal players
between +0.5 and -0.8. **Regenerate these 17 from the original notebook when you
can** and drop the `war_final` marker from `source`.

## Effect on the price model

The regression sample grows from 197 to 208 lots. Coefficients move:

| Term | Before | After |
| --- | --- | --- |
| intercept | -1.41 | -0.88 |
| pWAR | 1.26 | 1.16 |
| scarcity | 2.46 | 1.90 |
| flexibility | 0.23 | 0.25 |
| capped | 4.51 | 4.10 |
| overseas | -1.44 | -1.36 |

If you have quoted the old coefficients anywhere, they need updating.

`Datasets/price_model.json` **has** been regenerated, using `price2.fit()`, which
is in the repo. The refit moved it very little — the largest change is the `proj`
term (0.554 to 0.590 in the contested-probability model, 1.387 to 1.439 in the
multiple model); every other coefficient moved by under 1%, and the residual sd
and contest rate are unchanged. So this was never a material problem.

## Verification run

- All 16 modules import
- `engine.boot()` completes in ~13s
- `core.players()` returns 335 rows; Salt and Rasikh present
- `price_model()` n=208, `price_model2()` n=208
- Full trade evaluation runs (RCB XII 28.54 -> 26.65 if Salt is traded out)
- `streamlit run app.py` serves HTTP 200; `AppTest` reports 0 exceptions
- No duplicate players, no NaN in `pWAR_final` or `salary`
- No encoding or whitespace damage remaining in any name column
- Every alias target exists in the canonical data; every alias key is mapped
- No auction-2026 player with IPL ball-by-ball data is missing from `final_pwar.csv`

## Final coverage audit

Every one of these passes on the shipped build:

| Check | Result |
| --- | --- |
| 2027 roster players missing from `final_pwar.csv` | 0 |
| 2027 release-list players missing | 0 |
| 2027 auction-pool players missing | 0 |
| 2026 auction entries missing | 0 |
| Active players with 2024-26 IPL balls missing | 0 |
| Alias targets that do not exist in canonical data | 0 |
| Alias keys still unmapped in any dataset | 0 |
| Duplicate players | 0 |
| NaN in `pWAR_final` / `salary` / `role` | 0 |
| Encoding or whitespace damage in any name column | none |
| `AppTest` exceptions | 0 |

`RS Hangargekar` was found on a second pass and added: the auction file carries him
under that form for 2024-26 and as `Rajvardhan Hangargekar` for 2023, never in the
same year, so they are one player. The first fuzzy pass missed it because
initial-form names do not match on string similarity. A dedicated surname-plus-
initials scan found only this one genuine case; the rest were first-initial
coincidences among common surnames (Aaqib Khan is not Avesh Khan, Nahid Rana is
not Nitish Rana, Upendra Yadav is not Umesh Yadav).
