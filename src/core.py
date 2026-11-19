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
PWAR=_os.path.join(_DATA,'final_pwar.csv')
RPW=82.5
from names import ALIAS, fix
BAT_EXP={'Opener':290.0,'No3':254.5,'Middle':215.0,'Lower':98.0,'Tail':13.0}
BOWL_EXP={'Powerplay':290.0,'Middle':270.0,'Death':180.0}

def cr(x):
    if not isinstance(x,str) or str(x).strip() in ('--','','-','nan'): return np.nan
    v=float(re.sub(r'[^0-9.]','',str(x))); return v/100 if ' L' in str(x) else v

SEASON=2027

USE_ANNOUNCED_RELEASES = True
# Every trade completed so far this cycle happened BEFORE the retention deadline,
# so the only release information those clubs had was the projection -- that is the
# world those deals were made in and the world their cards must be priced against.
# The window is open again until the auction, and a trade made now faces the
# announced lists. So the resolver is switched by context: the live simulator uses
# the announced lists, tools/rebuild_featured.py sets this False for historical
# cards. Nothing about the projection is deleted either way.

def release_list(year=SEASON, strict=False):
    """The release list for a season, announced if we have it, projected if not.

       Until the franchises announce, the only release list available is the one
       the model projects, and every purse, vacancy and recovery probability on
       the site rests on it. Once the real lists are published the projection is
       no longer the best available answer -- but it must not be deleted, because
       next season starts in the same position: a window where only a projection
       exists.

       So the resolver is a fallback, not a replacement. Datasets/release_list_
       <year>_actual.csv wins whenever it is present and parses; otherwise the
       projected release_list_<year>.csv is used exactly as before. Dropping the
       announced file into Datasets is the whole switch-over -- no code changes,
       and it works unchanged for 2028.

       Returns (DataFrame, source) where source is 'announced' or 'projected'.
       `strict` raises instead of falling back, for a pipeline run that must not
       quietly publish projections as fact."""
    act=_os.path.join(_DATA,'release_list_%d_actual.csv'%year)
    prj=_os.path.join(_DATA,'release_list_%d.csv'%year)
    if USE_ANNOUNCED_RELEASES and _os.path.isfile(act):
        try:
            d=pd.read_csv(act)
            if len(d) and {'team','player'} <= set(d.columns):
                d['player']=fix(d.player)
                d['team']=d.team.astype(str).str.strip()
                d=d.dropna(subset=['player']).drop_duplicates(['team','player'])
                if len(d): return d, 'announced'
            raise ValueError('%s has no usable team/player rows'%act)
        except Exception as e:
            if strict: raise
            print('! announced release list unusable (%s) -- falling back to the projection'%e)
    elif strict:
        raise FileNotFoundError(act)
    d=pd.read_csv(prj)
    d['player']=fix(d.player)
    d['team']=d.team.astype(str).str.strip()
    return d.drop_duplicates(['team','player']), 'projected'


def completed_trades(year=SEASON):
    """The trades that have actually been done this window, in announcement order.

       Datasets/trades_2027.csv carries one row per player with the trade number
       he moved in. final_pwar.csv already reflects ALL of them -- a player's team
       there is where he plays now -- which is right for the simulator, because a
       user building a new deal should start from today's squads.

       It is wrong for the Featured cards. Trade 4 did not happen in a world where
       trades 5 and 6 had already been done, so pricing it against today's squads
       double-counts them: Delhi's purse before Natarajan was not the purse they
       hold after also doing Pant. rewind(n) returns the moves to reverse to get
       back to the world immediately before trade n, so each card is built against
       the state that deal actually faced."""
    f=_os.path.join(_DATA,'trades_%d.csv'%year)
    if not _os.path.isfile(f): return pd.DataFrame(
        columns=['trade','label','player','from_team','to_team','fee','prev_fee'])
    d=pd.read_csv(f); d['player']=fix(d.player)
    return d.sort_values(['trade','player']).reset_index(drop=True)


def rewind(n, year=SEASON):
    """Moves to undo so the squads read as they did just BEFORE trade n.

       Returns a list of dicts {player, team, salary}: put that player back on
       that club at that fee. Trades numbered n and above are reversed, newest
       first, so applying them in order lands on the pre-trade-n world."""
    d=completed_trades(year)
    if not len(d): return []
    back=d[d.trade>=n].sort_values('trade',ascending=False)
    return [dict(player=r.player, team=r.from_team,
                 salary=(None if pd.isna(r.prev_fee) else float(r.prev_fee)))
            for r in back.itertuples()]


def squads_before(n, year=SEASON):
    """final_pwar rows with team/salary rolled back to just before trade n."""
    P=players()
    for m in rewind(n, year):
        i=P.player==m['player']
        P.loc[i,'team']=m['team']
        if m['salary'] is not None: P.loc[i,'salary']=m['salary']
    return P


def release_source(year=SEASON):
    """'announced' or 'projected', without loading the whole list twice."""
    return 'announced' if (USE_ANNOUNCED_RELEASES and _os.path.isfile(
        _os.path.join(_DATA,'release_list_%d_actual.csv'%year))) else 'projected'


def players():
    d=pd.read_csv(PWAR)
    d['player']=fix(d.player)
    if 'pWAR_final' in d.columns: d['pWAR']=d.pWAR_final     # single source of truth
    return d

# ---------------------------------------------------------------- STEP 1
def price_model(P):
    """Regress what teams ACTUALLY paid on pWAR.  The old fit used a different
       scale entirely, so slope and intercept both have to be re-estimated."""
    a=pd.read_parquet(os.path.join(DATA,'ipl_auction_data_23_26.parquet'))
    s=a[a.auctionStatus.isin(['sold'])].copy()
    s['player']=fix(s.playerName)
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
    # A bowling archetype is not just 'Bowler'. Leg-spin and off-spin are not
    # interchangeable to a side that has lost one, and the auction prices them
    # differently, so the key carries the DELIVERY TYPE as well. bowl_class comes
    # from bowl_style in the ball-by-ball data (LB/LBG/LWS -> wrist-spin,
    # OB/SLA -> finger-spin, the rest pace); where a man has never bowled in the
    # IPL it falls back to the coarse bowl_kind, and failing that to 'none', so
    # nobody drops out of the count.
    _bk=d.get('bowl_class')
    if _bk is None: _bk=pd.Series(index=d.index,dtype=object)
    _bk=_bk.fillna(d.bowl_kind.fillna('').astype(str).str.replace(' bowler','',regex=False))
    _bk=_bk.replace('',pd.NA).fillna('none')
    d['bowl_class_f']=np.where(d.role.isin(['Bowler','Allrounder']),_bk,'none')
    d['arch']=(d.nat+'|'+d.role.fillna('?')+'|'+d.bat_group.fillna('none').astype(str)
               +'|'+d.bowl_class_f)
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
    s=a[a.auctionStatus=='sold'].copy(); s['player']=fix(s.playerName); s['price']=s.auctionPrice.map(cr)
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
