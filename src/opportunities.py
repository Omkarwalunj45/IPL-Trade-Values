import os as _os, sys as _sys
_DATA = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'Datasets')
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""
TEAM OPPORTUNITIES  --  stage 1

Where is a squad weak, before anybody has been released?

Nothing here is a new model.  Every number is read out of machinery that already
exists: the XII comes from the same MILP the trade simulator uses, par comes from
bench_bat.csv, and the fill probabilities come from the same no-trade auction that
engine.boot() has already run.  This module is an assembly layer, so a hole shown
here and a hole shown after a trade are measured identically.

The one judgement it adds is ordering.  A gap is ranked by gap_value, which is the
shortfall multiplied by the slot's weight -- and that weight is exposure times
importance (ipl_trade_optimizer.BAT_W).  Being 0.4 WAR short at the top of the
order is a bigger problem than being 0.4 short at seven, because the opener faces
roughly three times the balls.  Ranking on raw gap would get that backwards.
"""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from names import one

# batting slot -> par group.  Slots 8-12 carry no batting requirement: 8 is a
# bowling allrounder and 9-12 are bowlers, so they are judged on bowling alone.
GRP = {1: 'Opener', 2: 'Opener', 3: 'No3', 4: 'Middle', 5: 'Middle',
       6: 'Lower', 7: 'Lower'}

# how far below par before a slot is called a hole rather than noise.  0.15 WAR is
# roughly 12 runs across a season -- below that the projection cannot tell the
# difference between a weak player and an unlucky one.
HOLE_TOL = 0.15

_SEASON = 2026

_TEAM_MAP = {"Chennai Super Kings": "CSK", "Delhi Capitals": "DC", "Gujarat Titans": "GT",
             "Kolkata Knight Riders": "KKR", "Lucknow Super Giants": "LSG",
             "Mumbai Indians": "MI", "Punjab Kings": "PBKS", "Rajasthan Royals": "RR",
             "Royal Challengers Bengaluru": "RCB", "Sunrisers Hyderabad": "SRH"}

_BBB = {}



def _pool(C, seed=7):
    """The 2027 auction pool: everyone on a release list, everyone unsold, plus a
       draw of new entrants.  Rebuilt exactly as engine._auction builds it so the
       pool depth quoted here matches the pool the fill probabilities came from."""
    from entrants import draw_entrants
    PA = C['PA']
    rel = {n for v in C['REL'].values() for n in v}
    pool = PA[PA.player.isin(rel) | (PA.auctionStatus == 'unsold')].copy()
    pool = pd.concat([pool, draw_entrants(np.random.default_rng(seed), C['par'])],
                     ignore_index=True)
    return pool


def _depth(pool, slot, par, purse, pm2):
    """How much cover the auction actually offers for one slot."""
    from core import market_fair2
    cand = pool[(pool.bat_group == slot) | (pool.bat_group.isna())]
    if not len(cand):
        return dict(pool_n=0, pool_at_par=0, pool_affordable=0, best_available=np.nan)
    price = cand.apply(lambda r: market_fair2(r, pm2), axis=1)
    at_par = cand.pWAR >= par
    return dict(pool_n=int(len(cand)),
                pool_at_par=int(at_par.sum()),
                pool_affordable=int(((price <= max(purse, 0)) & at_par).sum()),
                best_available=round(float(cand.pWAR.max()), 2))


def last_match(team, year=_SEASON):
    """The p_match id of the last game this franchise played that season."""
    d = _ball(year)
    m = d[(d.tb == team) | (d.tw == team)]
    return int(m.p_match.max()) if len(m) else None


def _importance(slot=None, phases=None):
    """Importance of a position, with exposure deliberately stripped out.

       BAT_W multiplies importance by exposure, which is right when you are asking
       what a slot contributes over a season.  It is wrong when you are asking which
       hole to fix first: exposure would always push you towards the top of the order
       simply because openers face more balls.  What matters here is how much a win
       depends on that position per ball."""
    from ipl_trade_optimizer import _IMP_BAT, _PHASE_IMP
    if slot is not None:
        return float(_IMP_BAT.get(int(slot), 1.0))
    if phases:
        tot = sum(phases.values()) or 1.0
        return float(sum(_PHASE_IMP[p] * w for p, w in phases.items()) / tot)
    return 1.0


def recent_matches(team, n=5, year=_SEASON):
    """The last n games this franchise played that season."""
    d = _ball(year)
    m = d[(d.tb == team) | (d.tw == team)]
    return sorted(m.p_match.unique())[-n:] if len(m) else []


N_RECENT = 5


_POS = {}


def positions(team, C=None, year=_SEASON, use_json=True, n_recent=N_RECENT):
    """The side this club has actually been putting out, built slot by slot.

       One match is too thin a base.  A game where four men batted and seven bowled
       reads as a side with bowlers at five, six and seven, which is not the squad --
       it is the scorecard of one chase.  Looking across the last five games instead
       shows who genuinely occupies each position, and fills all twelve places.

       Slots 1-8 go to batters, taken from the men who actually batted in that group
       across those games.  Slots 9-12 go to bowlers by the phase each covers.

       `Datasets/playing_xii_2026.json` is checked first.  If the team has an entry
       there, that XII is used exactly as written instead of being re-derived, so a
       name typed in by hand takes effect on the next load.  Only when the team is
       missing from the file (or the file itself is missing) does this fall back to
       deriving the side from the last `n_recent` games."""
    import engine
    C = C or engine.boot()
    ov = _xii_override(team) if use_json else None
    if ov is not None:
        gone = retired()
        war = dict(zip(C['PA'].player, C['PA'].pWAR))
        par_bat = dict(zip(C['bb'].bat_group, C['bb'].par_pWAR))
        use = phase_usage(year); ph_raw = use.set_index('player')
        pw = C['PA'].set_index('player')
        rows = []
        for e in ov.get('xii', []):
            p = e.get('player', '')
            if p not in pw.index:
                p2 = one(p)
                p = p2 if p2 in pw.index else p
            if p not in pw.index or p in gone:
                continue
            grp, unit = e.get('group'), e.get('judged_on')
            w = war.get(p, np.nan)
            if unit == 'Batting':
                par, basis = par_bat.get(grp, np.nan), grp
                imp = _importance(slot=e.get('slot'))
            else:
                par, basis = bowl_par(p, C, use)
                imp = _importance(phases=_ph_dict(ph_raw, p))
            rows.append(_prow(e.get('slot'), grp, unit, basis, p, w, par, imp, pw))
        out = pd.DataFrame(rows)
        if len(out):
            out['note'] = ''
            out.attrs['p_match'] = ov.get('p_match')
            out.attrs['matches'] = n_recent
            return out, 'ok (from playing_xii_2026.json)'
        # every name in the file failed to match a known player -- fall through
        # to the derived side rather than returning an empty XII
    mids = recent_matches(team, n_recent, year)
    if not mids:
        return pd.DataFrame(), 'no match found'
    d = _ball(year)
    g = d[d.p_match.isin(mids)]

    # who batted where, across those games
    bat = g[g.tb == team]
    first = bat.groupby(['p_match', 'bat'], as_index=False).ball_id.min()
    first['pos'] = first.groupby('p_match').ball_id.rank(method='first').astype(int)
    first['player'] = first.bat.map(one)
    first['grp'] = np.where(first.pos <= 2, 'Opener',
                   np.where(first.pos == 3, 'No3',
                   np.where(first.pos <= 5, 'Middle', 'Lower')))
    cnt = first.groupby(['player', 'grp'], as_index=False).p_match.nunique()
    cnt.columns = ['player', 'grp', 'n']

    bg = bowl_groups(year)
    bg = bg[bg.team == team]
    bg['player'] = bg.player.map(one)
    bowled_recent = {one(p) for p in g[g.tw == team].bowl.dropna().unique()}
    bg = bg[bg.player.isin(bowled_recent)]

    squad = set(C['squads'][team]); gone = retired()
    war = dict(zip(C['PA'].player, C['PA'].pWAR))
    cnt = cnt[~cnt.player.isin(gone)]
    bg = bg[~bg.player.isin(gone)]
    cnt['w'] = cnt.player.map(war).fillna(0.0)
    bg['w'] = bg.player.map(war).fillna(0.0)

    par_bat = dict(zip(C['bb'].bat_group, C['bb'].par_pWAR))
    use = phase_usage(year); ph_raw = use.set_index('player')
    pw = C['PA'].set_index('player')
    meta_all = pw

    used, rows, notes = set(), [], {}
    PLAN = [(1, 'Opener'), (2, 'Opener'), (3, 'No3'), (4, 'Middle'), (5, 'Middle'),
            (6, 'Lower'), (7, 'Lower'), (8, 'Lower')]
    for slot, grp in PLAN:
        c = cnt[(cnt.grp == grp) & (~cnt.player.isin(used))]
        c = c.sort_values(['n', 'w'], ascending=[False, False])
        if not len(c):
            # nobody batted there in those games: take the best man at the club in
            # that group who is not already in the side
            pool = [p for p in squad if p not in used and p not in gone
                    and p in meta_all.index and str(meta_all.loc[p, 'bat_group']) == grp]
            if not pool:
                continue
            p = max(pool, key=lambda x: float(meta_all.loc[x, 'pWAR'] or 0))
            notes[p] = 'did not bat here in the last %d' % n_recent
        else:
            p = c.player.iloc[0]
        used.add(p)
        rows.append(_prow(slot, grp, 'Batting', grp, p, war.get(p, np.nan),
                          par_bat.get(grp, np.nan), _importance(slot=slot), pw))
    for slot, want in [(9, 'Powerplay'), (10, 'Middle'), (11, 'Death'), (12, 'any')]:
        c = bg[~bg.player.isin(used)]
        pick = c[c.phase == want] if want != 'any' else c
        if not len(pick):
            pick = c
            if len(pick):
                notes[pick.sort_values('w', ascending=False).player.iloc[0]] = \
                    'no %s specialist' % want.lower()
        if not len(pick):
            continue
        p = pick.sort_values(['w', 'balls'], ascending=[False, False]).player.iloc[0]
        used.add(p)
        par, basis = bowl_par(p, C, use)
        rows.append(_prow(slot, 'Bowler', 'Bowling', basis, p, war.get(p, np.nan), par,
                          _importance(phases=_ph_dict(ph_raw, p)), pw))
    out = pd.DataFrame(rows)
    if len(out):
        out['note'] = out.player.map(notes).fillna('')
    out.attrs['p_match'] = mids[-1]
    out.attrs['matches'] = len(mids)
    _POS[key] = (out, 'ok')
    return _POS[key]


def _ph_dict(ph_raw, p):
    if p not in ph_raw.index:
        return None
    r = ph_raw.loc[p]
    return {k: float(r[k]) for k in ('Powerplay', 'Middle', 'Death')}


def _prow(i, grp, unit, basis, p, w, par, imp, pw, batted=True):
    gap = (par - w) if (pd.notna(par) and pd.notna(w)) else np.nan
    m = pw.loc[p] if p in pw.index else None
    return dict(bat_slot=i, group=grp, judged_on=unit, basis=basis, player=p,
                pWAR=round(float(w), 2) if pd.notna(w) else np.nan,
                par=round(float(par), 2) if pd.notna(par) else np.nan,
                gap=round(float(gap), 2) if pd.notna(gap) else np.nan,
                importance=round(float(imp), 2),
                gap_value=round(float(gap * imp), 2) if pd.notna(gap) else np.nan,
                batted=batted,
                overseas=int(m.overseas) if m is not None and pd.notna(m.overseas) else 0,
                wk=bool(m.role == 'WK-Batter') if m is not None else False,
                status=('\u2014' if pd.isna(par) else 'Hole' if gap > HOLE_TOL
                        else 'Thin' if gap > 0 else 'Above par'))


_HOLES = {}


def holes(team, top=None, C=None):
    """The jobs worth fixing in the side that last took the field, ranked on
       shortfall x importance."""
    import engine
    C = C or engine.boot()
    if (team, top) in _HOLES:
        return _HOLES[(team, top)]
    pos, _ = positions(team, C)
    if not len(pos):
        return pd.DataFrame()
    v = pos[pos.gap > HOLE_TOL].copy()
    if not len(v):
        return pd.DataFrame()
    v = v.sort_values('gap_value', ascending=False).groupby(
        ['judged_on', 'group'], as_index=False).first()
    v = v.sort_values('gap_value', ascending=False)
    if top: v = v.head(top)
    auc = C['auc0']; a = auc[auc.team == team].set_index('role')
    purse = float(C['p0'].loc[team, 'purse']); pool = _pool(C)
    out = []
    for r in v.itertuples():
        bat = r.judged_on == 'Batting'
        d = (_depth(pool, r.group, r.par, purse, C['pm2']) if bat
             else _depth_bowl(pool, r.basis, r.par, purse, C['pm2']))
        hit = a.loc[r.group] if (bat and r.group in a.index) else None
        out.append(dict(slot=r.group, unit=r.judged_on, basis=r.basis, occupant=r.player,
                        pWAR=r.pWAR, par=r.par, gap=r.gap, weight=r.importance,
                        gap_value=r.gap_value,
                        p_fill=round(float(hit.p_fill), 2) if hit is not None else np.nan,
                        p_at_par=round(float(hit.p_at_par), 2) if hit is not None else np.nan,
                        recovery=round(float(hit.recovery_WAR), 3) if hit is not None else np.nan,
                        **d))
    _HOLES[(team, top)] = pd.DataFrame(out)
    return _HOLES[(team, top)]


def _depth_bowl(pool, basis, par, purse, pm2):
    """Cover available for a bowling hole: bowlers in the pool who clear the par,
       and can be paid for."""
    from core import market_fair2
    cand = pool[pool.bowl_phase.notna() | (pool.role == 'Bowler')]
    if not len(cand):
        return dict(pool_n=0, pool_at_par=0, pool_affordable=0, best_available=np.nan)
    price = cand.apply(lambda r: market_fair2(r, pm2), axis=1)
    at_par = cand.pWAR >= par
    return dict(pool_n=int(len(cand)), pool_at_par=int(at_par.sum()),
                pool_affordable=int(((price <= max(purse, 0)) & at_par).sum()),
                best_available=round(float(cand.pWAR.max()), 2))


def summary(team, C=None):
    """Squad-level context: what the XII is worth now, what the auction is expected
       to add, and the constraints the club is working inside."""
    import engine
    C = C or engine.boot()
    xii, val, vac, msg = C['base'][team]
    pos, _ = positions(team, C)
    n_hole = int((pos.status == 'Hole').sum()) if len(pos) else 0
    return dict(team=team,
                xii_value=round(float(val), 2),
                recovery=round(float(C['rec0'][team]), 2),
                xii_after_auction=round(float(C['v0'][team]), 2),
                purse=round(float(C['p0'].loc[team, 'purse']), 2),
                slots=int(C['p0'].loc[team, 'slots']),
                releases=int(C['p0'].loc[team, 'n_rel']),
                squad_n=int(len(C['squads'][team])),
                overseas_in_xii=int(pos.overseas.sum()) if len(pos) else 0,
                keepers_in_xii=int(pos.wk.sum()) if len(pos) else 0,
                holes=n_hole,
                p_top4=round(float(C['S0'].loc[team, 'p_top4']), 1),
                p_title=round(float(C['S0'].loc[team, 'p_title']), 1))


def report(team, top=3, C=None, B=None):
    """Everything the Team Opportunities tab needs, in one call."""
    import engine
    C = C or B or engine.boot()
    pos, msg = positions(team, C)
    return dict(summary=summary(team, C), positions=pos, holes=holes(team, top, C), msg=msg)


# =====================================================================
#  STAGE 2  --  candidate search
# =====================================================================
"""Which players on the other nine squads would actually fix this hole, and is
   the trade route cheaper than the auction route?

   Two-stage by necessity.  The screen re-solves the XII MILP for every plausible
   candidate on both sides of the deal -- ~30ms each, so a few seconds for a whole
   sweep.  The full evaluation runs the auction and the season and costs ~6s a
   deal, so it is spent only on the handful the screen has already ranked.

   The screen is deliberately two-sided.  A player who would improve the buyer is
   not a trade; a player who would improve the buyer AND whom the seller can afford
   to lose is a trade.  Ranking on the buyer's gain alone produces a wish list."""

