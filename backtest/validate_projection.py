"""PLAYER-PROJECTION BACKTEST, frozen at the trade date.

WHAT THIS DOES: for every traded player, computes his WAR from the three seasons
BEFORE the trade, and compares it with the WAR he actually produced in the two
seasons after.  It measures whether the WAR metric anticipates a player's near
future.  No hindsight: war_2024 has never seen a ball bowled in 2024.

WHAT THIS DOES NOT DO: it does not evaluate the TRADE.  It never builds either
club's XII, never prices the deal, never runs evaluate().  A club-level verdict
needs season squads, season salaries, purses and the cash that changed hands --
and the cash amounts are not in any file in this repo.  Until those are sourced,
this answers the smaller question honestly rather than the larger one badly.


Every input is frozen before the trade.  WAR for season Y is built only from
Y-3..Y-1, so war_2024 has never seen a ball bowled in 2024.

Two things vary by season and are passed in rather than hardcoded:

  t_years   how long the buying club holds the player before the next mega
            auction resets every squad.  The live model hardcodes 3 (a mega
            year); a mini-auction signing is only held for the seasons left
            until the next mega, so the option value must be shorter.
            IPL megas: 2022 and 2025.

  is_mega   which entrant-supply distribution the auction recovery should use.
"""
import warnings, os, sys; warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import pandas as pd, numpy as np
import war3
from names import fix

BBB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Datasets', 'ipl_bbb_since_2018.parquet')
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Datasets')
RPW = 82.5
MEGA_YEARS = {2022, 2025}

def t_years(season):
    """Seasons held before the next mega auction wipes the squad."""
    nxt = min([m for m in MEGA_YEARS if m >= season], default=season + 3)
    return max(1, min(3, nxt - season)) if season not in MEGA_YEARS else 3

raw = pd.read_parquet(BBB)
raw = raw[raw.competition == 'IPL'].copy() if 'competition' in raw.columns else raw

def prep(df, yrs, sw):
    d = df.copy().rename(columns={'year': 'season'})
    d = d[d.season.isin(yrs)].copy()
    d['bat'] = fix(d.bat); d['bowl'] = fix(d.bowl)
    for c in ['wide', 'noball', 'byes', 'legbyes']:
        if c not in d.columns: d[c] = 0
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
    d['score'] = pd.to_numeric(d.score, errors='coerce').fillna(0)
    if 'batruns' not in d.columns:
        d['batruns'] = (d.score - d.wide - d.noball - d.byes - d.legbyes).clip(lower=0)
    if 'ballfaced' not in d.columns: d['ballfaced'] = (d.wide == 0).astype(int)
    d['out'] = pd.to_numeric(d['out'], errors='coerce').fillna(0)
    d['ov'] = pd.to_numeric(d.over, errors='coerce').fillna(0).astype(int).clip(0, 19)
    d['w'] = (d.groupby(['p_match', 'inns'])['out'].cumsum() - d['out']).clip(0, 9).astype(int)
    d['sw'] = d.season.map(sw).fillna(1.0)
    d['comp'] = 'IPL'
    for c, v in [('bowl_kind', 'unknown'), ('bat_hand', 'unknown')]:
        if c not in d.columns: d[c] = v
    return d

def vintage(target):
    """Per-season WAR as known before `target`, normalised by weighted balls.

       war_table returns VORP accumulated over three seasons.  Dividing by the
       recency-weighted ball count and re-scaling to one season's exposure puts
       every vintage on the same footing as the live per-season pWAR, so 2021
       and 2024 numbers can be read against each other."""
    yrs = [target - 3, target - 2, target - 1]
    sw = {yrs[0]: 1.0, yrs[1]: 2.0, yrs[2]: 3.0}
    d = prep(raw, yrs, sw)
    n = d.team_bat.nunique()
    t = war3.war_table(war3.raa(d), n, str(target)).rename(columns={'WAR_%d' % target: 'WAR_cum'})
    wb = d.groupby('bat').apply(lambda x: (x.ballfaced * x.sw).sum(), include_groups=False)
    wb2 = d.groupby('bowl').apply(lambda x: (x.ballfaced * x.sw).sum(), include_groups=False)
    t['wballs'] = t.player.map(wb).fillna(0) + t.player.map(wb2).fillna(0)
    t['rate'] = t.VORP / t.wballs.replace(0, np.nan)          # runs above replacement per weighted ball
    t['WAR'] = (t.rate * 300) / RPW                            # one season of exposure, ~300 balls
    t['target'] = target; t['t_years'] = t_years(target)
    t['is_mega'] = target in MEGA_YEARS
    return t

def actual(player, seasons):
    """What he was actually worth afterwards -- the hindsight column."""
    d = prep(raw, seasons, {s: 1.0 for s in seasons})
    if not len(d): return np.nan
    t = war3.war_table(war3.raa(d), d.team_bat.nunique(), 'x').rename(columns={'WAR_x': 'W'})
    r = t[t.player == player]
    return float(r.W.iloc[0]) if len(r) else np.nan

V = {y: vintage(y) for y in (2021, 2022, 2023, 2024)}
for y, t in V.items():
    t.sort_values('WAR', ascending=False).to_csv(os.path.join(DATA, 'war_%d.csv' % y), index=False)
    print('war_%d  t=%d  mega=%-5s players=%d' % (y, t_years(y), y in MEGA_YEARS, len(t)))

tr = pd.read_parquet(os.path.join(DATA, 'ipl_trades.parquet'))
tr.columns = ['season', 'player', 'frm', 'to', 'note']
tr['player'] = tr.player.map(lambda p: fix(pd.Series([p])).iloc[0])
tr = tr[tr.season.isin([2021, 2022, 2023, 2024])]

rows = []
for r in tr.itertuples():
    v = V[r.season].set_index('player')
    known = float(v.loc[r.player, 'WAR']) if r.player in v.index else np.nan
    after = actual(r.player, [r.season, r.season + 1])
    rows.append(dict(season=r.season, player=r.player, frm=r.frm, to=r.to,
                     t_years=t_years(r.season), mega=r.season in MEGA_YEARS,
                     prior_WAR=round(known, 2) if pd.notna(known) else np.nan,
                     subsequent_WAR=round(after, 2) if pd.notna(after) else np.nan,
                     note=r.note))
B = pd.DataFrame(rows)
# deliberately not labelled 'good buy' / 'poor buy': this is the player's own
# projection, not a verdict on the deal his club made
B['prior_tier'] = np.where(B.prior_WAR.isna(), 'no recent IPL record',
                  np.where(B.prior_WAR >= 0.5, 'above replacement',
                  np.where(B.prior_WAR >= 0.0, 'marginal', 'below replacement')))
B.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),'validation_players.csv'), index=False)
print()
print(B[['season', 'player', 'frm', 'to', 't_years', 'prior_WAR', 'subsequent_WAR', 'prior_tier']].to_string(index=False))
ok = B.dropna(subset=['prior_WAR', 'subsequent_WAR'])
if len(ok):
    print('\nrank correlation model vs actual: %.3f  (n=%d)' % (ok.prior_WAR.corr(ok.subsequent_WAR, method='spearman'), len(ok)))
