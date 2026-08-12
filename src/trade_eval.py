import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 STEP 14 (rebuilt) -- TRADE EVALUATION
 A trade changes the ROSTER.  So we re-run the whole chain on the
 post-trade squad:  roster -> XII optimiser -> vacancies -> auction.
 The incoming player OCCUPIES a slot; he is never a null void.
=====================================================================
"""
import sys, os as _o; sys.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from ipl_trade_optimizer import build_players, optimize_xii, BAT_EXP, BOWL_EXP, RPW
from fast import load_pool, value_matrix, lot_order, PRICE_PER_WAR, BASE, STEP
from auction import PRICE_INTERCEPT
from price2 import draw as price_draw
import os as _os

def _load_price_model():
    import json as _json, numpy as _np
    with open(_os.path.join(_DATA,'price_model.json')) as _f: _m=_json.load(_f)
    for _k in ('b_contest','b_mult','resid'):
        if _k in _m: _m[_k]=_np.asarray(_m[_k],dtype=float)
    return _m
_PX=_load_price_model(); _PX['resid']=_PX['resid']*0.75          # shrink: 57 contested lots overstate the log-variance
def _base_price_pool():
    '''Empirical base-price slabs, drawn conditional on capped status.'''
    import re as _re
    a=pd.read_parquet(_os.path.join(_DATA,'ipl_auction_data_23_26.parquet'))
    a=a[a.year.isin([2024,2026])&a.auctionStatus.isin(['sold','unsold'])].copy()
    def _cr(x):
        if not isinstance(x,str) or str(x).strip() in ('--','','-','nan'): return np.nan
        v=float(_re.sub(r'[^0-9.]','',str(x))); return v/100 if ' L' in str(x) else v
    a['b']=a.basePrice.map(_cr)
    return {'CAPPED':a[(a.cappedStatus=='CAPPED')].b.dropna().values,
            'UNCAPPED':a[(a.cappedStatus!='CAPPED')].b.dropna().values}
_BASE=_base_price_pool()

ALIAS={'Vaibhav Suryavanshi':'Vaibhav Sooryavanshi'}
CAPTAINS={'CSK':'Ruturaj Gaikwad','GT':'Shubman Gill','RCB':'Rajat Patidar','RR':'Riyan Parag',
          'PBKS':'Shreyas Iyer','DC':'Axar Patel','SRH':'Pat Cummins'}
# Batting requirements exist only to No.7.  Slot 8 is a bowling all-rounder and 9-12
# are specialist bowlers: you never go to the auction looking for a batter at nine.
GRP={1:'Opener',2:'Opener',3:'No3',4:'Middle',5:'Middle',6:'Lower',7:'Lower'}

def bowl_kind_map():
    ipl=pd.read_parquet(_os.path.join(_DATA,'ipl_df__4_.parquet'))
    ipl['bowl']=ipl.bowl.str.strip().replace(ALIAS)
    g=ipl.groupby(['bowl','bowl_kind']).ballfaced.sum().reset_index()
    g=g.loc[g.groupby('bowl').ballfaced.idxmax()]
    g['kind']=np.where(g.bowl_kind.astype(str).str.contains('spin',case=False),'spin','pace')
    return dict(zip(g.bowl,g.kind))

def par_table():
    h=pd.read_csv(_os.path.join(_DATA,'hole_occupants_2027.csv'))
    p=h.groupby(['unit','role']).par.mean()
    return p.to_dict()

def rosters():
    r=pd.read_csv(_os.path.join(_DATA,'rosters_2027_scored.csv'))
    return r[r.player!='Ajinkya Rahane'][['team','player']]

def squad_of(P, roster, team, add=(), drop=(), fillers=True):
    names=set(roster[roster.team==team].player) - set(drop) | set(add)
    sq=P[P.player.isin(names)].reset_index(drop=True)
    if fillers:
        # a team can always field a replacement-level body; without this the ILP can be
        # INFEASIBLE (e.g. KKR after Rahane retired had only one eligible opener), which
        # would silently remove the team from the auction entirely.
        rows=[]
        for s in range(1,9):
            rows.append(dict(player='__FILL%d__'%s, nat_slot=s, bat_rate=0.0, bowl_rate=np.nan,
                phases=set(), can_bowl=False, overseas=0, is_wk=(s in (4,5)),
                role='Batter', bf_tot=0, bb_tot=0, sal_cr=0.30, last_team=team))
        rows.append(dict(player='__FILLBOWL__', nat_slot=9, bat_rate=0.0, bowl_rate=0.0,
            phases={'Powerplay','Middle','Death'}, can_bowl=True, overseas=0, is_wk=False,
            role='Bowler', bf_tot=0, bb_tot=0, sal_cr=0.30, last_team=team))
        sq=pd.concat([sq,pd.DataFrame(rows)],ignore_index=True)
    return sq, names

def xii_and_gaps(P, roster, team, par, add=(), drop=()):
    """Optimise the post-trade XII, then read gaps off the ACTUAL occupants."""
    sq,_=squad_of(P,roster,team,add,drop)
    lock={CAPTAINS[team]:s for s in [None]} if False else {}
    xii,war,msg=optimize_xii(sq)
    if xii is None: return None,np.nan,pd.DataFrame(),msg
    rows=[]
    for r in xii.itertuples():
        if int(r.bat_slot) in GRP:
            g=GRP[int(r.bat_slot)]; pr=par.get(('bat',g),0.0)
            rows.append(dict(team=team,unit='bat',role=g,occupant=r.player,rate=r.bat_rate,
                par=pr,exposure=BAT_EXP[int(r.bat_slot)],deficit=max(pr-r.bat_rate,0)))
        if pd.notna(r.bowl_slot):
            for ph in [x for x in str(r.phases).split(',') if x]:
                pr=par.get(('bowl',ph),0.0); rt=r.bowl_rate if pd.notna(r.bowl_rate) else 0
                rows.append(dict(team=team,unit='bowl',role=ph,occupant=r.player,rate=rt,
                    par=pr,exposure=BOWL_EXP[int(r.bowl_slot)]/max(len(str(r.phases).split(',')),1),
                    deficit=max(pr-rt,0)))
    g=pd.DataFrame(rows)
    g=(g.sort_values('deficit',ascending=False).groupby(['team','unit','role'],as_index=False).first())
    KM=bowl_kind_map()
    g['req_kind']=np.where(g.unit=='bowl', g.occupant.map(KM), None)
    g['war_gap']=g.deficit*g.exposure/RPW
    return xii,war,g[g.war_gap>0.01],msg

ADJ={'Opener':['No3'],'No3':['Opener','Middle'],'Middle':['No3','Lower'],
     'Lower':['Middle','Tail'],'Tail':['Lower']}
# bowling phases are adjacent too: a displaced powerplay bowler can take middle overs,
# a death bowler can take middle -- but ONLY if he is the same kind (pace / spin).
ADJ_PH={'Powerplay':['Middle'],'Middle':['Powerplay','Death'],'Death':['Middle']}

def cascade(reqs, rates, j_bought, new_rate, open_mask):
    """
    CHEAP RECALIBRATION.  Buying a player at slot j displaces the incumbent, who can
    shift +/-1 to an adjacent slot on the SAME team.  If he beats the man there, that
    slot upgrades and its requirement closes or shrinks.  One-step cascade: captures
    the main second-order effect at ~1/50th the cost of re-solving the whole ILP.
    """
    tm=reqs.team.values[j_bought]; ro=reqs.role.values[j_bought]; un=reqs.unit.values[j_bought]
    displaced=rates[j_bought]
    rates[j_bought]=new_rate
    if un=='bat':
        for k in np.where((reqs.team.values==tm)&(reqs.unit.values=='bat')&open_mask)[0]:
            if reqs.role.values[k] in ADJ.get(ro,[]) and displaced>rates[k]:
                rates[k]=displaced
                if rates[k]>=reqs.par.values[k]: open_mask[k]=False
                break
    else:
        kind=reqs.req_kind.values[j_bought] if 'req_kind' in reqs.columns else None
        for k in np.where((reqs.team.values==tm)&(reqs.unit.values=='bowl')&open_mask)[0]:
            same_kind = (kind is None) or (str(reqs.req_kind.values[k])==str(kind))
            if reqs.role.values[k] in ADJ_PH.get(ro,[]) and same_kind and displaced>rates[k]:
                rates[k]=displaced
                if rates[k]>=reqs.par.values[k]: open_mask[k]=False
                break
    return rates, open_mask

def auction_recovery(pool, reqs, purse0, slots0, sims=120, seed=5):
    """Return P(fill), P(at par), expected quality per requirement."""
    reqs=reqs.reset_index(drop=True)
    reqs['incumbent_rate']=reqs.rate
    rng=np.random.default_rng(seed)
    teams=list(purse0); tix={t:i for i,t in enumerate(teams)}
    rt=reqs.team.map(tix).values; rpar=reqs.par.values
    fills=np.zeros(len(reqs)); atpar=np.zeros(len(reqs)); qual=[[] for _ in range(len(reqs))]
    rel=pool.rel.values
    for s in range(sims):
        Pp=pool.copy(); sd=(1-rel)*0.12
        Pp['bat_rate']=Pp.bat_rate.values+rng.normal(0,sd); Pp['bowl_rate']=Pp.bowl_rate.values+rng.normal(0,sd)
        V=value_matrix(Pp,reqs); order=lot_order(Pp.assign(_i=np.arange(len(Pp))),rng)._i.values
        purse=np.array([purse0[t] for t in teams],float); slots=np.array([slots0[t] for t in teams],float)
        openr=np.ones(len(reqs),bool); live_rates=reqs.incumbent_rate.values.copy()
        for i in order:
            v=V[i]*openr; bids=[]
            for k in range(len(teams)):
                if slots[k]<=0 or purse[k]<BASE: continue
                m=(rt==k)&openr
                if not m.any(): continue
                vals=v[m]
                if vals.max()<=0: continue
                jb=np.where(m)[0][vals.argmax()]
                # a team must pay the market floor to sign anyone, so the ceiling is
                # intercept + marginal value, not marginal value alone
                c=min(PRICE_INTERCEPT+vals.max()*PRICE_PER_WAR,purse[k])
                if c>=BASE: bids.append((c,k,jb))
            if not bids: continue
            bids.sort(reverse=True); c1,k1,j1=bids[0]
            # market price from the fitted hurdle model; demand shifts P(contested)
            row=Pp.iloc[i]
            _bp=_BASE.get('CAPPED' if str(row.capped_f)=='CAPPED' else 'UNCAPPED')
            base=float(rng.choice(_bp)) if len(_bp) else 0.30
            _rt=float(row.bat_rate if reqs.unit.values[j1]=='bat' else row.bowl_rate)
            _pw=max(_rt,0.0)*float(reqs.exposure.values[j1])/RPW      # real projected WAR
            mkt=price_draw(_PX, _pw,
                           base, 1 if row.capped_f=='CAPPED' else 0, 1 if str(row.overseas) in ('1','OS','True','Overseas') else 0,
                           row.role, rng, extra_demand=0.35*max(len(bids)-1,0),
                           has_ipl=1 if (row.ipl_bf+row.ipl_bb)>=100 else 0)
            price=min(max(mkt,BASE), c1, purse[k1])
            if mkt>c1: continue          # market ran past what the team can justify -> walks away
            purse[k1]-=price; slots[k1]-=1; openr[j1]=False; fills[j1]+=1
            q=Pp.bowl_rate.values[i] if reqs.unit.values[j1]=='bowl' else Pp.bat_rate.values[i]
            qual[j1].append(q)
            if q>=rpar[j1]: atpar[j1]+=1
            live_rates,openr=cascade(reqs,live_rates,j1,q,openr)   # squad recalibrates
            V=value_matrix(Pp,reqs.assign(incumbent_rate=live_rates))
    o=reqs.copy(); o['p_fill']=fills/sims; o['p_at_par']=atpar/sims
    o['e_quality']=[np.mean(q) if q else np.nan for q in qual]
    o['recovery_WAR']=np.where(o.e_quality.notna(),
        o.p_fill*np.maximum(o.e_quality-o.rate,0)*o.exposure/RPW,0.0)
    return o

def evaluate(P, roster, pool, purse0, slots0, team_a, team_b, a_gets, b_gets, par, sims=120):
    res={}
    for tm,gets,gives in [(team_a,a_gets,b_gets),(team_b,b_gets,a_gets)]:
        _,w0,g0,_=xii_and_gaps(P,roster,tm,par)
        _,w1,g1,_=xii_and_gaps(P,roster,tm,par,add=gets,drop=gives)
        res[tm]=dict(xii_before=w0,xii_after=w1,gaps_before=g0,gaps_after=g1)
    all_g=pd.concat([res[t]['gaps_after'] for t in res]+[
        xii_and_gaps(P,roster,t,par)[2] for t in purse0 if t not in res],ignore_index=True)
    rec=auction_recovery(pool,all_g,purse0,slots0,sims=sims)
    for t in res:
        r=rec[rec.team==t]
        res[t]['recovery']=r.recovery_WAR.sum()
        res[t]['detail']=r[['unit','role','occupant','rate','par','p_fill','p_at_par','e_quality','recovery_WAR']]
        res[t]['net']=res[t]['xii_after']+res[t]['recovery']-res[t]['xii_before']
    return res
