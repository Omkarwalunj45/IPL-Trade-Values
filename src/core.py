import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 TRADE FRAMEWORK v2 -- built on the cricWAR-based pWAR
 Step 1: refit rupees-per-win against the NEW pWAR scale
 Step 2: role benchmarks (par pWAR per batting slot and bowling phase)
 Everything downstream imports from here.
=====================================================================
"""
import os, re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
DATA=_DATA
d=DATA
PWAR=_os.path.join(_DATA,'final_pwar.csv')
RPW=82.5
ALIAS={'Vaibhav Suryavanshi':'Vaibhav Sooryavanshi','Varun Chakaravarthy':'Varun Chakravarthy',
       'Philip Salt':'Phil Salt','Philip Dean Salt':'Phil Salt',
       'Rasikh Dar Salam':'Rasikh Salam','Rasikh Dar':'Rasikh Salam',
       'Rasikh Salam Dar':'Rasikh Salam'}
# line 25, in players()
d['player']=d.player.str.strip().replace(ALIAS)

# line 35, in price_model()
s['player']=s.playerName.str.strip().replace(ALIAS)

# line 89, in price_model2()
s['player']=s.playerName.str.strip().replace(ALIAS)
DATA=d
BAT_EXP={'Opener':290.0,'No3':254.5,'Middle':215.0,'Lower':98.0,'Tail':13.0}
BOWL_EXP={'Powerplay':290.0,'Middle':270.0,'Death':180.0}

def cr(x):
    if not isinstance(x,str) or str(x).strip() in ('--','','-','nan'): return np.nan
    v=float(re.sub(r'[^0-9.]','',str(x))); return v/100 if ' L' in str(x) else v

def players():
    d=pd.read_csv(PWAR)
    d['player']=d.player.str.strip()
    if 'pWAR_final' in d.columns: d['pWAR']=d.pWAR_final     # single source of truth
    return d

# ---------------------------------------------------------------- STEP 1
def price_model(P):
    """Regress what teams ACTUALLY paid on pWAR.  The old fit used a different
       scale entirely, so slope and intercept both have to be re-estimated."""
    a=pd.read_parquet(os.path.join(DATA,'ipl_auction_data_23_26.parquet'))
    s=a[a.auctionStatus.isin(['sold'])].copy()
    s['player']=s.playerName.str.strip()
    s['price']=s.auctionPrice.map(cr)
    m=s.merge(P[['player','pWAR','ipl_balls_wtd']],on='player',how='inner').dropna(subset=['price','pWAR'])
    m=m[m.ipl_balls_wtd>=150]
    X=np.column_stack([np.ones(len(m)),m.pWAR.values]); y=m.price.values
    beta,*_=np.linalg.lstsq(X,y,rcond=None)
    r=np.corrcoef(m.pWAR,y)[0,1]
    rng=np.random.default_rng(0); bs=[]
    for _ in range(2000):
        i=rng.integers(0,len(m),len(m))
        Xb=np.column_stack([np.ones(len(i)),m.pWAR.values[i]])
        bs.append(np.linalg.lstsq(Xb,y[i],rcond=None)[0][1])
    return dict(intercept=beta[0],slope=beta[1],corr=r,n=len(m),
                ci=(float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))))

def market_fair(pwar,pm): return pm['intercept']+pm['slope']*pwar

# ---------------------------------------------------------------- STEP 2
def benchmarks(P):
    """Par pWAR for each batting slot group and bowling phase group, from the
       players who actually occupy them.  Weighted by evidence, not headcount."""
    bat=P[P.bat_group.notna()&(P.ipl_balls_faced>0)]
    bb=(bat.groupby('bat_group').apply(lambda x: pd.Series({
        'n':len(x),'par_pWAR':np.average(x.pWAR,weights=x.ipl_balls_faced.clip(lower=1)),
        'exposure':BAT_EXP.get(x.name,150.0)}),include_groups=False).reset_index())
    bw=P[P.bowl_phase.notna()&(P.ipl_balls_bowled>0)].copy()
    rows=[]
    for ph in ['Powerplay','Middle','Death']:
        g=bw[bw.bowl_phase.str.contains(ph,na=False)]
        if len(g): rows.append(dict(phase=ph,n=len(g),
            par_pWAR=np.average(g.pWAR,weights=g.ipl_balls_bowled.clip(lower=1)),exposure=BOWL_EXP[ph]))
    return bb,pd.DataFrame(rows)

# ---------------------------------------------------------------- STEP 1b: richer price model
def archetype_features(P):
    """Scarcity and flexibility -- what a one-variable pWAR regression cannot see."""
    d=P.copy()
    d['nat']=np.where(d.overseas==1,'OS','IN')
    d['arch']=d.nat+'|'+d.role.fillna('?')+'|'+d.bat_group.fillna('none').astype(str)
    cnt=d.arch.value_counts()
    d['arch_n']=d.arch.map(cnt)
    d['scarcity']=1.0/np.sqrt(d.arch_n)              # rarer archetype -> higher
    # flexibility: how many distinct roles can he legally fill?
    nb=d.bowl_phase.fillna('').str.count(r'\+')+ (d.bowl_phase.notna()).astype(int)
    slots={'Opener':2,'No3':3,'Middle':3,'Lower':3,'Tail':2}
    d['bat_slots']=d.bat_group.map(slots).fillna(0)
    d['flex']=d.bat_slots+nb
    d['is_ar']=(d.role=='Allrounder').astype(int)
    d['is_bowl']=(d.role=='Bowler').astype(int)
    d['is_wk']=(d.role=='WK-Batter').astype(int)
    return d

def price_model2(P):
    a=pd.read_parquet(os.path.join(DATA,'ipl_auction_data_23_26.parquet'))
    s=a[a.auctionStatus=='sold'].copy(); s['player']=s.playerName.str.strip(); s['price']=s.auctionPrice.map(cr)
    D=archetype_features(P)
    m=s.merge(D,on='player',how='inner').dropna(subset=['price','pWAR'])
    m=m[m.ipl_balls_wtd>=150]
    cols=['pWAR','scarcity','flex','capped','overseas','is_ar','is_bowl','is_wk']
    X=np.column_stack([np.ones(len(m))]+[m[c].astype(float).values for c in cols]); y=m.price.values
    beta,*_=np.linalg.lstsq(X,y,rcond=None)
    pred=X@beta; r=np.corrcoef(pred,y)[0,1]
    return dict(cols=cols,beta=beta.tolist(),corr=r,n=len(m))

def market_fair2(row,pm2):
    b=pm2['beta']; v=b[0]
    for i,c in enumerate(pm2['cols']): v+=b[i+1]*float(row[c])
    return v
