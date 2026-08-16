import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 STEP 13 -- SEQUENTIAL AUCTION CLEARING (with knapsack opportunity cost)
 STEP 14 -- RECOVERY PROBABILITY
 Lots run in IPL pool order.  Each team bids its MARGINAL value:
 what the player adds to its best remaining plan, net of what that
 spend forecloses.  English clearing: winner pays 2nd price + step.
=====================================================================
"""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
import os as _os

RPW=82.5
# REFITTED on the pWAR scale (was 6.87 against the old projected-wins scale).
# price = Rs3.28cr + Rs1.57cr x pWAR, n=196 sold, corr 0.302.
PRICE_PER_WAR=1.57; PRICE_INTERCEPT=3.28; BASE=0.30; STEP=0.20
EXPOSURE={'Opener':290.0,'No3':254.5,'Middle':215.0,'Lower':98.0,'Tail':13.0,
          'Powerplay':290.0,'Middle_b':270.0,'Death':180.0}
BOWL_EXP={'Powerplay':290.0,'Middle':270.0,'Death':180.0}
ADJACENT={'Opener':['Opener','No3'],'No3':['No3','Opener','Middle'],
          'Middle':['Middle','No3','Lower'],'Lower':['Lower','Middle','Tail'],'Tail':['Tail','Lower']}

# ---------------------------------------------------------------- inputs
def load_pool():
    p=pd.read_csv(_os.path.join(_DATA,'pool_2027_attributed.csv'))
    role_pos={'Bowler':'Tail','WK-Batter':'Middle','Batter':'Middle','Allrounder':'Lower'}
    p['bat_group']=p.bat_group.fillna(p.role.map(role_pos))
    p['kind']=np.where(p.role.isin(['Bowler','Allrounder']), p.kind.fillna('pace'), np.nan)
    p['capped_f']=p.capped_new.fillna(p.capped).fillna('UNCAPPED')
    p['bat_rate']=p.bat_rate.fillna(0.0); p['bowl_rate']=p.bowl_rate.fillna(-0.05)
    p['rel']=p.reliability_score.fillna(0.2)
    return p

def load_reqs():
    r=pd.read_csv(_os.path.join(_DATA,'slot_requirements_2027.csv'))
    r=r[r.role!='depth'].copy()
    r['exposure']=np.where(r.unit=='bowl', r.role.map(BOWL_EXP), r.role.map(EXPOSURE))
    r['req_id']=r.team+'|'+r.unit+'|'+r.role
    return r

def lot_order(pool, rng):
    """capped AR -> batters -> pacers -> spinners -> keepers, then the same uncapped."""
    tiers=[]
    for cap in ['CAPPED','UNCAPPED']:
        for label,mask in [
            ('AR',      (pool.role=='Allrounder')),
            ('BAT',     (pool.role=='Batter')),
            ('PACE',    (pool.role=='Bowler')&(pool.kind=='pace')),
            ('SPIN',    (pool.role=='Bowler')&(pool.kind=='spin')),
            ('WK',      (pool.role=='WK-Batter'))]:
            sub=pool[(pool.capped_f==cap)&mask]
            if len(sub): tiers.append(sub.sample(frac=1,random_state=int(rng.integers(1e9))))
    return pd.concat(tiers,ignore_index=True) if tiers else pool

# ---------------------------------------------------------------- bidding
def match_value(player, req):
    """WAR this player adds to that requirement, 0 if he cannot fill it."""
    if req.unit=='bowl':
        if player.role not in ('Bowler','Allrounder'): return 0.0
        gain=player.bowl_rate-req.incumbent_rate
    else:
        if player.role=='Bowler': return 0.0
        if req.role not in ADJACENT.get(player.bat_group,[player.bat_group]): return 0.0
        gain=player.bat_rate-req.incumbent_rate
    return max(gain,0.0)*req.exposure/RPW

def team_ceiling(player, open_reqs, purse, slots, committed):
    """Marginal value = best plan WITH him minus best plan WITHOUT him, capped by purse."""
    if slots<=0 or purse<BASE: return 0.0,None
    vals=[(match_value(player,r),r) for r in open_reqs.itertuples()]
    vals=[(v,r) for v,r in vals if v>0]
    if not vals: return 0.0,None
    v,best=max(vals,key=lambda x:x[0])
    # opportunity cost: money spent here cannot fund the next-best hole
    others=sorted([x[0] for x in vals if x[1].req_id!=best.req_id],reverse=True)
    reserve=0.0
    if slots>1 and others:
        reserve=min(others[0]*PRICE_PER_WAR*0.5, max(purse-BASE*(slots-1),0)*0.35)
    ceiling=max(v*PRICE_PER_WAR-reserve,0.0)
    return min(ceiling,purse), best

def run_auction(pool, reqs, purse0, slots0, sims=300, seed=0, noise=True):
    rng=np.random.default_rng(seed)
    fills={r.req_id:0 for r in reqs.itertuples()}
    qual={r.req_id:[] for r in reqs.itertuples()}
    spend={t:[] for t in purse0}
    for s in range(sims):
        purse=dict(purse0); slots=dict(slots0)
        R=reqs.copy(); R['open']=1
        P=pool.copy()
        if noise:   # low-reliability players are genuinely uncertain
            sd=(1-P.rel)*0.12
            P['bat_rate']=P.bat_rate+rng.normal(0,sd)
            P['bowl_rate']=P.bowl_rate+rng.normal(0,sd)
        lots=lot_order(P,rng)
        for pl in lots.itertuples():
            bids=[]
            for t in purse:
                oq=R[(R.team==t)&(R.open==1)]
                if not len(oq): continue
                c,best=team_ceiling(pl,oq,purse[t],slots[t],None)
                if c>=BASE and best is not None: bids.append((c,t,best))
            if not bids: continue
            bids.sort(reverse=True,key=lambda x:x[0])
            win_c,win_t,win_req=bids[0]
            price=min(max(bids[1][0]+STEP if len(bids)>1 else BASE, BASE), win_c, purse[win_t])
            purse[win_t]-=price; slots[win_t]-=1
            R.loc[R.req_id==win_req.req_id,'open']=0
            fills[win_req.req_id]+=1
            qual[win_req.req_id].append(pl.bowl_rate if win_req.unit=='bowl' else pl.bat_rate)
        for t in purse: spend[t].append(purse0[t]-purse[t])
    out=reqs.copy()
    out['p_fill']=[fills[r]/sims for r in out.req_id]
    out['e_quality']=[np.mean(qual[r]) if qual[r] else np.nan for r in out.req_id]
    sp=pd.DataFrame({'team':list(spend),'exp_spend':[np.mean(v) for v in spend.values()]})
    return out, sp