# What a selling club will actually part with.
#
# The first version of this search proposed taking Bumrah for a below-par seamer,
# because it ranked on what the BUYER gained and never asked whether the deal was
# one anybody would agree to.  Nobody trades their best player to patch someone
# else's weakness.
#
# But requiring the man to be pure surplus is too strong the other way: no club has a
# spare opener worth having, so that filter returned nothing at all.  What makes a
# real trade work is the RETURN -- a player surplus to you filling a hole of theirs.
# So the cap here only rules out franchise players (nobody parts with a 3-WAR pillar
# whatever comes back), and the seller is then held to a NET test once the return is
# counted, which is where the deal is actually judged.
SELLER_MAX_LOSS = 2.50

# And after the return is included, the seller has to finish close to level.  They
# may finish AHEAD -- a player who is surplus to you can be exactly what they are
# missing, which is the whole reason trades exist -- but they will not accept a
# meaningful net loss.
SELLER_NET_TOL = -0.60

# The buyer's gain also has to be believable next to theirs.  A deal where one side
# gains 4 and the other 0.05 is not a trade, it is a gift, and it will be refused.
MAX_ASYMMETRY = 3.0

MAX_DONOR_LOSS = SELLER_MAX_LOSS

# Salary as a proxy for standing.
#
# The model saw Hardik Pandya as 1.10 pWAR after two lean seasons and happily sent
# him out for an uncapped batter.  No club does that: he is a twice World Cup winning
# allrounder who does two jobs, and the market knows it even when recent WAR does not.
# His 2026 salary does -- Rs 16.35cr against Rs 0.30cr -- so the fee is used as the
# star proxy the projection cannot supply.  The two sides of a swap must be within
# this ratio of each other by salary.
SAL_RATIO = 0.40

