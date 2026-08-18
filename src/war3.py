import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 WAR v3 -- cricWAR methodology, run on IPL and T20I, then combined.
 Season weights 1 / 2 / 3 for 2024 / 2025 / 2026 (applied as regression
 weights, which is mathematically identical to duplicating rows but
 without triplicating memory).
=====================================================================
"""
import os as _os, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')

from names import ALIAS, fix
RPW=82.5; SW={2024:1.0,2025:2.0,2026:3.0}

def _prep(df, comp):
    d=df.copy()
    if 'year' in d.columns: d=d.rename(columns={'year':'season'})
    d=d[d.season.between(2024,2026)].copy()
    d['bat']=fix(d.bat)
    d['bowl']=fix(d.bowl)
    for c in ['wide','noball','byes','legbyes']:
        if c not in d.columns: d[c]=0
        d[c]=pd.to_numeric(d[c],errors='coerce').fillna(0)
    d['score']=pd.to_numeric(d.score,errors='coerce').fillna(0)
    if 'batruns' not in d.columns:
        d['batruns']=(d.score-d.wide-d.noball-d.byes-d.legbyes).clip(lower=0)
    if 'ballfaced' not in d.columns:
        d['ballfaced']=(d.wide==0).astype(int)     # a wide is not a ball faced
    d['out']=pd.to_numeric(d['out'],errors='coerce').fillna(0)
    d['ov']=pd.to_numeric(d.over,errors='coerce').fillna(0).astype(int).clip(0,19)
    d['w']=(d.groupby(['p_match','inns'])['out'].cumsum()-d['out']).clip(0,9).astype(int)
    d['sw']=d.season.map(SW).fillna(1.0)
    d['comp']=comp
    if 'bowl_kind' not in d.columns: d['bowl_kind']='unknown'
    if 'bat_hand' not in d.columns: d['bat_hand']='unknown'
    return d

def load_both():
    ipl=_prep(pd.read_parquet(_os.path.join(_DATA,'ipl_df__4_.parquet')),'IPL')
    t20=_prep(pd.read_parquet(_os.path.join(_DATA,'IPL_APP_T20I_2__3_.parquet')),'T20I')
    return ipl,t20

# ---------------------------------------------------------------- cricWAR core
def raa(d):
    """theta -> run value -> conservation -> leverage -> contextual regression -> RAA."""
    th=d.groupby(['ov','w']).apply(lambda x: np.average(x.score,weights=x.sw),include_groups=False).rename('theta')
    d=d.join(th,on=['ov','w'])
    # run expectancy of the remainder, to price a wicket
    d=d.sort_values(['p_match','inns','ov','ball'])
    tot=d.groupby(['p_match','inns']).score.transform('sum')
    cum=d.groupby(['p_match','inns']).score.cumsum()
    d['RE']=tot-cum+d.score
    RE=d.groupby(['ov','w']).apply(lambda x: np.average(x.RE,weights=x.sw),include_groups=False).rename('RE_state')
    d=d.join(RE,on=['ov','w'])
    nx=RE.reset_index(); nx['w']=nx.w-1; nx=nx.rename(columns={'RE_state':'RE_next'})
    d=d.merge(nx,on=['ov','w'],how='left')
    d['WV']=(d.RE_state-d.RE_next).clip(lower=0).fillna(0)
    d['delta']=d.batruns-d.theta-d['out']*d.WV                 # batter's raw run value
    d['extras']=(d.score-d.batruns).clip(lower=0)
    LI=(d.theta/np.average(d.theta,weights=d.sw)).clip(0.35,3.0)
    d['dl_bat']=d.delta/LI
    d['dl_bowl']=-(d.delta+d.extras)/LI                        # CONSERVATION
    X=pd.get_dummies(d[['ground']],drop_first=True).astype(float)
    X['inns2']=(d.inns==2).astype(float)
    X['spin']=d.bowl_kind.astype(str).str.contains('spin',case=False).astype(float)
    X['lhb']=d.bat_hand.astype(str).str.upper().str.startswith('L').astype(float)
    X['c']=1.0; Xv=X.values; wt=d.sw.values
    for src,dst in [('dl_bat','e_bat'),('dl_bowl','e_bowl')]:
        y=d[src].fillna(0).values
        beta,*_=np.linalg.lstsq(Xv*wt[:,None],y*wt,rcond=None)
        d[dst]=y-Xv@beta
    return d

def vorp(d, n_teams, n_bat=7, n_bowl=6):
    """League level = top 8N batters and top 6N bowlers by weighted playing time.
       cricWAR uses 8N for both, but a T20 side fields eleven batters and only five
       or six bowling options, so 8N bowlers sets the bar far too low."""
    bt=d.groupby('bat').apply(lambda x: pd.Series({'b':(x.ballfaced*x.sw).sum(),'r':(x.e_bat*x.sw).sum()}),include_groups=False)
    bw=d.groupby('bowl').apply(lambda x: pd.Series({'b':(x.ballfaced*x.sw).sum(),'r':(x.e_bowl*x.sw).sum()}),include_groups=False)
    out={}
    for tag,g,k in [('bat',bt,n_bat),('bowl',bw,n_bowl)]:
        g=g[g.b>0].sort_values('b',ascending=False)
        rep=g.iloc[k*n_teams:]
        rate=rep.r.sum()/max(rep.b.sum(),1)
        g=g.copy(); g['vorp']=g.r-rate*g.b; g['rate']=g.vorp/g.b
        out[tag]=(g,rate)
    return out

def war_table(d, n_teams, label):
    o=vorp(d,n_teams)
    b=o['bat'][0][['b','vorp','rate']].rename(columns={'b':'bf','vorp':'v_bat','rate':'rate_bat'})
    w=o['bowl'][0][['b','vorp','rate']].rename(columns={'b':'bb','vorp':'v_bowl','rate':'rate_bowl'})
    t=b.join(w,how='outer').fillna(0)
    t['balls']=t.bf+t.bb; t['VORP']=t.v_bat+t.v_bowl
    t['rate']=t.VORP/t.balls.replace(0,np.nan)
    t['WAR_'+label]=t.VORP/RPW
    t=t.reset_index(); t.columns=['player']+list(t.columns[1:]); return t
