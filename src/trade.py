import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 STEPS 4-5 on the pWAR framework
   * vacancies from the pWAR-weighted XII vs role par
   * auction pool valued in pWAR
   * recovery: can the vacating side replace what left, and at what standard
   * purse sequence: carry-over -> +Rs6cr -> TRADE -> release deadline
   * surplus on the refitted price model (pWAR, scarcity, flex, capped, overseas)
   * league simulation -> playoff / title probability
=====================================================================
"""
import sys, os, json, re
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from ipl_trade_optimizer import (build_players_pwar, squad_pwar, optimize_xii_pwar,
                                 BAT_W, phase_multiplier, ALIAS)
from core import players, price_model2, archetype_features, market_fair2, cr
DATA=_DATA
RPW=82.5; GAMES=14; REPL_WIN=0.30; DENS=0.01212
CARRY={'CSK':2.40,'DC':0.35,'GT':1.95,'KKR':0.45,'LSG':4.55,'MI':0.55,'PBKS':3.50,'RR':2.65,'RCB':0.25,'SRH':5.45}
TOPUP=6.0; MAX_SQUAD=25

# ---------------------------------------------------------------- vacancies
def vacancies(P, team, bench_bat, bench_bowl, add=(), drop=()):
    sq=squad_pwar(P,team,add=add,drop=drop)
    xii,val,msg=optimize_xii_pwar(sq)
    if xii is None: return None,np.nan,pd.DataFrame(),msg
    pb=dict(zip(bench_bat.bat_group,bench_bat.par_pWAR)); rows=[]
    # no batting requirement below No.7 -- 8 is a bowling allrounder, 9-12 are bowlers
    grp={1:'Opener',2:'Opener',3:'No3',4:'Middle',5:'Middle',6:'Lower',7:'Lower'}
    for r in xii.itertuples():
        g=grp.get(int(r.bat_slot),'Tail'); par=pb.get(g,np.nan)
        if pd.notna(par) and r.pWAR<par:
            rows.append(dict(team=team,slot=g,occupant=r.player,pWAR=r.pWAR,par=par,
                             gap=par-r.pWAR,weight=BAT_W.get(int(r.bat_slot),1.0),
                             gap_value=(par-r.pWAR)*BAT_W.get(int(r.bat_slot),1.0)))
    v=pd.DataFrame(rows)
    if len(v): v=v.sort_values('gap_value',ascending=False).groupby(['team','slot'],as_index=False).first()
    return xii,val,v,'ok'

# ---------------------------------------------------------------- purse
def purse_and_slots(P, releases, trades=None):
    trades=trades or []; traded=set(t['player'] for t in trades)
    rows=[]
    for tm in sorted(CARRY):
        sq=P[P.team==tm]
        p=CARRY[tm]+TOPUP
        out=sum(float(sq[sq.player==t['player']].salary.iloc[0])
                for t in trades if t['from']==tm and (sq.player==t['player']).any())
        inn=sum(float(t['new_salary']) for t in trades if t['to']==tm)
        p+=out-inn
        rel=[r for r in releases.get(tm,[]) if r not in traded]
        freed=float(sq[sq.player.isin(rel)].salary.sum())
        p+=freed
        n_out=sum(1 for t in trades if t['from']==tm and (sq.player==t['player']).any())
        n_in=sum(1 for t in trades if t['to']==tm)
        final=len(sq)-n_out+n_in-len(rel)
        rows.append(dict(team=tm,carry=CARRY[tm],topup=TOPUP,trade_out=out,trade_in=inn,
                         releases=freed,n_rel=len(rel),purse=p,slots=max(MAX_SQUAD-final,0)))
    return pd.DataFrame(rows).set_index('team')

# ---------------------------------------------------------------- recovery
def recovery(pool, vac, purse, slots, pm2, sims=200, seed=7):
    """Can the vacancy be filled, and filled AT PAR, from the auction pool?"""
    if not len(vac): return pd.DataFrame()
    rng=np.random.default_rng(seed); out=[]
    for v in vac.itertuples():
        cand=pool[(pool.bat_group==v.slot)|(pool.bat_group.isna())]
        if not len(cand): out.append(dict(slot=v.slot,p_fill=0.0,p_at_par=0.0,e_pWAR=np.nan)); continue
        fills=at_par=0; q=[]
        for _ in range(sims):
            k=max(int(rng.poisson(max(len(cand)/6,1))),1)
            draw=cand.sample(min(k,len(cand)),replace=False,random_state=int(rng.integers(1e9)))
            aff=draw[draw.apply(lambda r: market_fair2(r,pm2),axis=1)<=purse]
            if len(aff):
                fills+=1; best=aff.pWAR.max(); q.append(best)
                if best>=v.par: at_par+=1
        out.append(dict(slot=v.slot,occupant=v.occupant,par=round(v.par,2),
            p_fill=fills/sims,p_at_par=at_par/sims,e_pWAR=round(np.mean(q),2) if q else np.nan))
    return pd.DataFrame(out)

# ---------------------------------------------------------------- league
def team_strength(xii_values):
    """XII value is a weighted pWAR sum; convert to expected wins.  An average side
       wins 7 of 14 and a replacement side 4.2, so the league mean XII value must map
       to 2.8 wins above replacement.  One scale factor, calibrated not guessed."""
    m=np.mean(list(xii_values.values())); k=2.8/m
    return {t: REPL_WIN*GAMES + v*k for t,v in xii_values.items()}, k

def wp(a,b): return float(np.clip(0.5+((a-b)/GAMES*RPW)*DENS,0.02,0.98))
def simulate(strength, sims=8000, seed=11):
    rng=np.random.default_rng(seed); N=list(strength); n=len(N); S=np.array([strength[t] for t in N])
    t4=np.zeros(n); t2=np.zeros(n); ti=np.zeros(n)
    P=np.array([[wp(S[i],S[j]) if i!=j else .5 for j in range(n)] for i in range(n)])
    for _ in range(sims):
        w=np.zeros(n)
        for i in range(n):
            for j in range(i+1,n):
                for _k in range(2):
                    if rng.random()<P[i,j]: w[i]+=1
                    else: w[j]+=1
        o=np.argsort(-(w+rng.random(n)*1e-6))
        t4[o[:4]]+=1; t2[o[:2]]+=1
        q1,q2,e1,e2=o[0],o[1],o[2],o[3]
        wq1=q1 if rng.random()<wp(S[q1],S[q2]) else q2; lq1=q2 if wq1==q1 else q1
        wel=e1 if rng.random()<wp(S[e1],S[e2]) else e2
        wq2=lq1 if rng.random()<wp(S[lq1],S[wel]) else wel
        ti[wq1 if rng.random()<wp(S[wq1],S[wq2]) else wq2]+=1
    return pd.DataFrame({'team':N,'p_top4':100*t4/sims,'p_top2':100*t2/sims,'p_title':100*ti/sims}).set_index('team')
