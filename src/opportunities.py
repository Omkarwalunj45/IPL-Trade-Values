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


def positions(team, C=None):
    """Every slot in the current best XII against the par for that slot.

       Returns one row per player in the XII.  Slots 8-12 show par as NaN because
       no batting standard applies to them -- that is not a missing value, it is
       the absence of a requirement."""
    import engine
    C = C or engine.boot()
    xii, val, vac, msg = C['base'][team]
    if xii is None or not len(xii):
        return pd.DataFrame(), msg
    par = dict(zip(C['bb'].bat_group, C['bb'].par_pWAR))
    from ipl_trade_optimizer import BAT_W, BOWL_W
    use = phase_usage()
    rows = []
    for r in xii.itertuples():
        s = int(r.bat_slot)
        g = GRP.get(s)
        if g is not None:
            # slots 1-7: judged on batting, against the par for that batting group
            p = par.get(g, np.nan)
            w = BAT_W.get(s, 1.0)
            unit, note = 'Batting', g
        else:
            # slots 8-12: bowlers.  Judged on bowling, against a par blended by the
            # phases they actually bowled in 2026 -- not by their role label.
            p, note = bowl_par(r.player, C, use)
            w = BOWL_W.get(int(r.bowl_slot), 0.5) if pd.notna(r.bowl_slot) else 0.5
            unit = 'Bowling'
        gap = (p - r.pWAR) if pd.notna(p) else np.nan
        rows.append(dict(bat_slot=s, group=g or 'Bowler', judged_on=unit, basis=note,
                         player=r.player, pWAR=round(float(r.pWAR), 2),
                         par=round(float(p), 2) if pd.notna(p) else np.nan,
                         gap=round(float(gap), 2) if pd.notna(gap) else np.nan,
                         weight=round(float(w), 2),
                         gap_value=round(float(gap * w), 2) if pd.notna(gap) else np.nan,
                         overseas=bool(r.overseas), wk=bool(r.wk),
                         bowl_slot=r.bowl_slot,
                         status=('—' if pd.isna(p) else
                                 'Hole' if gap > HOLE_TOL else
                                 'Thin' if gap > 0 else 'Above par')))
    return pd.DataFrame(rows).sort_values('bat_slot').reset_index(drop=True), 'ok'


def holes(team, top=3, C=None):
    """The slots worth fixing, ranked, across BOTH disciplines.

       Batting holes carry the auction's fill probabilities, because the auction
       models batting requirements.  Bowling holes do not -- engine._auction only
       raises batting requirements -- so those columns are blank rather than
       invented."""
    import engine
    C = C or engine.boot()
    pos, _ = positions(team, C)
    if not len(pos):
        return pd.DataFrame()
    v = pos[(pos.gap > HOLE_TOL)].copy()
    if not len(v):
        return pd.DataFrame()
    # one hole per group: the weakest occupant is the one that defines it
    v = v.sort_values('gap_value', ascending=False).groupby(
        ['judged_on', 'group'], as_index=False).first()
    v = v.sort_values('gap_value', ascending=False).head(top)
    auc = C['auc0']
    a = auc[auc.team == team].set_index('role')
    purse = float(C['p0'].loc[team, 'purse'])
    pool = _pool(C)
    out = []
    for r in v.itertuples():
        bat = r.judged_on == 'Batting'
        d = (_depth(pool, r.group, r.par, purse, C['pm2']) if bat
             else _depth_bowl(pool, r.basis, r.par, purse, C['pm2']))
        hit = a.loc[r.group] if (bat and r.group in a.index) else None
        out.append(dict(slot=r.group, unit=r.judged_on, basis=r.basis,
                        occupant=r.player, pWAR=r.pWAR, par=r.par, gap=r.gap,
                        weight=r.weight, gap_value=r.gap_value,
                        p_fill=round(float(hit.p_fill), 2) if hit is not None else np.nan,
                        p_at_par=round(float(hit.p_at_par), 2) if hit is not None else np.nan,
                        recovery=round(float(hit.recovery_WAR), 3) if hit is not None else np.nan,
                        **d))
    return pd.DataFrame(out)


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