# Three rules that salary alone does not enforce.
#
# 1. You do not trade a better player for a worse one.  The search proposed Ashutosh
#    Sharma (1.83) for Tilak Varma (2.02) -- giving up more than you get back, which
#    no club does whatever the surrounding arithmetic says.
#
# 2. You do not send an India international out for an uncapped player.  Tilak Varma
#    is capped and a World Cup winner; Shashank Singh is not.  The fee gap was inside
#    the salary band, so only the capped flag catches it.
#
# 3. The man who loses his place must do the same job as the man arriving.  Signing a
#    lower-order batter and dropping Mayank Markande, a spinner, is not fixing a
#    batting hole -- it is quietly weakening the attack to pay for it.
PROTECT_CAPPED = True

# ---------------------------------------------------------------- star premium
#
# Salary is a decent proxy for standing but a lagging one, and pWAR is worse: after
# two lean seasons Hardik Pandya reads as 1.10, so the search happily sent him out
# for an uncapped batter.  Clubs do not behave that way.  A man who bats, bowls,
# fields and can captain carries a premium the recent numbers cannot see.
#
# The 2025 mega auction retention list is the cleanest available marker of that.
# Retention there cost real money at the one moment every squad was rebuilt from
# scratch, so it records who each franchise judged untouchable: 46 retained plus 8
# RTM, two to six per club.  The 2026 list is useless for this -- it was a mini
# auction and 163 players were held.
#
# A retained man's trade value is marked up by STAR_PREMIUM.  He is not untradeable;
# he simply costs more to prise loose, which is why he tends to come back as two
# players or one player plus cash rather than a like-for-like swap.
STAR_PREMIUM = 0.12

