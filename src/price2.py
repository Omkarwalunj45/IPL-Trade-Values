import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""Two-part (hurdle) price model, which is what real mini auctions look like:
   Part 1  P(contested)         -- 2/3 of lots go at base price, one bidder only
   Part 2  multiple over base   -- lognormal, fitted on contested lots only
   Together these reproduce the point mass at base AND the fat right tail."""
import sys, os as _o; sys.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
from price import cr, point_in_time_proj, ALIAS
from names import fix
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
import os as _os


def build(years=(2024,2026)):
    a=pd.read_parquet(_os.path.join(_DATA,'ipl_auction_data_23_26.parquet')); rows=[]
    for y in years:
        s=a[(a.year==y)&(a.auctionStatus=='sold')].copy()
        s['player']=fix(s.playerName)
        s['price']=s.auctionPrice.map(cr); s['base']=s.basePrice.map(cr)
        s['capped']=(s.cappedStatus=='CAPPED').astype(int); s['os']=s.isPlayerOverseas.notna().astype(int)
        s=s.merge(point_in_time_proj(y),on='player',how='left'); s['proj_WAR']=s.proj_WAR.fillna(0)
        s['has_ipl']=(s.prior_exp.fillna(0)>=100).astype(int)
        rows.append(s[['player','price','base','capped','os','role','proj_WAR','has_ipl']])
    d=pd.concat(rows,ignore_index=True).dropna(subset=['price','base'])
    d['contested']=(d.price>d.base*1.01).astype(int)
    d['mult']=d.price/d.base
    return d

def design(d):
    X=pd.get_dummies(d[['role']],drop_first=True).astype(float)
    X['proj']=d.proj_WAR.values; X['capped']=d.capped.values; X['os']=d.os.values
    X['has_ipl']=d.has_ipl.values; X['const']=1.0
    return X

def logit(X,y,l2=1.0,it=200):
    X=X.values.astype(float); b=np.zeros(X.shape[1])
    for _ in range(it):
        p=1/(1+np.exp(-X@b)); W=p*(1-p)+1e-9
        g=X.T@(y-p)-l2*b; H=-(X.T*W)@X-l2*np.eye(len(b))
        s=np.linalg.solve(H,-g); b=b+s
        if np.max(np.abs(s))<1e-9: break
    return b

def fit():
    d=build(); X=design(d)
    b_c=logit(X,d.contested.values.astype(float))
    con=d[d.contested==1]; Xc=design(con)
    y=np.log(con.mult.values)
    b_m,*_=np.linalg.lstsq(Xc.values.astype(float),y,rcond=None)
    resid=y-Xc.values.astype(float)@b_m
    return dict(cols=list(X.columns),b_contest=b_c,b_mult=b_m,resid=resid,
                p_contest_rate=d.contested.mean(),data=d)

def row(model,proj,capped,os_,role,has_ipl=1):
    x=np.zeros(len(model['cols']))
    for i,c in enumerate(model['cols']):
        if c=='const': x[i]=1
        elif c=='proj': x[i]=proj
        elif c=='capped': x[i]=capped
        elif c=='os': x[i]=os_
        elif c=='has_ipl': x[i]=has_ipl
        elif c.startswith('role_'): x[i]=1.0 if c=='role_'+str(role) else 0.0
    return x

def draw(model,proj,base,capped,os_,role,rng,extra_demand=0.0,has_ipl=1):
    """extra_demand shifts P(contested) up when several teams need that archetype."""
    x=row(model,proj,capped,os_,role,has_ipl)
    pc=1/(1+np.exp(-(x@model['b_contest']+extra_demand)))
    if rng.random()>pc: return base
    mu=float(x@model['b_mult'])+rng.choice(model['resid'])
    return base*float(np.exp(mu))