# a deal that costs the seller more than this in XII value is one they would not do
# for nothing.  It is not discarded -- it is reclassified as needing something back.
MAX_DONOR_LOSS = 1.00

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
    par = float(inc.par.min()) if len(inc) else np.nan
    inc_pwar = float(inc.pWAR.min()) if len(inc) else 0.0
    before = _slot_pwar(C['base'][team][0], slot, unit)

    cand = PW[(PW.team != team) & (~PW.player.astype(str).str.startswith('Replacement'))].copy()
    # a player cannot fix a batting hole he is worse than, and a specialist bowler
    # cannot fix one at all -- both filters are about candidacy, not quality
    # a batting hole needs someone who bats, a bowling hole someone who bowls
    share = cand.share_bowl if unit == 'Bowling' else cand.share_bat
    cand = cand[(cand.pWAR > inc_pwar) & (share > 0.25)]
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
                np.where(~d.fixes_hole, 'Does not close it',
                np.where(d.d_sell > -MAX_DONOR_LOSS, 'Straight swap', 'Needs compensation')))
    order = {'Straight swap': 0, 'Needs compensation': 1,
             'Does not close it': 2, 'Cannot afford': 3}
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
    H = holes(team, top=3, C=C)
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


def find_return(buyer, seller, need, max_loss, C=None, top=3, exclude=()):
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
    squad = [p for p in C['squads'][buyer] if p not in set(exclude)]
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
    for r in d.itertuples():
        ret = find_return(team, r.from_team, r.d_sell, max_loss=r.d_buy, C=C, top=1)
        give = ret.iloc[0] if len(ret) else None
        p = dict(gets=r.player, gives=(give.player if give is not None else None),
                 from_team=r.from_team,
                 gets_sal=r.salary, gives_sal=(float(give.salary) if give is not None else 0.0),
                 buy_gain=r.d_buy, buy_cost=(float(give.cost_to_buyer) if give is not None else 0.0),
                 sell_loss=r.d_sell, sell_gain=(float(give.gain_to_seller) if give is not None else 0.0))
        p['buy_net'] = round(p['buy_gain'] + p['buy_cost'], 3)
        p['sell_net'] = round(p['sell_loss'] + p['sell_gain'], 3)
        p['cash'] = round(p['gets_sal'] - p['gives_sal'], 2)
        p['saving'] = r.saving
        p['tier'] = r.tier
        p['why'] = r.why if hasattr(r, 'why') else ''
        if p['gives']:
            p['why'] += (f" Sending {p['gives']} back covers {p['sell_gain']:.2f} of that, "
                         f"leaving {r.from_team} {p['sell_net']:+.2f} overall.")
        p['why'] += (f" Net to {team}: {p['buy_net']:+.2f}.")
        p['both_gain'] = bool(p['buy_net'] > 0 and p['sell_net'] > -MAX_DONOR_LOSS)
        if verify and p['gives']:
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

_SEASON = 2026

_TEAM_MAP = {"Chennai Super Kings": "CSK", "Delhi Capitals": "DC", "Gujarat Titans": "GT",
             "Kolkata Knight Riders": "KKR", "Lucknow Super Giants": "LSG",
             "Mumbai Indians": "MI", "Punjab Kings": "PBKS", "Rajasthan Royals": "RR",
             "Royal Challengers Bengaluru": "RCB", "Sunrisers Hyderabad": "SRH"}

_BBB = {}


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


def phase_usage(year=_SEASON):
    """Balls each bowler actually sent down in each phase, and the share.

       Usage is measured, not inferred.  A player labelled a death bowler who in fact
       bowled two overs at the death and eight in the middle should be judged mostly
       on the middle."""
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
    return out.reset_index().rename(columns={'bowl': 'player'})


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


def bat_positions(year=_SEASON):
    """Which position each batter actually came in at, match by match.

       There is no batting-position column, so it is derived from the order in which
       men reached the crease: sort each innings by the first ball a batter faced and
       the ranking IS the order.  A man who never got in leaves no row, which is
       correct -- he did not occupy the position that day."""
    d = _ball(year)
    f = d.groupby(['p_match', 'inns', 'tb', 'bat'], as_index=False).ball_id.min()
    f['pos'] = f.groupby(['p_match', 'inns']).ball_id.rank(method='first').astype(int)
    f['group'] = np.where(f.pos <= 2, 'Opener',
                 np.where(f.pos == 3, 'No3',
                 np.where(f.pos <= 5, 'Middle',
                 np.where(f.pos <= 8, 'Lower', 'Tail'))))
    return f.rename(columns={'tb': 'team', 'bat': 'player'})