# Some men are simply not for sale at any price the model can express.  A franchise
# icon is not a valuation problem, he is a fixed point: Mumbai do not trade Rohit or
# Bumrah, Chennai do not trade Dhoni, and no arithmetic should be allowed to suggest
# otherwise.  These are excluded from both sides of every proposal.
UNTRADEABLE = {
    'Virat Kohli', 'Jasprit Bumrah', 'Shubman Gill', 'Suryakumar Yadav',
    'Rohit Sharma', 'Sunil Narine', 'MS Dhoni',
}

# Across a whole package the star-adjusted value going out may exceed what comes in
# by this much and no more.  It stops two useful players being bundled up for one
# name that only looks bigger.
PKG_TOL = 0.15

# ...and a floor underneath it.  The ceiling above stops you giving up more than you
# get; on its own it happily let the reverse through -- Will Jacks leaving for a
# fringe seamer, because Jacks was blocked at his club so the XII arithmetic said
# nobody lost anything.  A player who cannot get a game still has a market value, and
# no club gives him away.  The package going back must be worth at least this share
# of the man arriving.
RETURN_FLOOR = 0.60

_RETAINED = None


def retained_2025():
    """Players retained (or bought back via RTM) at the 2025 mega auction."""
    global _RETAINED
    if _RETAINED is None:
        a = pd.read_parquet(_os.path.join(_DATA, 'ipl_auction_data_23_26.parquet'))
        a = a[(a.year == 2025) & (a.auctionStatus.isin(['retained', 'rtm']))]
        _RETAINED = {one(p) for p in a.playerName.dropna()}
    return _RETAINED


def star_value(player, pwar):
    """What a club prices him at, rather than what last season says he is worth."""
    if pwar is None or not np.isfinite(pwar):
        return 0.0
    return float(pwar) * (1.0 + STAR_PREMIUM if player in retained_2025() else 1.0)

# below this the improvement is inside the projection's own noise, and dividing a
# rounding error by a base-price salary produces a spectacular and meaningless
# value-per-crore.  Rank on impact first, efficiency second.
MIN_GAIN = 0.15


def _slot_pwar(xii, slot, unit='Batting'):
    """The weakest pWAR currently doing that job -- that is what defines the hole,
       so that is what has to improve for the hole to be closed.

       For a batting hole the job is a batting group.  For a bowling hole it is
       'holds a bowling slot at all', because the MILP is free to re-assign which
       bowler covers which phase."""
    if xii is None or not len(xii):
        return np.nan
    if unit == 'Bowling':
        g = xii[xii.bowl_slot.notna()]
    else:
        g = xii[xii.bat_slot.map(lambda s: GRP.get(int(s))) == slot]
    return float(g.pWAR.min()) if len(g) else np.nan


def _fixes_hole(xii_after, slot, before, unit='Batting'):
    """Did the hole actually close?

       Not the same as 'did the signing bat in that slot'.  The MILP reorders the
       whole side, so buying a top-order batter can fix a middle-order hole by
       pushing an incumbent down into it.  That is a real fix and rejecting it
       because the new man batted at three would throw away the best deals."""
    a = _slot_pwar(xii_after, slot, unit)
    return bool(pd.notna(a) and pd.notna(before) and a > before + 0.01)


def screen(team, slot, C=None, max_candidates=None, unit='Batting'):
    """Cheap sweep: every plausible candidate on the other nine squads, scored on
       what he adds to the buyer, what he costs the seller, and what he costs in
       money against what the auction would charge for him."""
    import engine
    from trade import vacancies
    from core import market_fair2
    C = C or engine.boot()
    PW, PA, pm2 = C['PW'], C['PA'], C['pm2']
    base_buy = C['base'][team][1]
    purse = float(C['p0'].loc[team, 'purse'])
    slots_free = int(C['p0'].loc[team, 'slots'])
    pos, _ = positions(team, C)
    inc = pos[(pos.group == slot) & (pos.judged_on == unit)]
    inc = inc.sort_values('gap', ascending=False)
    occ = str(inc.player.iloc[0]) if len(inc) else ''
    par = float(inc.par.min()) if len(inc) else np.nan
    inc_pwar = float(inc.pWAR.min()) if len(inc) else 0.0
    before = _slot_pwar(C['base'][team][0], slot, unit)

    known = set(C['PA'].player)
    cand = PW[(PW.team != team) & (PW.player.isin(known))
              & (~PW.player.astype(str).str.startswith('Replacement'))].copy()
    # a player cannot fix a batting hole he is worse than, and a specialist bowler
    # cannot fix one at all -- both filters are about candidacy, not quality
    # a batting hole needs someone who bats, a bowling hole someone who bowls
    share = cand.share_bowl if unit == 'Bowling' else cand.share_bat
    cand = cand[(cand.pWAR > inc_pwar) & (share > 0.25)]

    meta = C['PA'].set_index('player')
    if unit == 'Batting':
        # An opener is not fixed by a middle-order batter.  Rutherford and Wadhera bat
        # four and five; putting them at the top is a different player in a different
        # job, so the candidate's own batting group has to match the hole.
        ok = [p for p in cand.player
              if p in meta.index and str(meta.loc[p, 'bat_group']) == slot]
    else:
        # A spinner's slot is not filled by a seamer.  Match the type first, then
        # require the man actually bowls the phase the hole is in.
        want_kind = str(inc.basis.iloc[0]) if len(inc) else ''
        kind = str(meta.loc[occ, 'bowl_kind']) if occ in meta.index else 'nan'
        want_ph = _dominant_phase(occ, C)
        ok = []
        for p in cand.player:
            if p not in meta.index:
                continue
            if str(meta.loc[p, 'bowl_kind']) != kind:
                continue
            ph = str(meta.loc[p, 'bowl_phase'] or '')
            if want_ph and want_ph not in ph:
                continue
            ok.append(p)
    cand = cand[cand.player.isin(ok) & (~cand.player.isin(UNTRADEABLE))]
    if max_candidates:
        cand = cand.nlargest(max_candidates, 'pWAR')

    _px = PA.set_index('player')
    prices = {n: float(market_fair2(_px.loc[n], pm2)) for n in _px.index}
    out = []
    for c in cand.itertuples():
        xii_b, val_b, _, _ = vacancies(PW, team, C['bb'], C['bw'], add=(c.player,))
        if xii_b is None or not np.isfinite(val_b):
            continue
        d_buy = val_b - base_buy
        if d_buy <= 0:
            continue
        _, val_s, _, _ = vacancies(PW, c.team, C['bb'], C['bw'], drop=(c.player,))
        d_sell = (val_s - C['base'][c.team][1]) if np.isfinite(val_s) else np.nan
        # he must be surplus at his own club, or this is not a trade anybody makes
        if not (pd.notna(d_sell) and d_sell > -SELLER_MAX_LOSS):
            continue
        sal = float(c.salary) if pd.notna(c.salary) else 0.30
        mkt = prices.get(c.player, np.nan)
        out.append(dict(
            player=c.player, from_team=c.team, role=str(c.role),
            pWAR=round(float(c.pWAR), 2), overseas=int(c.overseas), wk=bool(c.is_wk),
            salary=round(sal, 2), market=round(mkt, 2) if pd.notna(mkt) else np.nan,
            saving=round(mkt - sal, 2) if pd.notna(mkt) else np.nan,
            d_buy=round(float(d_buy), 3),
            d_sell=round(float(d_sell), 3) if pd.notna(d_sell) else np.nan,
            per_cr=round(float(d_buy) / max(sal, 0.30), 3),
            fixes_hole=_fixes_hole(xii_b, slot, before, unit),
            affordable=bool(sal <= purse and slots_free >= 1),
            beats_par=bool(pd.notna(par) and c.pWAR >= par)))
    d = pd.DataFrame(out)
    if not len(d):
        return d
    d = d[d.d_buy >= MIN_GAIN].copy()
    if not len(d):
        return d
    # A deal the buyer cannot afford is dead.  A deal that does not close the hole is
    # off-topic.  A deal the seller would refuse for nothing is neither -- it is a
    # real deal that needs something going back, so it is labelled, not deleted.
    d['viable'] = d.affordable & d.fixes_hole
    d['tier'] = np.where(~d.affordable, 'Cannot afford',
                np.where(~d.fixes_hole, 'Does not close it', 'Available'))
    order = {'Available': 0, 'Does not close it': 1, 'Cannot afford': 2}
    d['_o'] = d.tier.map(order)
    return d.sort_values(['_o', 'd_buy', 'per_cr'],
                         ascending=[True, False, False]).drop(columns='_o').reset_index(drop=True)


