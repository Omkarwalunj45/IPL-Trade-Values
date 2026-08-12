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

def boot():
    """Everything that does not depend on the trade."""
    if _C: return _C
    from core import players, price_model2, archetype_features
    from trade import vacancies, purse_and_slots, simulate
    from ipl_trade_optimizer import build_players_pwar
    P = players(); PA = archetype_features(P)
    _C['PA'] = PA; _C['pm2'] = price_model2(P); _C['PW'] = build_players_pwar()
    _C['bb'] = pd.read_csv(os.path.join(DATA,'bench_bat.csv'))
    _C['bw'] = pd.read_csv(os.path.join(DATA,'bench_bowl.csv'))
    rel = pd.read_csv(os.path.join(DATA,'release_list_2027.csv')); rel['player'] = rel.player.str.strip()
    _C['REL'] = rel.groupby('team').player.apply(list).to_dict()
    _C['teams'] = sorted(_C['PW'].team.dropna().unique())
    _C['base'] = {t: vacancies(_C['PW'], t, _C['bb'], _C['bw']) for t in _C['teams']}
    _C['k'] = 2.8 / np.mean([_C['base'][t][1] for t in _C['teams']])
    _C['S0'] = simulate({t: 0.30*14 + _C['base'][t][1]*_C['k'] for t in _C['teams']}, sims=1500)
    _C['p0'] = purse_and_slots(_C['PW'], _C['REL'])
    _C['par'] = dict(zip(_C['bb'].bat_group, _C['bb'].par_pWAR))
    _C['squads'] = _C['PW'].groupby('team').player.apply(lambda s: sorted(s)).to_dict()
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
    # ---- auction on the post-trade holes
    rel_names = {n for v in C['REL'].values() for n in v}
    pool = PA[PA.player.isin(rel_names) | (PA.auctionStatus == 'unsold')].copy()
    pool = pd.concat([pool, draw_entrants(np.random.default_rng(5), C['par'])], ignore_index=True)
    eb = pool.bat_group.map(EX).fillna(150.)
    pool['bat_rate'] = pool.pWAR/eb; pool['bowl_rate'] = pool.pWAR/280.
    pool['rel'] = np.clip(pool.balls_eq.fillna(200)/1000, .1, .9)
    pool['capped_f'] = np.where(pool.capped.fillna(0) == 1, 'CAPPED', 'UNCAPPED')
    pool['kind'] = pool.bowl_kind.fillna('pace'); pool['role'] = pool.role.fillna('Batter')
    pool['ipl_bf'] = pool.ipl_balls_faced.fillna(0); pool['ipl_bb'] = pool.ipl_balls_bowled.fillna(0)
    pool['sal'] = pool.salary; pool['overseas'] = pool.overseas.fillna(0)
    R = pd.DataFrame([dict(team=t, unit='bat', role=r.slot, occupant=r.occupant,
        rate=r.pWAR/EX.get(r.slot,150.), par=r.par/EX.get(r.slot,150.), exposure=EX.get(r.slot,150.),
        req_kind=None, incumbent_rate=r.pWAR/EX.get(r.slot,150.))
        for t in teams for r in aft[t][2].itertuples() if r.slot in EX]).reset_index(drop=True)
    auc = TE.auction_recovery(pool, R, p1.purse.to_dict(), p1.slots.to_dict(), sims=45)
    v1 = {t: aft[t][1] for t in teams}
    for t in (tA, tB): v1[t] = aft[t][1] + auc[auc.team == t].recovery_WAR.sum()
    S1 = simulate({t: 0.30*14 + v1[t]*k for t in teams}, sims=1500, seed=11)
    mf = lambda n: float(market_fair2(PA[PA.player == n].iloc[0], pm2))
    out = dict(A=tA, B=tB, players=[], rows=[], holes=[], infeasible=infeasible)
    for n in a_gets + b_gets:
        r = PA[PA.player == n].iloc[0]; s = sal.get(n, salary_of(n))
        out['players'].append(dict(player=n, to=tA if n in a_gets else tB, pWAR=round(float(r.pWAR),2),
            salary=round(s,2), market=round(mf(n),2), surplus=round(mf(n)-s,2), role=str(r.role)))
    for t in (tA, tB):
        gets = a_gets if t == tA else b_gets; gives = b_gets if t == tA else a_gets
        assets = (sum(mf(n)-sal.get(n, salary_of(n)) for n in gets)
                  - sum(mf(n)-salary_of(n) for n in gives))
        out['rows'].append(dict(team=t, xii_no=round(base[t][1],2), xii_yes=round(aft[t][1],2),
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
