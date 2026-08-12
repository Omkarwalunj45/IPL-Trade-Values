"""
Live trade evaluation.  The no-trade baseline (every squad's best XII, purses,
league odds) is identical for every trade, so it is computed once and cached;
a trade then only re-solves the two squads that changed, one auction and one
league run.
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'Datasets')
sys.path.insert(0, HERE)

EX = {'Opener':290., 'No3':254., 'Middle':215., 'Lower':98.}
_C = {}

def _stamp():
    """Modification time of the valuation file. Used as a cache key so that
       replacing final_pwar.csv invalidates the cached baseline instead of
       leaving stale player values in memory."""
    try: return os.path.getmtime(os.path.join(DATA, 'final_pwar.csv'))
    except OSError: return 0


def _auction(C, vac_by_team, purse, slots, sims=45, seed=7):
    """Run the mini auction for a given set of squad holes and purses, and return
       expected recovery in WAR per team. Used for BOTH the no-trade state and the
       post-trade state, so the two are always measured the same way."""
    import trade_eval as TE
    from entrants import draw_entrants
    from core import market_fair2
    PA = C['PA']
    rel_names = {n for v in C['REL'].values() for n in v}
    pool = PA[PA.player.isin(rel_names) | (PA.auctionStatus == 'unsold')].copy()
    pool = pd.concat([pool, draw_entrants(np.random.default_rng(seed), C['par'])], ignore_index=True)
    eb = pool.bat_group.map(EX).fillna(150.)
    pool['bat_rate'] = pool.pWAR / eb; pool['bowl_rate'] = pool.pWAR / 280.
    pool['rel'] = np.clip(pool.balls_eq.fillna(200) / 1000, .1, .9)
    pool['capped_f'] = np.where(pool.capped.fillna(0) == 1, 'CAPPED', 'UNCAPPED')
    pool['kind'] = pool.bowl_kind.fillna('pace'); pool['role'] = pool.role.fillna('Batter')
    pool['ipl_bf'] = pool.ipl_balls_faced.fillna(0); pool['ipl_bb'] = pool.ipl_balls_bowled.fillna(0)
    pool['sal'] = pool.salary; pool['overseas'] = pool.overseas.fillna(0)
    rows = [dict(team=t, unit='bat', role=r.slot, occupant=r.occupant,
                 rate=r.pWAR / EX.get(r.slot, 150.), par=r.par / EX.get(r.slot, 150.),
                 exposure=EX.get(r.slot, 150.), req_kind=None,
                 incumbent_rate=r.pWAR / EX.get(r.slot, 150.))
            for t, v in vac_by_team.items() for r in v.itertuples() if r.slot in EX]
    if not rows:
        return {t: 0.0 for t in vac_by_team}, pd.DataFrame()
    R = pd.DataFrame(rows).reset_index(drop=True)
    # a club cannot bid with a negative purse
    pr = {t: max(float(p), 0.0) for t, p in purse.items()}
    auc = TE.auction_recovery(pool, R, pr, slots, sims=sims)
    rec = {t: float(auc[auc.team == t].recovery_WAR.sum()) for t in vac_by_team}
    return rec, auc

def boot():
    """Everything that does not depend on the trade.

       Built into a local dict and published to the cache only once complete, so a
       failed or interrupted load can never leave a half-filled cache behind."""
    if _C.get('_ready') and _C.get('_stamp') == _stamp():
        return _C
    from core import players, price_model2, archetype_features
    from trade import vacancies, purse_and_slots, simulate
    from ipl_trade_optimizer import build_players_pwar
    c = {}
    P = players(); PA = archetype_features(P)
    c['PA'] = PA; c['pm2'] = price_model2(P); c['PW'] = build_players_pwar()
    c['bb'] = pd.read_csv(os.path.join(DATA, 'bench_bat.csv'))
    c['bw'] = pd.read_csv(os.path.join(DATA, 'bench_bowl.csv'))
    rel = pd.read_csv(os.path.join(DATA, 'release_list_2027.csv'))
    rel['player'] = rel.player.str.strip()
    c['REL'] = rel.groupby('team').player.apply(list).to_dict()
    c['teams'] = sorted(c['PW'].team.dropna().unique())
    c['base'] = {t: vacancies(c['PW'], t, c['bb'], c['bw']) for t in c['teams']}
    c['k'] = 2.8 / np.mean([c['base'][t][1] for t in c['teams']])
    c['p0'] = purse_and_slots(c['PW'], c['REL'])
    c['par'] = dict(zip(c['bb'].bat_group, c['bb'].par_pWAR))
    c['squads'] = c['PW'].groupby('team').player.apply(lambda s: sorted(s)).to_dict()
    # NO-TRADE STATE: every squad also goes to the auction and fills what it can.
    # Both states must be measured the same way, otherwise the post-trade side gets
    # a free lift purely from being the one where the auction was counted.
    c['rec0'], c['auc0'] = _auction(c, {t: c['base'][t][2] for t in c['teams']},
                                    c['p0'].purse.to_dict(), c['p0'].slots.to_dict())
    c['v0'] = {t: c['base'][t][1] + c['rec0'][t] for t in c['teams']}
    c['S0'] = simulate({t: 0.30*14 + c['v0'][t]*c['k'] for t in c['teams']}, sims=1500)
    c['_stamp'] = _stamp(); c['_ready'] = True
    _C.clear(); _C.update(c)
    return _C

def salary_of(name):
    C = boot(); r = C['PA'][C['PA'].player == name]
    return float(r.salary.iloc[0]) if len(r) and pd.notna(r.salary.iloc[0]) else 0.0

def evaluate(tA, tB, a_gets, b_gets, sal):
    """a_gets/b_gets: player names.  sal: {player: negotiated salary}."""
    from core import market_fair2
    from trade import vacancies, purse_and_slots, simulate
    import trade_eval as TE
    from entrants import draw_entrants
    C = boot(); PA, pm2, PW = C['PA'], C['pm2'], C['PW']
    teams, base, k = C['teams'], C['base'], C['k']
    aft = dict(base)
    aft[tA] = vacancies(PW, tA, C['bb'], C['bw'], add=a_gets, drop=b_gets)
    aft[tB] = vacancies(PW, tB, C['bb'], C['bw'], add=b_gets, drop=a_gets)
    # A squad that cannot field a legal XII after the trade returns nan. That is a real
    # answer -- the deal leaves them short of a legal side -- so flag it rather than
    # letting nan leak into every downstream number.
    infeasible = [t for t in (tA, tB) if not np.isfinite(aft[t][1])]
    for t in infeasible:
        aft[t] = (aft[t][0], base[t][1], aft[t][2], 'infeasible')
    trades = ([{'from': tB, 'to': tA, 'player': p, 'new_salary': sal.get(p, salary_of(p))} for p in a_gets] +
              [{'from': tA, 'to': tB, 'player': p, 'new_salary': sal.get(p, salary_of(p))} for p in b_gets])
    p1 = purse_and_slots(PW, C['REL'], trades)
    # ---- POST-TRADE STATE: same auction routine, same settings, every team
    rec, auc = _auction(C, {t: aft[t][2] for t in teams}, p1.purse.to_dict(), p1.slots.to_dict())
    v1 = {t: aft[t][1] + rec[t] for t in teams}
    S1 = simulate({t: 0.30*14 + v1[t]*k for t in teams}, sims=1500, seed=11)
    mf = lambda n: float(market_fair2(PA[PA.player == n].iloc[0], pm2))
    out = dict(A=tA, B=tB, players=[], rows=[], holes=[], infeasible=infeasible,
               unaffordable=[t for t in (tA, tB) if p1.loc[t,'purse'] < 0])
    for n in a_gets + b_gets:
        r = PA[PA.player == n].iloc[0]; s = sal.get(n, salary_of(n))
        out['players'].append(dict(player=n, to=tA if n in a_gets else tB, pWAR=round(float(r.pWAR),2),
            salary=round(s,2), market=round(mf(n),2), surplus=round(mf(n)-s,2), role=str(r.role)))
    for t in (tA, tB):
        gets = a_gets if t == tA else b_gets; gives = b_gets if t == tA else a_gets
        assets = (sum(mf(n)-sal.get(n, salary_of(n)) for n in gets)
                  - sum(mf(n)-salary_of(n) for n in gives))
        out['rows'].append(dict(team=t, xii_no=round(C['v0'][t],2), xii_yes=round(v1[t],2),
            top4_no=round(C['S0'].loc[t,'p_top4'],1), top4_yes=round(S1.loc[t,'p_top4'],1),
            title_no=round(C['S0'].loc[t,'p_title'],1), title_yes=round(S1.loc[t,'p_title'],1),
            purse_no=round(C['p0'].loc[t,'purse'],2), purse_yes=round(p1.loc[t,'purse'],2),
            assets=round(assets,2),
            util=round((v1[t]-base[t][1]) + 0.5*(S1.loc[t,'p_title']-C['S0'].loc[t,'p_title']) + 0.1*assets, 2)))
        for r in auc[auc.team == t].itertuples():
            out['holes'].append(dict(team=t, slot=r.role, occupant=r.occupant,
                p_fill=round(float(r.p_fill),2), p_at_par=round(float(r.p_at_par),2),
                recovery=round(float(r.recovery_WAR),3)))
    return out
