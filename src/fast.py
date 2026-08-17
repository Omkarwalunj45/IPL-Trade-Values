import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import sys, os as _o; sys.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
from auction import *

def value_matrix(pool, reqs):
    """V[i,j] = WAR player i adds to requirement j.  Computed once."""
    n,m=len(pool),len(reqs)
    V=np.zeros((n,m))
    pr=pool.role.values; pg=pool.bat_group.values
    pk=pool['kind'].values if 'kind' in pool.columns else np.array([None]*len(pool))
    rk=reqs['req_kind'].values if 'req_kind' in reqs.columns else np.array([None]*len(reqs))
    br=pool.bat_rate.values; wr=pool.bowl_rate.values
    ru=reqs.unit.values; rr=reqs.role.values; ri=reqs.incumbent_rate.values; re=reqs.exposure.values
    for j in range(m):
        if ru[j]=='bowl':
            ok=np.isin(pr,['Bowler','Allrounder'])
            if rk[j] is not None and str(rk[j])!='nan':      # a spin hole needs a spinner
                ok=ok & ((pk==rk[j]) | pd.isna(pk))
            V[:,j]=np.where(ok,np.maximum(wr-ri[j],0)*re[j]/RPW,0)
        else:
            ok=(pr!='Bowler')
            adj=np.array([rr[j] in ADJACENT.get(g,[g]) for g in pg])
            V[:,j]=np.where(ok&adj,np.maximum(br-ri[j],0)*re[j]/RPW,0)
    return V

def run_fast(pool, reqs, purse0, slots0, sims=200, seed=7, noise_sd_scale=0.12):
    rng=np.random.default_rng(seed)
    teams=list(purse0); tidx={t:i for i,t in enumerate(teams)}
    rteam=reqs.team.map(tidx).values
    fills=np.zeros(len(reqs)); qual=[[] for _ in range(len(reqs))]
    spend=np.zeros((sims,len(teams)))
    base_pool=pool.copy(); rel=pool.rel.values
    for s in range(sims):
        P=base_pool.copy()
        sd=(1-rel)*noise_sd_scale
        P['bat_rate']=P.bat_rate.values+rng.normal(0,sd)
        P['bowl_rate']=P.bowl_rate.values+rng.normal(0,sd)
        V=value_matrix(P,reqs)
        order=lot_order(P.assign(_i=np.arange(len(P))),rng)._i.values
        purse=np.array([purse0[t] for t in teams],float)
        slots=np.array([slots0[t] for t in teams],float)
        openr=np.ones(len(reqs),bool)
        for i in order:
            v=V[i]*openr
            bids=[]
            for k,t in enumerate(teams):
                if slots[k]<=0 or purse[k]<BASE: continue
                mask=(rteam==k)&openr
                if not mask.any(): continue
                vals=v[mask]
                if vals.max()<=0: continue
                jbest=np.where(mask)[0][vals.argmax()]
                top=vals.max(); rest=np.sort(vals)[::-1][1:]
                reserve=min(rest[0]*PRICE_PER_WAR*0.5, max(purse[k]-BASE*(slots[k]-1),0)*0.35) if (slots[k]>1 and len(rest) and rest[0]>0) else 0.0
                c=min(max(top*PRICE_PER_WAR-reserve,0.0),purse[k])
                if c>=BASE: bids.append((c,k,jbest))
            if not bids: continue
            bids.sort(reverse=True)
            c1,k1,j1=bids[0]
            price=min(max(bids[1][0]+STEP if len(bids)>1 else BASE,BASE),c1,purse[k1])
            purse[k1]-=price; slots[k1]-=1; openr[j1]=False
            fills[j1]+=1
            qual[j1].append(P.bowl_rate.values[i] if reqs.unit.values[j1]=='bowl' else P.bat_rate.values[i])
        spend[s]=np.array([purse0[t] for t in teams])-purse
    out=reqs.copy()
    out['p_fill']=fills/sims
    out['e_quality']=[np.mean(q) if q else np.nan for q in qual]
    sp=pd.DataFrame({'team':teams,'exp_spend':spend.mean(0)})
    return out,sp

def run_full(pool,reqs,purse0,slots0,sims=200,seed=7):
    """Same engine, but also records whether the acquisition reached PAR for that role."""
    rng=np.random.default_rng(seed)
    teams=list(purse0); tidx={t:i for i,t in enumerate(teams)}
    rteam=reqs.team.map(tidx).values; rpar=reqs.par.values
    fills=np.zeros(len(reqs)); atpar=np.zeros(len(reqs)); qual=[[] for _ in range(len(reqs))]
    prices=[[] for _ in range(len(reqs))]
    rel=pool.rel.values; base=pool.copy()
    for s in range(sims):
        P=base.copy(); sd=(1-rel)*0.12
        P['bat_rate']=P.bat_rate.values+rng.normal(0,sd); P['bowl_rate']=P.bowl_rate.values+rng.normal(0,sd)
        V=value_matrix(P,reqs); order=lot_order(P.assign(_i=np.arange(len(P))),rng)._i.values
        purse=np.array([purse0[t] for t in teams],float); slots=np.array([slots0[t] for t in teams],float)
        openr=np.ones(len(reqs),bool)
        for i in order:
            v=V[i]*openr; bids=[]
            for k in range(len(teams)):
                if slots[k]<=0 or purse[k]<BASE: continue
                mask=(rteam==k)&openr
                if not mask.any(): continue
                vals=v[mask]
                if vals.max()<=0: continue
                jb=np.where(mask)[0][vals.argmax()]; top=vals.max(); rest=np.sort(vals)[::-1][1:]
                res_=min(rest[0]*PRICE_PER_WAR*0.5,max(purse[k]-BASE*(slots[k]-1),0)*0.35) if (slots[k]>1 and len(rest) and rest[0]>0) else 0.0
                c=min(max(top*PRICE_PER_WAR-res_,0.0),purse[k])
                if c>=BASE: bids.append((c,k,jb))
            if not bids: continue
            bids.sort(reverse=True); c1,k1,j1=bids[0]
            price=min(max(bids[1][0]+STEP if len(bids)>1 else BASE,BASE),c1,purse[k1])
            purse[k1]-=price; slots[k1]-=1; openr[j1]=False; fills[j1]+=1
            q=P.bowl_rate.values[i] if reqs.unit.values[j1]=='bowl' else P.bat_rate.values[i]
            qual[j1].append(q); prices[j1].append(price)
            if q>=rpar[j1]: atpar[j1]+=1
    out=reqs.copy()
    out['p_fill']=fills/sims; out['p_fill_at_par']=atpar/sims
    out['e_quality']=[np.mean(q) if q else np.nan for q in qual]
    out['e_price']=[np.mean(p) if p else np.nan for p in prices]
    return out
