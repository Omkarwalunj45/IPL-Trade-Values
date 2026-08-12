import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
============================================================================
 IPL TRADE OPTIMISER  --  maximise team WAR under real selection constraints
============================================================================
 Rate is a property of the PLAYER.  Exposure is a property of the SLOT.
 Team WAR = sum over slots of (player's rate in that discipline x slot exposure)

 HARD CONSTRAINTS ENFORCED
   1. Batting position may move by at most +/-1 from a player's natural slot
      (positions 1 and 2 are one interchangeable opening pair, so a No.3
       may open).  A No.3 can NEVER bat 5 or lower.
   2. Playing TWELVE (Impact Player era): 8 specialist batting slots + 4 tail.
   3. Bowling: 5 mandatory bowling slots, 6th and 7th optional.
   4. Phase cover: minimum bowlers able to bowl powerplay / middle / death.
      Trade a powerplay-and-death bowler out and the gap must be refilled.
   5. Exactly one wicketkeeper in the twelve.
   6. At most 4 overseas players in the twelve.
   7. A player occupies at most one batting slot and at most one bowling slot,
      and can only bowl if he is in the twelve.  Batting slot and bowling slot
      are INDEPENDENT -- an opener may be a frontline bowler.

 USAGE
     from ipl_trade_optimizer import *
     P = build_players()
     xii, war = optimize_xii(squad(P, 'CSK'))
     evaluate_trade(P, 'CSK', 'MI',
                    a_receives=['Hardik Pandya'],
                    b_receives=['Shivam Dube','Ayush Mhatre'])
============================================================================
"""
import numpy as np, pandas as pd, re, warnings
from scipy.optimize import milp, LinearConstraint, Bounds
import os as _os

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------- CONFIG
BBB_PATH  = _os.path.join(_DATA,'ipl_df__4_.parquet')
SAL_PATH  = _os.path.join(_DATA,'ipl_salaries.csv')
WAR_PATH  = _os.path.join(_DATA,'war_final.parquet')

RPW              = 82.5      # runs per win
SEASON_MATCHES   = 14
MAX_OVERSEAS     = 4         # in the playing twelve
N_WICKETKEEPERS  = 1
MIN_PP_BOWLERS   = 2         # bowlers in the XII able to bowl the powerplay
MIN_MID_BOWLERS  = 3
MIN_DEATH_BOWLERS= 2
MANDATORY_BOWL_SLOTS = [1,2,3,4,5]     # must be filled
OPTIONAL_BOWL_SLOTS  = [6,7]           # filled if a 6th/7th bowler helps
BAT_POS_FLEX     = 1         # +/- 1 position, hard
YEAR_W           = {2026:5, 2025:4, 2024:3, 2023:2}
ALIAS            = {"Vaibhav Suryavanshi":"Vaibhav Sooryavanshi"}
TEAM_MAP = {"Chennai Super Kings":"CSK","Delhi Capitals":"DC","Gujarat Titans":"GT",
 "Kolkata Knight Riders":"KKR","Lucknow Super Giants":"LSG","Mumbai Indians":"MI",
 "Punjab Kings":"PBKS","Rajasthan Royals":"RR","Royal Challengers Bangalore":"RCB",
 "Royal Challengers Bengaluru":"RCB","Sunrisers Hyderabad":"SRH"}

# ------------------------------------------------ SLOT EXPOSURE (Statsguru, 581 innings)
_INNS = 581
_BAT_BF  = {1:24070/2, 2:24070/2, 3:10561, 4:9915, 5:7926, 6:5777, 7:4067, 8:2362}
_TAIL_BF = (1274+629+272)/4.0                       # per tail slot
_BOWL_B  = {1:11930, 2:11676, 3:12028, 4:11890, 5:11065, 6:6849, 7:1020}

BAT_EXP  = {s: v/_INNS*SEASON_MATCHES for s,v in _BAT_BF.items()}
BAT_EXP[9] = _TAIL_BF/_INNS*SEASON_MATCHES          # slot 9 = the four tail places
BOWL_EXP = {s: v/_INNS*SEASON_MATCHES for s,v in _BOWL_B.items()}
BAT_SLOTS  = list(range(1,9)); TAIL_SLOT = 9; ALL_BAT = BAT_SLOTS + [TAIL_SLOT]
BOWL_SLOTS = list(range(1,8))
N_TAIL = 4

# ---------------------------------------------------------------- LOADING
def _to_cr(x):
    if not isinstance(x,str): return np.nan
    v=re.sub(r'[^0-9.]','',x)
    return np.nan if v in ('','.') else (float(v)/100 if 'Lakh' in x else float(v))

def load_salaries():
    s=pd.read_csv(SAL_PATH)
    sw=s.season>=2024
    s.loc[sw,['player','salary']]=s.loc[sw,['salary','player']].values   # columns transposed from 2024
    s['player']=s.player.str.strip().replace(ALIAS)
    s['sal_cr']=s.salary.map(_to_cr)
    s['country']=s.country.astype(str).str.replace(r'[^\x00-\x7F]','',regex=True).str.strip()
    s['overseas']=(s.country.str.replace(r'\s*\(.*\)','',regex=True).str.strip()!='India').astype(int)
    return s

def build_players(verbose=True):
    """One row per player: natural batting slot, bat/bowl rates, bowling phases, flags."""
    bbb=pd.read_parquet(BBB_PATH).rename(columns={'year':'season'})
    bbb['bat']=bbb.bat.str.strip().replace(ALIAS); bbb['bowl']=bbb.bowl.str.strip().replace(ALIAS)
    bbb['tb']=bbb.team_bat.map(TEAM_MAP); bbb['tbo']=bbb.team_bowl.map(TEAM_MAP)
    bbb['seq']=bbb.over*100+bbb.ball

    # --- natural batting slot: recency-weighted median order of arrival
    first=(bbb.sort_values('seq').groupby(['p_match','inns','bat'],as_index=False)
              .agg(fb=('seq','min'),season=('season','first')))
    first['pos']=first.sort_values('fb').groupby(['p_match','inns']).cumcount()+1
    first['w']=first.season.map(YEAR_W)
    nat=(first.groupby('bat').apply(lambda x: np.average(x.pos,weights=x.w),include_groups=False)
              .rename('nat_pos').reset_index().rename(columns={'bat':'player'}))
    nat['nat_slot']=nat.nat_pos.round().clip(1,9).astype(int)

    # --- bowling phase capability: phases where he bowls >=10% of his deliveries
    ph=(bbb.groupby(['bowl','phase'],as_index=False).ballfaced.sum()
           .rename(columns={'bowl':'player'}))
    tot=ph.groupby('player').ballfaced.sum().rename('tot')
    ph=ph.join(tot,on='player'); ph['share']=ph.ballfaced/ph.tot
    phases=(ph[ph.share>=0.10].groupby('player').phase.apply(set).rename('phases'))

    # --- rates, split by discipline, recency + reliability shrunk
    w=pd.read_parquet(WAR_PATH); w['player']=w.player.replace(ALIAS)
    w=w.groupby(['season','player'],as_index=False).agg(
        team=('team','first'),bf=('bf','sum'),bb=('bb','sum'),
        RAA_bat=('RAA_bat','sum'),REP_bat=('REP_bat','sum'),
        RAA_bowl=('RAA_bowl','sum'),REP_bowl=('REP_bowl','sum'))
    w['bat_RAR']=w.RAA_bat+w.REP_bat; w['bowl_RAR']=w.RAA_bowl+w.REP_bowl
    lg_bat=w.bat_RAR.sum()/w.bf.sum(); lg_bowl=w.bowl_RAR.sum()/w.bb.sum()
    K_BAT, K_BOWL = 887, 475            # from year-to-year reliability (r=.19 batting, .31 bowling)
    w['yw']=w.season.map(YEAR_W)
    g=(w.groupby('player').apply(lambda x: pd.Series({
        'wbatRAR':(x.yw*x.bat_RAR).sum(),'wbf':(x.yw*x.bf).sum(),
        'wbowlRAR':(x.yw*x.bowl_RAR).sum(),'wbb':(x.yw*x.bb).sum(),
        'bf_tot':x.bf.sum(),'bb_tot':x.bb.sum(),
        'last_team':x.sort_values('season').team.iloc[-1]}),include_groups=False).reset_index())
    g['bat_rate']=(g.wbatRAR+K_BAT*lg_bat)/(g.wbf+K_BAT)
    g['bowl_rate']=(g.wbowlRAR+K_BOWL*lg_bowl)/(g.wbb+K_BOWL)

    P=g.merge(nat[['player','nat_pos','nat_slot']],on='player',how='left')
    P=P.merge(phases,on='player',how='left')
    P['phases']=P.phases.apply(lambda x: x if isinstance(x,set) else set())
    P['can_bowl']=(P.bb_tot>=60)&(P.phases.apply(len)>0)
    P.loc[~P.can_bowl,'bowl_rate']=np.nan
    P['nat_slot']=P.nat_slot.fillna(9).astype(int)
    sal=load_salaries()
    latest=sal.sort_values('season').groupby('player').last().reset_index()
    P=P.merge(latest[['player','overseas','role','sal_cr']],on='player',how='left')
    P['overseas']=P.overseas.fillna(0).astype(int)
    P['is_wk']=(P.role=='WK-Batter').fillna(False)
    if verbose:
        print('players built: %d | can bowl: %d | keepers: %d'%(len(P),P.can_bowl.sum(),P.is_wk.sum()))
    return P

def squad(P, team, season=2026, add=(), drop=()):
    """Roster for a franchise, with players added/removed to model a trade."""
    sal=load_salaries()
    names=set(sal[(sal.season==season)&(sal.team==team)].player)
    names |= set(add); names -= set(drop)
    s=P[P.player.isin(names)].copy()
    missing=names-set(s.player)
    if missing: print('   [warn] no record for: %s'%', '.join(sorted(missing)))
    return s.reset_index(drop=True)

# ---------------------------------------------------------------- ELIGIBILITY
def bat_eligible(nat_slot, s):
    """+/-1 position, with 1 and 2 a single interchangeable opening pair."""
    if s == TAIL_SLOT:
        return nat_slot >= 7
    if nat_slot <= 2:                       # an opener may bat 1, 2 or 3
        return s <= 3
    if s <= 2:                              # anyone naturally at 3 may open
        return nat_slot <= 3
    return abs(nat_slot - s) <= BAT_POS_FLEX

# ---------------------------------------------------------------- OPTIMISER
def optimize_xii(sq, max_overseas=MAX_OVERSEAS, verbose=False, locked=None):
    locked = locked or {}   # {player: bat_slot} -- captains cannot be moved
    sq=sq.reset_index(drop=True); n=len(sq)
    nb=n*len(ALL_BAT); nw=n*len(BOWL_SLOTS)
    bi=lambda p,s: p*len(ALL_BAT)+ALL_BAT.index(s)
    wi=lambda p,b: nb+p*len(BOWL_SLOTS)+BOWL_SLOTS.index(b)
    c=np.zeros(nb+nw)
    for p in range(n):
        for s in ALL_BAT:
            c[bi(p,s)] = -sq.bat_rate.iloc[p]*BAT_EXP[s]
        r=sq.bowl_rate.iloc[p]
        for b in BOWL_SLOTS:
            c[wi(p,b)] = 0.0 if pd.isna(r) else -r*BOWL_EXP[b]
    A=[];lb=[];ub=[]
    def add(row,l,u): A.append(row);lb.append(l);ub.append(u)

    for s in BAT_SLOTS:                                   # every batting slot filled once
        r=np.zeros(nb+nw); [r.__setitem__(bi(p,s),1) for p in range(n)]; add(r,1,1)
    r=np.zeros(nb+nw); [r.__setitem__(bi(p,TAIL_SLOT),1) for p in range(n)]; add(r,N_TAIL,N_TAIL)
    for b in MANDATORY_BOWL_SLOTS:
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for p in range(n)]; add(r,1,1)
    for b in OPTIONAL_BOWL_SLOTS:
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for p in range(n)]; add(r,0,1)

    for p in range(n):
        r=np.zeros(nb+nw); [r.__setitem__(bi(p,s),1) for s in ALL_BAT]; add(r,0,1)
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; add(r,0,1)
        r=np.zeros(nb+nw)                                  # may bowl only if selected
        [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; [r.__setitem__(bi(p,s),-1) for s in ALL_BAT]
        add(r,-np.inf,0)
        for s in ALL_BAT:                                  # HARD positional eligibility
            if not bat_eligible(int(sq.nat_slot.iloc[p]), s):
                r=np.zeros(nb+nw); r[bi(p,s)]=1; add(r,0,0)
        if pd.isna(sq.bowl_rate.iloc[p]):                  # non-bowlers cannot take a bowling slot
            r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; add(r,0,0)

    for pl,slot in locked.items():                         # captain locked to his 2026 slot
        if pl in set(sq.player):
            pi=int(sq.index[sq.player==pl][0])
            r=np.zeros(nb+nw); r[bi(pi,int(slot))]=1; add(r,1,1)
    r=np.zeros(nb+nw)                                      # overseas cap on the twelve
    for p in range(n):
        if sq.overseas.iloc[p]==1: [r.__setitem__(bi(p,s),1) for s in ALL_BAT]
    add(r,0,max_overseas)
    r=np.zeros(nb+nw)                                      # exactly one keeper
    for p in range(n):
        if sq.is_wk.iloc[p]: [r.__setitem__(bi(p,s),1) for s in ALL_BAT]
    add(r,N_WICKETKEEPERS,np.inf)   # >=1 keeper: extra WK-Batters are judged purely as batters
    for phase,mn in [('Powerplay',MIN_PP_BOWLERS),('Middle',MIN_MID_BOWLERS),('Death',MIN_DEATH_BOWLERS)]:
        r=np.zeros(nb+nw)                                  # phase cover among ASSIGNED bowlers
        for p in range(n):
            if phase in sq.phases.iloc[p]:
                [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]
        add(r,mn,np.inf)

    res=milp(c=c,constraints=LinearConstraint(np.array(A),lb,ub),
             integrality=np.ones(nb+nw),bounds=Bounds(0,1))
    if not res.success:
        return None, np.nan, res.message
    x=res.x; rows=[]
    for p in range(n):
        s=[ss for ss in ALL_BAT if x[bi(p,ss)]>0.5]
        if not s: continue
        b=[bb for bb in BOWL_SLOTS if x[wi(p,bb)]>0.5]
        rows.append(dict(player=sq.player.iloc[p],nat_slot=int(sq.nat_slot.iloc[p]),
            bat_slot=s[0],bowl_slot=(b[0] if b else None),overseas=int(sq.overseas.iloc[p]),
            wk=bool(sq.is_wk.iloc[p]),phases=','.join(sorted(sq.phases.iloc[p])),
            bat_rate=sq.bat_rate.iloc[p],bowl_rate=sq.bowl_rate.iloc[p]))
    xii=pd.DataFrame(rows)
    xii['bat_RAR']=xii.bat_slot.map(BAT_EXP)*xii.bat_rate
    xii['bowl_RAR']=xii.bowl_slot.map(BOWL_EXP).fillna(0)*xii.bowl_rate.fillna(0)
    xii['WAR']=(xii.bat_RAR+xii.bowl_RAR)/RPW
    return xii.sort_values(['bat_slot','bowl_slot']).reset_index(drop=True), -res.fun/RPW, 'ok'

# ---------------------------------------------------------------- TRADE API
def evaluate_trade(P, team_a, team_b, a_receives, b_receives, season=2026, show=True):
    """a_receives: players moving A <- B.   b_receives: players moving B <- A."""
    res={}
    for team,gets,gives in [(team_a,a_receives,b_receives),(team_b,b_receives,a_receives)]:
        _,before,_=optimize_xii(squad(P,team,season))
        xii,after,msg=optimize_xii(squad(P,team,season,add=gets,drop=gives))
        res[team]=dict(before=before,after=after,delta=after-before,xii=xii,status=msg)
    if show:
        print('%-6s %8s %8s %8s'%('team','before','after','delta'))
        for t,v in res.items():
            print('%-6s %8.2f %8.2f %+8.2f'%(t,v['before'],v['after'],v['delta']))
        da,db=res[team_a]['delta'],res[team_b]['delta']
        q=('win-win' if da>0 and db>0 else 'lose-lose' if da<0 and db<0
           else '%s wins'%(team_a if da>db else team_b))
        print('verdict: %s   |  total value created %+.2f WAR'%(q,da+db))
    return res


# ---------------------------------------------------------------- pWAR rewire
PWAR_PATH=_os.path.join(_DATA,'final_pwar.csv')

def build_players_pwar(verbose=False):
    """Same squad structure as build_players -- natural slot, phases, keeper,
       overseas, all constraints unchanged -- but the VALUE comes from pWAR.

       pWAR is a season total.  The optimiser needs a per-ball rate, so pWAR is
       converted back:  rate = pWAR * RPW / expected_balls, then split between
       batting and bowling in the proportion the player actually plays them."""
    P=build_players(verbose=False)
    W=pd.read_csv(PWAR_PATH); W['player']=W.player.str.strip().replace(ALIAS)
    if 'pWAR_final' in W.columns: W['pWAR']=W.pWAR_final
    W=W[['player','pWAR','ipl_balls_faced','ipl_balls_bowled','balls_eq','team','bat_group','bowl_phase','role','salary','overseas','capped']]
    P=P.drop(columns=[c for c in ['team','salary','overseas','capped','role'] if c in P.columns],errors='ignore')
    M=P.merge(W,on='player',how='inner')
    bf=M.ipl_balls_faced.fillna(0); bb=M.ipl_balls_bowled.fillna(0)
    tot=(bf+bb).replace(0,np.nan)
    M['share_bat']=(bf/tot).fillna(0.5); M['share_bowl']=1-M.share_bat
    # total runs above replacement implied by pWAR
    RAR=M.pWAR*RPW
    M['bat_rate']=np.where(bf>0, RAR*M.share_bat/bf.replace(0,np.nan), 0.0)
    M['bowl_rate']=np.where(bb>0, RAR*M.share_bowl/bb.replace(0,np.nan), 0.0)
    M[['bat_rate','bowl_rate']]=M[['bat_rate','bowl_rate']].fillna(0.0)
    M['overseas']=M.overseas.fillna(0).astype(int)
    if verbose:
        print('pWAR-rewired players: %d | bat_rate %.3f..%.3f | bowl_rate %.3f..%.3f'%(
            len(M),M.bat_rate.min(),M.bat_rate.max(),M.bowl_rate.min(),M.bowl_rate.max()))
    return M

def squad_pwar(P, team, add=(), drop=()):
    names=set(P[P.team==team].player)-set(drop)|set(add)
    return P[P.player.isin(names)].reset_index(drop=True)


# ---------------------------------------------------------------- pWAR objective
# Slot weights: a slot's share of exposure, normalised so an average slot = 1.0.
# A player placed in an average slot therefore contributes his full pWAR, an
# opener slightly more, a No.8 much less.  Units stay in pWAR throughout, so
# removing a player and reading the drop is meaningful.
# Slot weight = WIN SHARE, not raw exposure.  Fitted by logistic regression of
# match result on runs scored by each batting slot and runs conceded in each
# bowling phase (n=542 team-innings, 2023-26).  Exposure alone underrates the
# lower order and the death overs: a run at No.8 is worth 1.69x its ball count,
# death bowling 1.30x, while powerplay bowling is worth only 0.76x.
_WIN_SHARE_BAT={1:.165,2:.183,3:.159,4:.138,5:.121,6:.092,7:.081,8:.062}
_IMP_BAT={s: _WIN_SHARE_BAT[s]/(BAT_EXP[s]/sum(BAT_EXP[k] for k in _WIN_SHARE_BAT)) for s in _WIN_SHARE_BAT}
_PHASE_IMP={'Powerplay':0.76,'Middle':1.05,'Death':1.30}
_BW_MEAN=np.mean([BAT_EXP[s]*_IMP_BAT.get(s,1.0) for s in BAT_SLOTS])
_WW_MEAN=np.mean([BOWL_EXP[b] for b in BOWL_SLOTS[:5]])
BAT_W  = {s: BAT_EXP[s]*_IMP_BAT.get(s,1.0)/_BW_MEAN for s in ALL_BAT}
BOWL_W = {b: BOWL_EXP[b]/_WW_MEAN for b in BOWL_SLOTS}

def phase_multiplier(phases):
    """A bowler who covers the death is worth more per ball than a powerplay-only
       bowler, because death runs decide more matches."""
    ph=[p for p in _PHASE_IMP if p in (phases or set())]
    return float(np.mean([_PHASE_IMP[p] for p in ph])) if ph else 1.0

def optimize_xii_pwar(sq, max_overseas=MAX_OVERSEAS, locked=None):
    """Identical constraints to optimize_xii.  Only the objective changes:
       maximise sum of (pWAR split by discipline) x (slot weight)."""
    locked=locked or {}
    sq=sq.reset_index(drop=True); n=len(sq)
    nb=n*len(ALL_BAT); nw=n*len(BOWL_SLOTS)
    bi=lambda p,s: p*len(ALL_BAT)+ALL_BAT.index(s)
    wi=lambda p,b: nb+p*len(BOWL_SLOTS)+BOWL_SLOTS.index(b)
    c=np.zeros(nb+nw)
    for p in range(n):
        pw=float(sq.pWAR.iloc[p]); sb=float(sq.share_bat.iloc[p]); sw=1.0-sb
        for s in ALL_BAT:  c[bi(p,s)] = -pw*sb*BAT_W[s]
        pm=phase_multiplier(sq.phases.iloc[p])
        for b in BOWL_SLOTS: c[wi(p,b)] = -pw*sw*BOWL_W[b]*pm
    A=[];lb=[];ub=[]
    def add(row,l,u): A.append(row);lb.append(l);ub.append(u)
    for s in BAT_SLOTS:
        r=np.zeros(nb+nw); [r.__setitem__(bi(p,s),1) for p in range(n)]; add(r,1,1)
    r=np.zeros(nb+nw); [r.__setitem__(bi(p,TAIL_SLOT),1) for p in range(n)]; add(r,N_TAIL,N_TAIL)
    for b in MANDATORY_BOWL_SLOTS:
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for p in range(n)]; add(r,1,1)
    for b in OPTIONAL_BOWL_SLOTS:
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for p in range(n)]; add(r,0,1)
    for p in range(n):
        r=np.zeros(nb+nw); [r.__setitem__(bi(p,s),1) for s in ALL_BAT]; add(r,0,1)
        r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; add(r,0,1)
        r=np.zeros(nb+nw)
        [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; [r.__setitem__(bi(p,s),-1) for s in ALL_BAT]
        add(r,-np.inf,0)
        for s in ALL_BAT:
            if not bat_eligible(int(sq.nat_slot.iloc[p]), s):
                r=np.zeros(nb+nw); r[bi(p,s)]=1; add(r,0,0)
        if not bool(sq.can_bowl.iloc[p]):
            r=np.zeros(nb+nw); [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]; add(r,0,0)
    for pl,slot in locked.items():
        if pl in set(sq.player):
            pi=int(sq.index[sq.player==pl][0])
            r=np.zeros(nb+nw); r[bi(pi,int(slot))]=1; add(r,1,1)
    r=np.zeros(nb+nw)
    for p in range(n):
        if sq.overseas.iloc[p]==1: [r.__setitem__(bi(p,s),1) for s in ALL_BAT]
    add(r,0,max_overseas)
    r=np.zeros(nb+nw)
    for p in range(n):
        if sq.is_wk.iloc[p]: [r.__setitem__(bi(p,s),1) for s in ALL_BAT]
    add(r,N_WICKETKEEPERS,np.inf)
    for phase,mn in [('Powerplay',MIN_PP_BOWLERS),('Middle',MIN_MID_BOWLERS),('Death',MIN_DEATH_BOWLERS)]:
        r=np.zeros(nb+nw)
        for p in range(n):
            if phase in sq.phases.iloc[p]:
                [r.__setitem__(wi(p,b),1) for b in BOWL_SLOTS]
        add(r,mn,np.inf)
    res=milp(c=c,constraints=LinearConstraint(np.array(A),lb,ub),
             integrality=np.ones(nb+nw),bounds=Bounds(0,1))
    if not res.success: return None,np.nan,res.message
    x=res.x; rows=[]
    for p in range(n):
        s=[ss for ss in ALL_BAT if x[bi(p,ss)]>0.5]
        if not s: continue
        b=[bb for bb in BOWL_SLOTS if x[wi(p,bb)]>0.5]
        pw=float(sq.pWAR.iloc[p]); sb=float(sq.share_bat.iloc[p])
        pm=phase_multiplier(sq.phases.iloc[p])
        contrib=pw*sb*BAT_W[s[0]] + (pw*(1-sb)*BOWL_W[b[0]]*pm if b else 0.0)
        rows.append(dict(player=sq.player.iloc[p],nat_slot=int(sq.nat_slot.iloc[p]),
            bat_slot=s[0],bowl_slot=(b[0] if b else None),overseas=int(sq.overseas.iloc[p]),
            wk=bool(sq.is_wk.iloc[p]),pWAR=pw,contribution=contrib))
    return pd.DataFrame(rows).sort_values('bat_slot').reset_index(drop=True), -res.fun, 'ok'
