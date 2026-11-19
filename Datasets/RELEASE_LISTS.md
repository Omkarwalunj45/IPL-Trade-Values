# Release lists

Two files, one contract.

| file | what it is | used when |
| --- | --- | --- |
| `release_list_<year>.csv` | the model's **projection** | always present; used when no announced file exists |
| `release_list_<year>_actual.csv` | the franchises' **announced** list | used whenever it is present and parses |

`core.release_list(year)` resolves between them and returns `(DataFrame, source)`
where source is `'announced'` or `'projected'`. Everything downstream — purses,
vacancies, the auction pool, recovery probabilities, retained squads — goes
through it. Dropping the announced file into `Datasets/` is the entire
switch-over. No code changes, and it works unchanged next season.

The projection is never deleted: every season opens with a window in which only
a projection exists.

## Format

Minimum columns are `team` and `player`. `role` and `sal` are used by the
pipeline when present and filled with blanks when not.

```csv
team,player,role,sal
SRH,Liam Livingstone,Allrounder,13.0
CSK,Matt Henry,Bowler,2.0
```

`team` must be the short code (CSK, DC, GT, KKR, LSG, MI, PBKS, RCB, RR, SRH).
Player names run through `names.fix()`, so known alias spellings are fine.

## What happens to a player the projection got wrong

Nothing needs editing by hand. The pre-release squad is `final_pwar.csv`'s
`team` column, which is the squad *before* anyone went. The resolved release
list is subtracted from it, so:

* projected released, actually retained → he is simply not subtracted, and stays
  in the squad and out of the auction pool;
* not projected, actually released → he is subtracted, and enters the pool.

`rosters_2027_scored.csv` is the retained list **under the projection**. It is
no longer read as truth: `trade_eval.rosters()` derives the retained squad as
`(that file + the projected list) − the resolved list`, so it stays correct
either way and there is no second file to keep in step.

A malformed announced file falls back to the projection with a warning rather
than crashing. `core.release_list(strict=True)` raises instead, for a batch run
that must not publish projections as fact.