def why(r, slot, occupant):
    """One line explaining the row, built from its own numbers rather than a template
       with adjectives in it."""
    bits = [f"Slots straight in at {str(slot).lower()}, {r.d_buy:+.2f} on the best XII over {occupant}."]
    if pd.notna(r.saving):
        if r.saving > 0.5:
            bits.append(f"He costs \u20b9{r.salary:.2f}cr in salary against \u20b9{r.market:.2f}cr "
                        f"to buy the same player at auction \u2014 \u20b9{r.saving:.2f}cr cheaper by trade.")
        elif r.saving < -0.5:
            bits.append(f"But \u20b9{r.salary:.2f}cr is \u20b9{abs(r.saving):.2f}cr above his "
                        f"\u20b9{r.market:.2f}cr auction value, so you are overpaying for the certainty.")
        else:
            bits.append(f"At \u20b9{r.salary:.2f}cr he is priced about where the auction would "
                        f"put him, so the gain is the player, not the discount.")
    if pd.notna(r.d_sell):
        if r.d_sell < -MAX_DONOR_LOSS:
            bits.append(f"{r.from_team} lose {abs(r.d_sell):.2f} off their own XII, so this only "
                        f"happens with a player or cash going back.")
        elif r.d_sell < -0.01:
            bits.append(f"{r.from_team} give up {abs(r.d_sell):.2f}, which is inside the range "
                        f"a squad absorbs.")
        else:
            bits.append(f"{r.from_team} lose nothing measurable by letting him go.")
    if r.overseas:
        bits.append("Overseas, so he takes one of the four slots.")
    return " ".join(bits)


def opportunities_for(team, slot=None, top=5, C=None, full=False, max_candidates=None):
    """The tab's entry point.  Screens every candidate for the named hole (or the
       worst hole if none is named), then optionally runs the full auction-and-season
       evaluation on the ones that survived."""
    import engine
    C = C or engine.boot()
    H = holes(team, top=None, C=C)
    if not len(H):
        return dict(team=team, slot=None, occupant=None, table=pd.DataFrame(), hole=None)
    row = H[H.slot == slot].iloc[0] if (slot and (H.slot == slot).any()) else H.iloc[0]
    slot = row.slot
    d = screen(team, slot, C, max_candidates=max_candidates, unit=row.unit)
    if len(d):
        d = d[d.viable].head(top).copy() if d.viable.any() else d.head(top).copy()
        d['why'] = [why(r, slot, row.occupant) for r in d.itertuples()]
        if full and len(d):
            import engine as E
            res = []
            for r in d.itertuples():
                e = E.evaluate(team, r.from_team, [r.player], [], {r.player: r.salary})
                a = next(x for x in e['rows'] if x['team'] == team)
                b = next(x for x in e['rows'] if x['team'] == r.from_team)
                res.append(dict(util_buy=a['util'], util_sell=b['util'],
                                title_buy=a['title_yes'] - a['title_no'],
                                title_sell=b['title_yes'] - b['title_no'],
                                mutual=bool(a['util'] > 0 and b['util'] > 0)))
            for k in res[0]:
                d[k] = [x[k] for x in res]
    return dict(team=team, slot=slot, occupant=row.occupant, par=row.par,
                gap=row.gap, table=d, hole=row.to_dict())


def find_return(buyer, seller, need, max_loss, in_salary=1.0, C=None, top=3, exclude=()):
    """What the buyer sends back.

       A one-way deal is a wish, not a trade.  If the seller drops `need` WAR by
       giving a player up, something has to close that gap.  So sweep the buyer's
       own squad for players who are worth more to the seller than they are to the
       buyer -- surplus at one club and a hole at the other is exactly the asymmetry
       a trade exists to exploit.

       `max_loss` is the budget, and it is what stops the search proposing that
       Mumbai solve an opening problem by sending Bumrah out.  Whatever goes back
       cannot cost the buyer more than the incoming player is worth, or the deal is
       self-defeating however happy it makes the seller."""
    import engine
    from trade import vacancies
    C = C or engine.boot()
    PW = C['PW']
    base_b, base_s = C['base'][buyer][1], C['base'][seller][1]
    # engine.evaluate() prices players out of PA, so anything absent there cannot be
    # part of a proposal however well it screens
    known = set(C['PA'].player)
    squad = [p for p in C['squads'][buyer] if p not in set(exclude) and p in known]
    out = []
    for p in squad:
        _, v_s, _, _ = vacancies(PW, seller, C['bb'], C['bw'], add=(p,))
        if not np.isfinite(v_s):
            continue
        gain_s = v_s - base_s
        if gain_s <= 0:
            continue
        _, v_b, _, _ = vacancies(PW, buyer, C['bb'], C['bw'], drop=(p,))
        if not np.isfinite(v_b):
            continue
        loss_b = v_b - base_b                      # negative
        r = PW[PW.player == p].iloc[0]
        if abs(loss_b) >= max_loss:
            continue
        sal_p = float(r.salary) if pd.notna(r.salary) else 0.30
        # neither side gives up a materially bigger name than it receives
        lo, hi = min(sal_p, in_salary), max(sal_p, in_salary)
        if hi > 0 and lo / hi < SAL_RATIO:
            continue
        out.append(dict(player=p, gain_to_seller=round(float(gain_s), 3),
                        cost_to_buyer=round(float(loss_b), 3),
                        net=round(float(gain_s + loss_b), 3),
                        salary=round(float(r.salary) if pd.notna(r.salary) else 0.30, 2),
                        pWAR=round(float(r.pWAR), 2),
                        covers=bool(gain_s >= abs(need))))
    d = pd.DataFrame(out)
    if not len(d):
        return d
    # cover the seller's loss where possible, and among those that do, give up least
    return d.sort_values(['covers', 'cost_to_buyer'],
                         ascending=[False, False]).head(top).reset_index(drop=True)


