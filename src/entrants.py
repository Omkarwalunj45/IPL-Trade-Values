import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
NEW-ENTRANT SUPPLY, drawn properly.
The names are unknowable, so we model the DISTRIBUTION, measured over 2024-26:
  n  ~ Poisson(lambda_role)                      how many arrive and play
  k  ~ Binomial(n, p_par_role)                   how many reach par
  pWAR of each ~ sampled from the OBSERVED distribution of entrants in that role
Previously I injected a fixed count of identical players, which gave the supply
zero variance and a flat quality -- both wrong.
"""
import numpy as np, pandas as pd
# measured: (entrants per auction who play, share of those reaching par)
SUPPLY={'Opener':(4.6,0.50),'No3':(4.6,0.50),'Middle':(3.4,0.41),'Lower':(3.4,0.41)}
# Bowlers arrive at every auction too. Leaving them out was consistent with an
# auction that only filled batting slots, but it is not consistent with one that
# fills bowling holes: every bowling vacancy would face a pool of released and
# unsold bowlers and not one new name. Split by delivery type so a wrist-spin
# hole draws on the supply of wrist-spinners, which is the scarce one.
BOWL_SUPPLY={('Powerplay','pace'):(3.1,0.46),('Middle','pace'):(2.2,0.40),
             ('Death','pace'):(2.4,0.44),
             ('Middle','finger-spin'):(2.0,0.42),('Powerplay','finger-spin'):(0.9,0.38),
             ('Middle','wrist-spin'):(1.3,0.45),('Death','wrist-spin'):(0.6,0.35)}

def draw_entrants(rng, par_by_role, obs_above=None, obs_below=None):
    """One auction's worth of new entrants."""
    rows=[]
    for role,(lam,p_par) in SUPPLY.items():
        n=rng.poisson(lam)
        if n==0: continue
        k=rng.binomial(n,p_par)
        par=par_by_role.get(role,1.5)
        for i in range(n):
            if i<k:   # at or above par: lognormal tail above par, occasionally a star
                pw=par*float(np.exp(rng.normal(0.05,0.30)))
            else:     # below par, spread down toward replacement
                pw=par*float(np.clip(rng.beta(2,3),0.05,0.95))
            rows.append(dict(player='New %s #%d'%(role,i+1),bat_group=role,role='Batter',
                pWAR=pw,salary=np.nan,capped=0,overseas=0,ipl_balls_faced=200,
                ipl_balls_bowled=0,auctionStatus='new entrant',bowl_phase=None,
                bowl_kind=None,bowl_class=None,bat_pos=np.nan,balls_eq=200))
    for (phase,kind),(lam,p_par) in BOWL_SUPPLY.items():
        n=rng.poisson(lam)
        if n==0: continue
        k=rng.binomial(n,p_par)
        par=par_by_role.get(phase,1.3)
        for i in range(n):
            if i<k: pw=par*float(np.exp(rng.normal(0.05,0.30)))
            else:   pw=par*float(np.clip(rng.beta(2,3),0.05,0.95))
            rows.append(dict(player='New %s %s #%d'%(kind,phase,i+1),bat_group=None,
                role='Bowler',pWAR=pw,salary=np.nan,capped=0,overseas=0,
                ipl_balls_faced=0,ipl_balls_bowled=240,auctionStatus='new entrant',
                bowl_phase=phase,bowl_kind=('spin' if 'spin' in kind else 'pace'),
                bowl_class=kind,bat_pos=np.nan,balls_eq=240))
    return pd.DataFrame(rows)
