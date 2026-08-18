import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 CORRECTED PURSE / SLOT / SURPLUS PIPELINE
 Order of events is FIXED and cannot be reversed:
   1. carry-over from the 2026 auction
   2. + Rs6cr BCCI top-up
   3. TRADE WINDOW   : + salary of players leaving, - negotiated salary of players arriving
   4. RELEASE DEADLINE: apply the release list, with any TRADED player struck from it
   5. -> auction purse and squad slots
 A traded player must never also be counted as a release: that double-credits his salary.
=====================================================================
"""
import sys, os as _o; sys.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
import numpy as np, pandas as pd, re, warnings; warnings.filterwarnings('ignore')
from price2 import draw as _px_draw
import os as _os


from names import ALIAS, fix
RPW=82.5; PPW=1.57; MAX_MARKET=27.0   # PPW refitted on pWAR
SLAB_CAPPED=11.0; SLAB_UNCAPPED=4.0
PERSIST=0.296; AGE_COEF=-0.00200; DISCOUNT=0.88
K_BAT,K_BOWL=887,475; MAX_SQUAD=25; TOPUP=6.0
CARRY={'CSK':2.40,'DC':0.35,'GT':1.95,'KKR':0.45,'LSG':4.55,
       'MI':0.55,'PBKS':3.50,'RR':2.65,'RCB':0.25,'SRH':5.45}
def _load_price_model():
    import json as _json, numpy as _np
    with open(_os.path.join(_DATA,'price_model.json')) as _f: _m=_json.load(_f)
    for _k in ('b_contest','b_mult','resid'):
        if _k in _m: _m[_k]=_np.asarray(_m[_k],dtype=float)
    return _m
_PX=_load_price_model(); _PX['resid']=_PX['resid']*0.75

# ---------------------------------------------------------------- inputs (two files only)
def load_state():
    ros=pd.read_csv(_os.path.join(_DATA,'rosters_2027_scored.csv'))
    ros=ros[ros.player!='Ajinkya Rahane'].copy()
    ros['player']=fix(ros.player)
    ros=ros[['team','player','role','sal']].rename(columns={'sal':'salary'}).drop_duplicates(['team','player'])
    rel=pd.read_csv(_os.path.join(_DATA,'release_list_2027.csv'))
    rel['player']=fix(rel.player)
    rel=rel[['team','player','role','sal']].rename(columns={'sal':'salary'}).drop_duplicates(['team','player'])
    pool=pd.read_csv(_os.path.join(_DATA,'pool_2027_scored.csv'))
    pool['player']=fix(pool.player)
    # PRE-release squad = post-release roster + the players we predict will be released
    squad=pd.concat([ros.assign(status='keep'),rel.assign(status='release')],ignore_index=True)
    squad=squad.drop_duplicates(['team','player'])
    return squad, rel, pool

# ---------------------------------------------------------------- the sequence
def purse_and_slots(squad, rel, trades=None):
    """trades = [{'from':'MI','to':'CSK','player':'Hardik Pandya','new_salary':10.0}, ...]"""
    trades=trades or []
    traded=set(t['player'] for t in trades)
    rows=[]
    for tm in sorted(CARRY):
        sq=squad[squad.team==tm]
        p=CARRY[tm]; step=[('carry_over',CARRY[tm],p)]
        p+=TOPUP; step.append(('bcci_topup',TOPUP,p))
        out_sal=sum(float(sq[sq.player==t['player']].salary.iloc[0])
                    for t in trades if t['from']==tm and (sq.player==t['player']).any())
        in_sal=sum(float(t['new_salary']) for t in trades if t['to']==tm)
        p+=out_sal; step.append(('trade_out',out_sal,p))
        p-=in_sal;  step.append(('trade_in',-in_sal,p))
        # releases, with traded players STRUCK OUT
        r=rel[(rel.team==tm)&(~rel.player.isin(traded))]
        freed=float(r.salary.sum()); n_rel=len(r)
        p+=freed; step.append(('releases',freed,p))
        n_out=sum(1 for t in trades if t['from']==tm and (sq.player==t['player']).any())
        n_in=sum(1 for t in trades if t['to']==tm)
        final_squad=len(sq)-n_out+n_in-n_rel
        rows.append(dict(team=tm,carry=CARRY[tm],topup=TOPUP,trade_out=out_sal,trade_in=in_sal,
            releases=freed,n_released=n_rel,purse=p,squad_pre=len(sq),
            squad_final=final_squad,slots=max(MAX_SQUAD-final_squad,0)))
    return pd.DataFrame(rows).set_index('team')

# ---------------------------------------------------------------- surplus
def projections(squad, pool):
    live=pd.concat([squad[['player','role','salary']].assign(on_roster=1),
                    pool[['player','role','sal']].rename(columns={'sal':'salary'}).assign(on_roster=0)],
                   ignore_index=True).drop_duplicates('player')
    # Back-fill salary from ANY auction year and ANY status (retained / traded / rtm),
    # then by surname when the spelling differs ("Varun Chakaravarthy", "Philip Salt").
    _a=pd.read_parquet(_os.path.join(_DATA,'ipl_auction_data_23_26.parquet'))
    _a=_a[_a.auctionStatus.isin(['sold','retained','traded','rtm'])].copy()
    _a['_p']=fix(_a.playerName)
    def _cr2(x):
        if not isinstance(x,str) or str(x).strip() in ('--','','-','nan'): return np.nan
        v=float(re.sub(r'[^0-9.]','',str(x))); return v/100 if ' L' in str(x) else v
    _a['_s']=_a.auctionPrice.map(_cr2).fillna(_a.basePrice.map(_cr2))
    _last=_a.sort_values('year').groupby('_p')['_s'].last()
    live['salary']=live.salary.fillna(live.player.map(_last))
    _key=lambda n:(str(n).split()[-1].lower(), str(n).split()[0][0].lower())
    _alt={}
    for _p,_v in _last.items(): _alt.setdefault(_key(_p),_v)
    _need=live.salary.isna()
    live.loc[_need,'salary']=[_alt.get(_key(p),np.nan) for p in live.loc[_need,'player']]
    a=pd.read_parquet(_os.path.join(_DATA,'ipl_auction_data_23_26.parquet'))
    a=a[a.year==2026].copy(); a['player']=fix(a.playerName)
    f=a.drop_duplicates('player').set_index('player')
    live['capped']=live.player.map((f.cappedStatus=='CAPPED').astype(int)).fillna(0).astype(int)
    live['overseas']=live.player.map(f.isPlayerOverseas.notna().astype(int)).fillna(0).astype(int)
    c=pd.read_csv(_os.path.join(_DATA,'cricinfo_player_profiles.csv')); c=c[c.gender=='M']
    m1=c[c.display_name.isin(set(live.player))].assign(player=lambda d:d.display_name)
    m2=c[(~c.display_name.isin(set(m1.player)))&(c.full_name.isin(set(live.player)))].assign(player=lambda d:d.full_name)
    live=live.merge(pd.concat([m1,m2]).drop_duplicates('player')[['player','age']],on='player',how='left')
    live.loc[live.player=='Rashid Khan','age']=27
    w=pd.read_parquet(_os.path.join(_DATA,'war_final.parquet')); w['player']=fix(w.player)
    # recency weighting 5/4/3/2 for 2026/25/24/23: without it a strong season three
    # years ago keeps carrying a player whose last two have been ordinary
    # Recency weighting decides the RATE; the TRUE ball count decides how much that rate
    # is trusted.  Weighting must never inflate the sample size, or a player with one
    # good recent season looks as reliable as one with four.
    w=w[w.season>=2025]          # last TWO seasons only: sample size and recency together
    _YW={2026:3,2025:2}
    w['_yw']=w.season.map(_YW).fillna(1.0)
    for _c in ['RAA_bat','REP_bat','RAA_bowl','REP_bowl']: w[_c+'_w']=w[_c]*w['_yw']
    w['bf_w']=w.bf*w['_yw']; w['bb_w']=w.bb*w['_yw']
    g=w.groupby('player',as_index=False).agg(
        bf=('bf','sum'), bb=('bb','sum'),                       # TRUE balls -> reliability
        bf_w=('bf_w','sum'), bb_w=('bb_w','sum'),
        RAA_bat=('RAA_bat_w','sum'), REP_bat=('REP_bat_w','sum'),
        RAA_bowl=('RAA_bowl_w','sum'), REP_bowl=('REP_bowl_w','sum'))
    # recency-weighted rate, then re-expressed over the player's ACTUAL workload
    g['RAA_bat']=(g.RAA_bat+g.REP_bat)/g.bf_w.replace(0,np.nan)*g.bf
    g['RAA_bowl']=(g.RAA_bowl+g.REP_bowl)/g.bb_w.replace(0,np.nan)*g.bb
    g['REP_bat']=0.0; g['REP_bowl']=0.0
    w=g.fillna({'RAA_bat':0,'RAA_bowl':0})
    w['bat_RAR']=w.RAA_bat+w.REP_bat; w['bowl_RAR']=w.RAA_bowl+w.REP_bowl
    d=live.merge(w[['player','bf','bb','bat_RAR','bowl_RAR']],on='player',how='left').fillna(
        {'bf':0,'bb':0,'bat_RAR':0,'bowl_RAR':0})
    # mid-season replacements and traded players arrive with a blank role -> infer it
    # from what they actually did, otherwise their projection comes back NaN
    miss=d.role.isna()
    if miss.any():
        share=d.bf/(d.bf+d.bb).replace(0,np.nan)
        d.loc[miss,'role']=np.where(share[miss]>=0.75,'Batter',
                            np.where(share[miss]<=0.25,'Bowler','Allrounder'))
    rb=d.groupby('role').apply(lambda x: x.bat_RAR.sum()/max(x.bf.sum(),1),include_groups=False)
    rw=d.groupby('role').apply(lambda x: x.bowl_RAR.sum()/max(x.bb.sum(),1),include_groups=False)
    d['rb']=d.role.map(rb); d['rw']=d.role.map(rw)
    d['bat_rate']=(d.bat_RAR+K_BAT*d.rb)/(d.bf+K_BAT)
    d['bowl_rate']=(d.bowl_RAR+K_BOWL*d.rw)/(d.bb+K_BOWL)
    # A specialist bowler is picked to bowl 24 balls, not to face 3 or 4 at number 11.
    # Crediting or debiting that batting is pure noise, so his batting exposure is 0.
    E={'Batter':240,'WK-Batter':240,'Allrounder':190,'Bowler':0}
    B={'Bowler':280,'Allrounder':160,'Batter':0,'WK-Batter':0}
    d['proj2027']=(d.bat_rate*d.role.map(E).fillna(150)
                  +d.bowl_rate*d.role.map(B).fillna(0))/RPW
    return d[d.bf+d.bb>0].copy(), rb

def surplus(d, rb, rng, salary_override=None):
    salary_override=salary_override or {}
    out=[]
    for r in d.itertuples():
        sal=float(salary_override.get(r.player, r.salary)) if pd.notna(r.salary) or r.player in salary_override else np.nan
        if not np.isfinite(sal): continue
        base=2.00 if r.capped else 0.30
        mkt=min(float(np.median([_px_draw(_PX,max(r.proj2027,0),base,int(r.capped),int(r.overseas),
              r.role,rng,extra_demand=0.6,has_ipl=1) for _ in range(60)])),MAX_MARKET)
        fair=r.proj2027*PPW
        y1=(fair-sal) if fair>=sal else max(fair-sal,mkt-sal)
        strike=SLAB_CAPPED if r.capped else SLAB_UNCAPPED
        age=r.age if pd.notna(r.age) else 28
        rate=r.bat_rate; mean=rb.get(r.role,0.13); expo=(r.proj2027*RPW)/max(rate,1e-6) if rate>0 else 200
        opt=0.0
        for i in range(1,4):
            rr=rate
            for k in range(i): rr=mean+PERSIST*(rr-mean)+AGE_COEF*(age+k)
            opt+=max(max(rr,0)*expo/RPW*PPW-strike,0)*(DISCOUNT**i)   # rate x balls = RUNS -> /RPW = WINS
        out.append(dict(player=r.player,role=r.role,age=age,capped=r.capped,on_roster=r.on_roster,
            salary=round(sal,2),proj2027=round(r.proj2027,3),market=round(mkt,2),
            y1=round(y1,2),option=round(opt,2),total=round(y1+opt,2)))
    return pd.DataFrame(out).sort_values('total',ascending=False)