def confirm(team, pkgs, C, top=2):
    """Re-check the shortlist with the full evaluator before anything is shown.

       The screen works in XII value alone; the card reports `util`, which also counts
       title odds and the money moving.  Those can disagree -- a deal can look positive
       on XII and land negative once a Rs 1.7cr salary swing is priced in, which is how
       a card once appeared showing the buyer at -1.40.  So the shortlist is confirmed
       against the same numbers the card will print."""
    import engine
    out = []
    for r in pkgs.itertuples():
        back = list(r.gives_all or [])
        sal = {r.gets: r.gets_sal}
        ev = engine.evaluate(team, r.from_team, [r.gets], back, sal)
        a = next(x for x in ev['rows'] if x['team'] == team)
        b = next(x for x in ev['rows'] if x['team'] == r.from_team)
        if a['util'] > 0 and b['util'] > SELLER_NET_TOL:
            out.append((ev, r))
        if len(out) >= top:
            break
    return out


def package(team, slot=None, top=3, C=None, verify=False):
    """A complete two-sided proposal per candidate: who comes in, who goes back, and
       whether both clubs finish ahead.  `verify=True` spends ~6s a deal running the
       real auction-and-season evaluation instead of the screen's XII arithmetic."""
    import engine
    C = C or engine.boot()
    R = opportunities_for(team, slot=slot, top=top, C=C)
    d = R['table']
    if not len(d):
        return R
    props = []
    meta_all = C['PA'].set_index('player')
    unit_needed = R['hole']['unit'] if R.get('hole') else 'Batting'
    for r in d.itertuples():
        ret = best_return(team, r.from_team, r.d_sell, max_loss=max(r.d_buy, 0.80) * 2.0,
                          in_salary=r.salary, C=C, in_pwar=r.pWAR,
                          in_capped=int(meta_all.loc[r.player, 'capped'])
                          if r.player in meta_all.index else 0,
                          in_player=r.player)
        gl = ret['players'] if ret else []
        p = dict(gets=r.player, gives=(gl[0] if gl else None), gives_all=gl,
                 from_team=r.from_team,
                 gets_sal=r.salary, gives_sal=(ret['salary'] if ret else 0.0),
                 buy_gain=r.d_buy, buy_cost=(ret['cost'] if ret else 0.0),
                 sell_loss=r.d_sell, sell_gain=(ret['gain'] if ret else 0.0))
        p['buy_net'] = round(p['buy_gain'] + p['buy_cost'], 3)
        p['sell_net'] = round(p['sell_loss'] + p['sell_gain'], 3)
        p['cash'] = round(p['gets_sal'] - p['gives_sal'], 2)
        p['saving'] = r.saving
        p['tier'] = r.tier
        rep = replaces(team, p['gets'], gl, C)
        p['replaces'] = rep['line'] if rep else ''
        p['overseas_after'] = rep['overseas_after'] if rep else np.nan
        p['why'] = r.why if hasattr(r, 'why') else ''
        if p['gives']:
            p['why'] += (f" Sending {p['gives']} back covers {p['sell_gain']:.2f} of that, "
                         f"leaving {r.from_team} {p['sell_net']:+.2f} overall.")
        p['why'] += (f" Net to {team}: {p['buy_net']:+.2f}.")
        # realistic = buyer ahead, seller not meaningfully behind, and neither side
        # so far ahead of the other that the deal reads as charity
        # the man losing his place must do the same job as the man arriving
        drop1 = (rep['dropped'][0] if rep and rep['dropped'] else None)
        p['displaces'] = drop1
        p['role_match'] = bool(drop1 is None or _discipline(drop1, C) == unit_needed)
        # nobody hands a player over for nothing, so a proposal with an empty return
        # is not a trade
        p['both_gain'] = bool(gl and p['role_match'] and p['buy_net'] > 0
                              and p['sell_net'] > SELLER_NET_TOL
                              and abs(p['buy_net'] - p['sell_net']) <= MAX_ASYMMETRY)
        if verify and p['gives'] is not None:
            e = engine.evaluate(team, r.from_team, [p['gets']], [p['gives']],
                                {p['gets']: p['gets_sal'], p['gives']: p['gives_sal']})
            a = next(x for x in e['rows'] if x['team'] == team)
            b = next(x for x in e['rows'] if x['team'] == r.from_team)
            p.update(util_buy=a['util'], util_sell=b['util'], mutual=bool(a['util'] > 0 and b['util'] > 0))
        props.append(p)
    R['packages'] = pd.DataFrame(props)
    return R


# =====================================================================
#  PHASE USAGE, BOWLING PAR, AND THE SIDE THAT ACTUALLY PLAYED
# =====================================================================
"""Two things the first cut got wrong.

   Slots 8-12 were shown with a blank par.  Dropping the batting requirement was
   right -- they are bowlers -- but leaving them unjudged was not.  They should be
   held to a BOWLING standard, and bench_bowl.csv has carried a par by phase all
   along.  A death bowler and a powerplay bowler are not doing the same job, so the
   par a man is held to is blended by the phases he actually bowls, taken from his
   real 2026 usage rather than assumed from his role label.

   And the XII shown first was the optimiser's ideal, not the side that took the
   field.  Those differ, and a coach looking at his own squad wants to start from
   what he actually picked."""



def _ball(year=_SEASON):
    """Ball-by-ball for one IPL season, teams reduced to their three-letter code."""
    if year in _BBB:
        return _BBB[year]
    import os
    d = pd.read_parquet(_os.path.join(_DATA, 'ipl_df__4_.parquet'))
    d = d[(d.year == year) & (d.competition == 'IPL')].copy()
    d['tb'] = d.team_bat.map(_TEAM_MAP)
    d['tw'] = d.team_bowl.map(_TEAM_MAP)
    _BBB[year] = d
    return d


_PU = {}


