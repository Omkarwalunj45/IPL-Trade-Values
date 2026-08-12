import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
A) Empirical price model fitted on real mini-auction outcomes (2024 + 2026)
B) Bidder-specific valuation noise -> winner's curse -> endogenous price explosions
"""
import numpy as np, pandas as pd, re, warnings; warnings.filterwarnings('ignore')
import os as _os

RPW=82.5; ALIAS={'Vaibhav Suryavanshi':'Vaibhav Sooryavanshi'}

def cr(x):
    if not isinstance(x,str) or str(x).strip() in ('--','','-','nan'): return np.nan
    v=float(re.sub(r'[^0-9.]','',str(x))); return v/100 if ' L' in str(x) else v

def point_in_time_proj(year):
    w=pd.read_parquet(_os.path.join(_DATA,'war_final.parquet')); w['player']=w.player.replace(ALIAS)
    w=w.groupby(['season','player'],as_index=False).agg(bf=('bf','sum'),bb=('bb','sum'),
      RAA_bat=('RAA_bat','sum'),REP_bat=('REP_bat','sum'),RAA_bowl=('RAA_bowl','sum'),REP_bowl=('REP_bowl','sum'))
    w['bat_RAR']=w.RAA_bat+w.REP_bat; w['bowl_RAR']=w.RAA_bowl+w.REP_bowl
    h=w[w.season<year].copy()
    if h.empty: return pd.DataFrame(columns=['player','proj_WAR','prior_exp'])
    LGB=h.bat_RAR.sum()/max(h.bf.sum(),1); LGW=h.bowl_RAR.sum()/max(h.bb.sum(),1)
    h['yw']=h.season.map({year-1:5,year-2:4,year-3:3,year-4:2}).fillna(1)
    g=h.groupby('player').apply(lambda x: pd.Series({
        'pb':((x.yw*x.bat_RAR).sum()+887*LGB)/((x.yw*x.bf).sum()+887),
        'pw':((x.yw*x.bowl_RAR).sum()+475*LGW)/((x.yw*x.bb).sum()+475),
        'ebf':(x.yw*x.bf).sum()/x.yw.sum(),'ebb':(x.yw*x.bb).sum()/x.yw.sum(),
        'prior_exp':x.bf.sum()+x.bb.sum()}),include_groups=False).reset_index()
    g['proj_WAR']=(g.pb*g.ebf+g.pw*g.ebb)/RPW
    return g[['player','proj_WAR','prior_exp']]

def fit_price_model():
    """log(price) ~ projected WAR + capped + overseas + role.  Residuals are RESAMPLED,
       which is how the fat right tail (Cameron Green) enters without being hardcoded."""
    a=pd.read_parquet(_os.path.join(_DATA,'ipl_auction_data_23_26.parquet'))
    rows=[]
    for y in [2024,2026]:
        s=a[(a.year==y)&(a.auctionStatus=='sold')].copy()
        s['player']=s.playerName.str.strip().replace(ALIAS)
        s['price']=s.auctionPrice.map(cr); s['base']=s.basePrice.map(cr)
        s['capped']=(s.cappedStatus=='CAPPED').astype(int)
        s['os']=s.isPlayerOverseas.notna().astype(int)
        s=s.merge(point_in_time_proj(y),on='player',how='left')
        s['proj_WAR']=s.proj_WAR.fillna(0.0); s['has_ipl']=(s.prior_exp.fillna(0)>=100).astype(int)
        rows.append(s[['player','price','base','capped','os','role','proj_WAR','has_ipl']])
    d=pd.concat(rows,ignore_index=True).dropna(subset=['price','base'])
    d['y']=np.log(d.price/d.base)                      # multiple of base price, log scale
    X=pd.get_dummies(d[['role']],drop_first=True).astype(float)
    X['proj']=d.proj_WAR.values; X['capped']=d.capped.values; X['os']=d.os.values
    X['has_ipl']=d.has_ipl.values; X['const']=1.0
    beta,*_=np.linalg.lstsq(X.values,d.y.values,rcond=None)
    d['fit']=X.values@beta; d['resid']=d.y-d.fit
    return dict(beta=beta,cols=list(X.columns),resid=d.resid.values,data=d,
                r2=1-((d.y-d.fit)**2).sum()/((d.y-d.y.mean())**2).sum())

def price_draw(model, proj_WAR, base, capped, os_, role, rng, n_bidders):
    """Predicted multiple of base, plus a resampled residual.  More bidders -> the
       winner is the one who most overestimates, so we take the max of n draws."""
    cols=model['cols']; b=model['beta']
    x=np.zeros(len(cols))
    for i,c in enumerate(cols):
        if c=='const': x[i]=1
        elif c=='proj': x[i]=proj_WAR
        elif c=='capped': x[i]=capped
        elif c=='os': x[i]=os_
        elif c=='has_ipl': x[i]=1
        elif c.startswith('role_'): x[i]=1.0 if c=='role_'+str(role) else 0.0
    mu=float(x@b)
    k=max(int(n_bidders),1)
    eps=rng.choice(model['resid'],size=k).max()        # winner's curse: max of k draws
    return float(base*np.exp(mu+eps))