def bowl_groups(year=_SEASON):
    """Each bowler's dominant phase in that season, from balls actually bowled."""
    u = phase_usage(year)
    d = _ball(year)
    tm = d.groupby(['tw', 'bowl'], as_index=False).p_match.nunique()
    tm.columns = ['team', 'player', 'matches']
    u = u.merge(tm, on='player', how='right')
    sh = u[['Powerplay_sh', 'Middle_sh', 'Death_sh']].fillna(0)
    # A raw share is the wrong test.  There are ten middle overs and only four at the
    # death, so almost every bowler's biggest share is the middle and nobody comes out
    # a death bowler.  What marks a specialist is bowling a phase MORE than the
    # innings offers it, so each share is divided by that phase's share of the innings.
    avail = {'Powerplay_sh': 6/20, 'Middle_sh': 10/20, 'Death_sh': 4/20}
    rel = sh.div(pd.Series(avail))
    u['phase'] = rel.idxmax(axis=1).str.replace('_sh', '', regex=False)
    u['phase_lean'] = rel.max(axis=1).round(2)
    u['balls'] = u.balls.fillna(0)
    return u


# slot -> which batting group is allowed to fill it.  This is the user-facing shape
# of a T20 side, not the MILP's: two openers, a three, two in the middle, three
# lower-order, then four bowlers picked on the phases they cover.
XII_PLAN = [(1, 'Opener'), (2, 'Opener'), (3, 'No3'), (4, 'Middle'), (5, 'Middle'),
            (6, 'Lower'), (7, 'Lower'), (8, 'Lower'),
            (9, 'Powerplay'), (10, 'Middle'), (11, 'Death'), (12, 'any')]
_BAT_SLOTS_N = 8


def as_played(team, year=_SEASON, C=None):
    """The XII this club actually fielded, built slot by slot.

       For each batting slot only players who ACTUALLY BATTED in that group are
       eligible -- openers can only fill 1 and 2, a number three only 3, and so on.
       Slots 9-12 go to bowlers, chosen by the phase each man genuinely bowled most,
       so the side gets powerplay, middle and death cover rather than four bowlers
       who all bowl the same overs.

       Within a group, candidates are ranked on WAR x matches: projected value
       weighted by how often the selectors actually picked him."""
    import engine
    C = C or engine.boot()
    bp = bat_positions(year)
    bp = bp[bp.team == team]
    bp['player'] = bp.player.map(one)
    bg = bowl_groups(year)
    bg = bg[bg.team == team]
    bg['player'] = bg.player.map(one)

    pw = C['PW'][['player', 'pWAR', 'role', 'overseas', 'is_wk']]
    war = dict(zip(pw.player, pw.pWAR))
    meta = pw.set_index('player')

    # how often each man appeared in each batting group
    cnt = bp.groupby(['player', 'group'], as_index=False).p_match.nunique()
    cnt.columns = ['player', 'group', 'matches']
    cnt['pWAR'] = cnt.player.map(war).fillna(0.0)
    cnt['war_matches'] = (cnt.pWAR * cnt.matches).round(2)

    bg['pWAR'] = bg.player.map(war).fillna(0.0)
    bg['war_matches'] = (bg.pWAR * bg.matches).round(2)

    used, rows = set(), []
    for slot, need in XII_PLAN:
        fallback = False
        if slot <= _BAT_SLOTS_N:
            c = cnt[(cnt.group == need) & (~cnt.player.isin(used))]
            c = c.sort_values(['matches', 'war_matches'], ascending=[False, False])
        else:
            pool_b = bg[(~bg.player.isin(used)) & (bg.balls >= 24)]
            c = pool_b[pool_b.phase == need] if need != 'any' else pool_b
            fallback = False
            if not len(c) and need != 'any':
                # nobody specialised in that phase.  Rather than leave the slot empty,
                # take the best remaining bowler and say plainly that the club had no
                # specialist -- an unfilled phase is itself a finding.
                c = pool_b; fallback = True
            c = c.sort_values(['war_matches', 'balls'], ascending=[False, False])
        if not len(c):
            rows.append(dict(slot=slot, need=need, player=None, matches=0, pWAR=np.nan,
                             war_matches=np.nan, basis='nobody played here'))
            continue
        b = c.iloc[0]; used.add(b.player)
        m = meta.loc[b.player] if b.player in meta.index else None
        rows.append(dict(slot=slot, need=need, player=b.player,
                         matches=int(b.matches), pWAR=round(float(b.pWAR), 2),
                         war_matches=float(b.war_matches),
                         basis=(need if slot <= _BAT_SLOTS_N else
                                (f"{b.phase} bowler \u2014 no {need} specialist" if fallback
                                 else f"{b.phase} bowler")),
                         overseas=int(m.overseas) if m is not None else 0,
                         wk=bool(m.is_wk) if m is not None else False,
                         still_at_club=b.player in set(C['squads'][team])))
    return pd.DataFrame(rows)