def phase_usage(year=_SEASON):
    """Balls each bowler actually sent down in each phase, and the share.

       Usage is measured, not inferred.  A player labelled a death bowler who in fact
       bowled two overs at the death and eight in the middle should be judged mostly
       on the middle."""
    if year in _PU:
        return _PU[year]
    d = _ball(year)
    d = d[(d.wide == 0) & (d.noball == 0)]
    g = d.groupby(['bowl', 'phase']).size().unstack(fill_value=0)
    for p in ('Powerplay', 'Middle', 'Death'):
        if p not in g.columns:
            g[p] = 0
    g = g[['Powerplay', 'Middle', 'Death']]
    tot = g.sum(axis=1).replace(0, np.nan)
    share = g.div(tot, axis=0)
    share.columns = [c + '_sh' for c in share.columns]
    out = g.join(share)
    out['balls'] = tot
    _PU[year] = out.reset_index().rename(columns={'bowl': 'player'})
    return _PU[year]


def bowl_par(player, C, usage=None):
    """The bowling par this player is held to: bench_bowl.csv's par for each phase,
       blended by how much he actually bowls in each.

       Returns (par, label).  A bowler with no 2026 record gets the flat mean, which
       is the honest answer when there is nothing to weight by."""
    bw = C['bw'].set_index('phase')
    usage = phase_usage() if usage is None else usage
    r = usage[usage.player == player]
    if not len(r) or not np.isfinite(r.balls.iloc[0]) or r.balls.iloc[0] < 24:
        return float(bw.par_pWAR.mean()), 'no 2026 record'
    r = r.iloc[0]
    w = {p: float(r[p + '_sh']) for p in ('Powerplay', 'Middle', 'Death')}
    par = sum(w[p] * float(bw.loc[p, 'par_pWAR']) for p in w)
    lab = ' / '.join(f"{p[:2].upper()} {w[p]*100:.0f}%" for p in
                     ('Powerplay', 'Middle', 'Death') if w[p] >= 0.10)
    return float(par), lab


def appearances(year=_SEASON):
    """Matches played per player per team, counted from the ball-by-ball.

       A batter who never reached the crease and did not bowl leaves no trace, so
       this slightly understates a reserve batter's appearances.  For picking out a
       first-choice XII, which is what it is used for, that does not matter."""
    d = _ball(year)
    b = d.groupby(['tb', 'bat']).p_match.nunique().reset_index()
    b.columns = ['team', 'player', 'm_bat']
    w = d.groupby(['tw', 'bowl']).p_match.nunique().reset_index()
    w.columns = ['team', 'player', 'm_bowl']
    m = b.merge(w, on=['team', 'player'], how='outer').fillna(0)
    m['matches'] = m[['m_bat', 'm_bowl']].max(axis=1).astype(int)
    m['player'] = m.player.map(one)
    return m.groupby(['team', 'player'], as_index=False).matches.max()




def _dominant_phase(player, C, year=_SEASON):
    """Which phase this bowler mostly covers, measured against how much of the innings
       that phase is -- so a death bowler is a man who bowls the death more than four
       overs in twenty would predict."""
    u = phase_usage(year)
    r = u[u.player == player]
    if not len(r):
        return None
    r = r.iloc[0]
    avail = {'Powerplay': 6/20, 'Middle': 10/20, 'Death': 4/20}
    rel = {p: (float(r[p + '_sh']) / avail[p]) for p in avail}
    return max(rel, key=rel.get)


def replaces(team, gets, gives, C=None):
    """Who actually loses his place, and what it does to the overseas count.

       The XII is re-solved with the new man in it, and whoever was in the old side
       and is not in the new one is the player displaced.  If an overseas signing
       pushes out an Indian and the side was already carrying its four, a second
       overseas player has to drop out -- the MILP enforces that, so this reads the
       consequence off the solution rather than asserting it."""
    import engine
    from trade import vacancies
    C = C or engine.boot()
    PW = C['PW']
    before = C['base'][team][0]
    gives = [gives] if isinstance(gives, str) else list(gives or [])
    after, val, _, _ = vacancies(PW, team, C['bb'], C['bw'],
                                 add=(gets,), drop=tuple(gives))
    if after is None or not len(after):
        return None
    b, a = set(before.player), set(after.player)
    # the men going the other way obviously leave; the interesting name is whoever
    # loses his place BECAUSE the new man arrived
    out = sorted((b - a) - set(gives))
    inn = sorted(a - b)
    os_b = int(before.overseas.sum()); os_a = int(after.overseas.sum())
    meta = C['PA'].set_index('player')
    def _os(p):
        return bool(meta.loc[p, 'overseas']) if p in meta.index else False
    return dict(dropped=out, added=inn, overseas_before=os_b, overseas_after=os_a,
                gets_overseas=_os(gets),
                line=_replace_line(team, gets, out, inn, os_b, os_a, _os))


def _replace_line(team, gets, out, inn, os_b, os_a, is_os):
    if not out:
        return f"{gets} comes straight into the {team} XII without displacing anybody."
    who = out[0]
    tag = " (overseas)" if is_os(gets) else ""
    txt = f"{gets}{tag} takes {who}'s place in the {team} XII"
    extra = [p for p in out[1:]]
    if extra:
        os_extra = [p for p in extra if is_os(p)]
        if is_os(gets) and os_extra:
            txt += (f", and because that is a fifth overseas player, {os_extra[0]} drops out "
                    f"to keep the side inside the four permitted")
        else:
            txt += f", with {', '.join(extra)} also making way"
    return txt + f". Overseas in the XII: {os_b} \u2192 {os_a}."


def _discipline(p, C):
    """Whether a player is in the side to bat or to bowl."""
    m = C['PW'][C['PW'].player == p]
    if not len(m):
        return None
    r = m.iloc[0]
    return 'Bowling' if float(r.share_bowl) > float(r.share_bat) else 'Batting'


def best_return(buyer, seller, need, max_loss, in_salary, C=None, max_players=2,
                in_pwar=None, in_capped=None, in_player=''):
    """The package going back -- one player, or two when one cannot cover it.

       A star doing two jobs is not replaced by one uncapped batter, which is why a
       single-player search kept failing: the seller was left several WAR down and
       would simply refuse.  So if no one man covers the gap, pairs are tried.  The
       salary of the whole package is held against the incoming fee, so two cheap
       squad players cannot be dressed up as fair value for an India allrounder."""
    import engine
    from trade import vacancies
    C = C or engine.boot()
    PW = C['PW']
    base_b, base_s = C['base'][buyer][1], C['base'][seller][1]
    known = set(C['PA'].player)
    meta = C['PA'].set_index('player')
    squad = [p for p in C['squads'][buyer] if p in known]
    sal = {p: (float(meta.loc[p, 'salary']) if pd.notna(meta.loc[p, 'salary']) else 0.30)
           for p in squad if p in meta.index}

    def ok_salary(tot):
        lo, hi = min(tot, in_salary), max(tot, in_salary)
        return hi <= 0 or lo / hi >= SAL_RATIO

    def ok_player(p):
        if p not in meta.index or p in UNTRADEABLE:
            return False
        w = float(meta.loc[p, 'pWAR']) if pd.notna(meta.loc[p, 'pWAR']) else 0.0
        # never give up a better player than the one arriving
        # star-adjusted, so a retained man is not swapped for a bigger recent number
        if in_pwar is not None and star_value(p, w) >= star_value(in_player, in_pwar):
            return False
        # never give up an India international for an uncapped man
        if PROTECT_CAPPED and in_capped is not None:
            if int(meta.loc[p, 'capped'] or 0) == 1 and int(in_capped or 0) == 0:
                return False
        return True

    singles = []
    for p in squad:
        if not ok_player(p):
            continue
        _, v_s, _, _ = vacancies(PW, seller, C['bb'], C['bw'], add=(p,))
        # A return does not have to force its way into the seller's XII.  Clubs take
        # players who cover a role they are thin in, or who are blocked at the buyer's
        # club by someone better and would walk into a weaker squad.  Requiring a
        # positive XII gain here ruled out exactly the surplus-for-need swaps that
        # make up most real IPL trades, so anything not actively harmful is allowed
        # and the seller's NET position decides.
        if not np.isfinite(v_s) or v_s - base_s < 0:
            continue
        _, v_b, _, _ = vacancies(PW, buyer, C['bb'], C['bw'], drop=(p,))
        if not np.isfinite(v_b):
            continue
        singles.append(dict(player=p, gain=v_s - base_s, cost=v_b - base_b, sal=sal.get(p, 0.30)))
    if not singles:
        return None

    def ok_pkg(players):
        # star-adjusted, the package going back must neither outweigh the man arriving
        # nor be a token: real trades sit inside a band, not at either extreme
        tot = sum(star_value(p, float(meta.loc[p, 'pWAR'] or 0)) for p in players
                  if p in meta.index)
        want = star_value(in_player, in_pwar or 0)
        return want * RETURN_FLOOR <= tot <= want * (1 + PKG_TOL)

    def score(players, gain, cost):
        return dict(players=players, gain=round(gain, 3), cost=round(cost, 3),
                    salary=round(sum(sal.get(p, 0.30) for p in players), 2))

    cands = []
    for s in singles:
        if abs(s['cost']) < max_loss and ok_salary(s['sal']) and ok_pkg([s['player']]):
            cands.append(score([s['player']], s['gain'], s['cost']))
    covered = [c for c in cands if c['gain'] >= abs(need) + SELLER_NET_TOL]
    if covered:
        return max(covered, key=lambda c: c['cost'])

    if max_players >= 2:
        top = sorted(singles, key=lambda s: -s['gain'])[:8]
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                a, b = top[i], top[j]
                tot_sal = a['sal'] + b['sal']
                if not ok_salary(tot_sal) or not ok_pkg([a['player'], b['player']]):
                    continue
                _, v_s, _, _ = vacancies(PW, seller, C['bb'], C['bw'],
                                         add=(a['player'], b['player']))
                _, v_b, _, _ = vacancies(PW, buyer, C['bb'], C['bw'],
                                         drop=(a['player'], b['player']))
                if not (np.isfinite(v_s) and np.isfinite(v_b)):
                    continue
                gain, cost = v_s - base_s, v_b - base_b
                if abs(cost) >= max_loss * 1.6:
                    continue
                cands.append(score([a['player'], b['player']], gain, cost))
        covered = [c for c in cands if c['gain'] >= abs(need) + SELLER_NET_TOL]
        if covered:
            return max(covered, key=lambda c: c['cost'])
    return max(cands, key=lambda c: c['gain'] + c['cost']) if cands else None


FULL_NAME = {v: k for k, v in _TEAM_MAP.items()}
XII_JSON = _os.path.join(_DATA, 'playing_xii_2026.json')
RETIRED_JSON = _os.path.join(_DATA, 'retired_2027.json')


def _xii_override(team, path=None):
    """The hand-edited XII for one club, if the JSON file has an entry for it."""
    import json
    try:
        d = json.load(open(path or XII_JSON, encoding='utf-8'))
        e = d.get(team)
        return e if e and e.get('xii') else None
    except Exception:
        return None


def retired():
    """Men still carried in the roster files who will not play again.

       The squad data has no retirement flag, so Ajinkya Rahane still reads as a KKR
       opener.  Leaving him in reports a hole that cannot be traded for, since no club
       can acquire him.  The list is a plain JSON file meant to be edited by hand."""
    import json
    try:
        return set(json.load(open(RETIRED_JSON, encoding='utf-8')).get('retired', []))
    except Exception:
        return set()


def export_xii(path=XII_JSON, year=_SEASON, C=None):
    """Write every club's last-match XII to JSON so it can be corrected by hand.

       Batting order is derived from who reached the crease first, which is right for
       the men who batted but says nothing about someone who padded up and was not
       needed.  Rather than hide that, the side is written out and read back, so a
       wrong name can be fixed in one file instead of in code."""
    import engine, json
    C = C or engine.boot()
    out = {}
    for t in C['teams']:
        p, _ = positions(t, C, year, use_json=False)
        out[t] = dict(team=t, name=FULL_NAME.get(t, t), season=year,
                      p_match=int(p.attrs.get('p_match')) if len(p) else None,
                      xii=[dict(slot=int(r.bat_slot), player=r.player,
                                judged_on=r.judged_on, group=r.group)
                           for r in p.itertuples()])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return path


def bowl_groups(year=_SEASON):
    """Each bowler's team, workload, and the phase he genuinely specialises in.

       A raw share is the wrong test: there are ten middle overs and only four at the
       death, so nearly every bowler's biggest share is the middle and nobody comes out
       a death bowler.  Each share is divided by that phase's share of the innings
       first, so a specialist is a man who bowls a phase more than the innings offers."""
    u = phase_usage(year)
    d = _ball(year)
    tm = d.groupby(['tw', 'bowl'], as_index=False).p_match.nunique()
    tm.columns = ['team', 'player', 'matches']
    u = u.merge(tm, on='player', how='right')
    sh = u[['Powerplay_sh', 'Middle_sh', 'Death_sh']].fillna(0)
    avail = {'Powerplay_sh': 6/20, 'Middle_sh': 10/20, 'Death_sh': 4/20}
    rel = sh.div(pd.Series(avail))
    u['phase'] = rel.idxmax(axis=1).str.replace('_sh', '', regex=False)
    u['balls'] = u.balls.fillna(0)
    return u
