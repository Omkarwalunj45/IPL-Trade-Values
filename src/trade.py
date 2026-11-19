import os as _os, sys as _sys
_DATA=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),'Datasets')
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
"""
=====================================================================
 STEPS 4-5 on the pWAR framework
   * vacancies from the pWAR-weighted XII vs role par
   * auction pool valued in pWAR
   * recovery: can the vacating side replace what left, and at what standard
   * purse sequence: carry-over -> +Rs6cr -> TRADE -> release deadline
   * surplus on the refitted price model (pWAR, scarcity, flex, capped, overseas)
   * league simulation -> playoff / title probability
=====================================================================
"""
import sys, os, json, re
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from ipl_trade_optimizer import (build_players_pwar, squad_pwar, optimize_xii_pwar,
                                 BAT_W, phase_multiplier, ALIAS)
from core import players, price_model2, archetype_features, market_fair2, cr
DATA=_DATA
RPW=82.5; GAMES=14; REPL_WIN=0.30; DENS=0.01212
CARRY={'CSK':2.40,'DC':0.35,'GT':1.95,'KKR':0.45,'LSG':4.55,'MI':0.55,'PBKS':3.50,'RR':2.65,'RCB':0.25,'SRH':5.45}
TOPUP=6.0; MAX_SQUAD=25

# ---------------------------------------------------------------- vacancies
BOWL_EX={'Powerplay':290.0,'Middle':270.0,'Death':180.0}
BOWL_W={'Powerplay':1.15,'Middle':1.0,'Death':1.20}

# Legal balls a side must cover in each phase of ONE innings, measured 2022-26.
# Twenty overs have to be bowled by somebody; these are the budgets that get
# allocated among the XII's bowling resources.
# Balls per innings, measured 2022-26 over 583 innings. Both tables are GROUP
# totals and both divide by EVERY innings, not only the ones in which that group
# appeared -- numbers six and seven often do not bat at all, and averaging over
# just the innings they did bat inflated them (Lower 20.1 against a true 16.7,
# Tail 13.2 against 7.5). The tell was the batting total coming to 125.5 when an
# innings is 120 balls. Both tables now sum to 115.6, counting the same
# deliveries from the batting end and the bowling end, which is the check.
PHASE_BALLS={'Powerplay':30.1,'Middle':53.7,'Death':31.8}

# Opener, Middle and Lower are TWO batting positions each; No3 is ONE. These
# group totals are therefore NOT comparable man-for-man and must not be read that
# way. Per position the order is what you would expect:
#     pos1 19.9  pos2 21.7  pos3 18.4  pos4 17.0  pos5 14.2  pos6 10.0  pos7 6.8
# i.e. Opener 20.8, No3 18.4, Middle 15.6, Lower 8.4 per player. The group total
# is what belongs here, because a hole spanning two slots is worth more to fix
# than one spanning a single slot at the same deficit per ball.
SLOT_BALLS={'Opener':41.7,'No3':18.4,'Middle':31.2,'Lower':16.7}
MAX_BALLS_PER_BOWLER=24.0        # four overs
_SHARE=None; _BATSHARE=None


def phase_share():
    """Per-bowler, per-phase usage and economy against the league.

         share      -- fraction of his deliveries bowled in that phase. This is
                       the exposure weight: an all-rounder who rolls his arm over
                       for two overs is not cover for the death, and weighting by
                       share is what stops him counting as if he were.
         econ_delta -- league economy in that phase minus his, so positive means
                       he goes for fewer runs than an average bowler does there."""
    global _SHARE
    if _SHARE is None:
        f=_os.path.join(_DATA,'bowl_phase_share.csv')
        _SHARE=pd.read_csv(f) if _os.path.isfile(f) else pd.DataFrame(
            columns=['player','phase','balls','share','econ','lg_econ','econ_delta'])
    return _SHARE


def bat_share():
    """Per-batter, per-position strike rate against the league at that position.

       The batting mirror of phase_share. A number six is not judged against an
       opener's strike rate, and a man who has faced forty balls at three is not
       treated as that side's number three."""
    global _BATSHARE
    if _BATSHARE is None:
        f=_os.path.join(_DATA,'bat_slot_share.csv')
        _BATSHARE=pd.read_csv(f) if _os.path.isfile(f) else pd.DataFrame(
            columns=['player','slot','balls','share','sr','lg_sr','sr_delta'])
    return _BATSHARE


def allocate_overs(xii, sq):
    """How this XII would actually get through its twenty overs, phase by phase.

       Earlier this asked only 'who is the best bowler in this phase' and compared
       him to a par. That is the wrong question twice over: a side does not bowl
       its best man for all twenty overs, and a phase covered by one good bowler
       and three poor ones is not a well-covered phase.

       So the phase budget is allocated instead. Within a phase the bowlers who
       actually bowl in it are ranked by economy against the league and given
       balls in order, nobody past four overs, and the phase is scored as the
       ball-weighted average of what the men who bowled it are worth. Death and
       powerplay allocate first: they are the specialist phases."""
    S=phase_share(); info=sq.set_index('player'); cand={}
    for r in xii.itertuples():
        if r.player not in info.index: continue
        m=info.loc[r.player]
        if getattr(m,'ndim',1)>1: m=m.iloc[0]
        d=S[S.player==r.player]
        if not len(d): continue
        kind=str(m.get('bowl_class') or m.get('bowl_kind') or '')
        for q in d.itertuples():
            cand.setdefault(q.phase,[]).append(
                dict(player=r.player,share=float(q.share),delta=float(q.econ_delta),kind=kind))
    used={}; out=[]
    for ph in ('Death','Powerplay','Middle'):
        budget=PHASE_BALLS[ph]; got=0.0; num=0.0; top=(None,0.0)
        for c in sorted(cand.get(ph,[]),key=lambda x:-x['delta']):
            if got>=budget: break
            room=MAX_BALLS_PER_BOWLER-used.get(c['player'],0.0)
            if room<=0: continue
            take=min(budget-got,room,MAX_BALLS_PER_BOWLER*max(c['share'],0.05)*2.0)
            if take<=0: continue
            used[c['player']]=used.get(c['player'],0.0)+take
            got+=take; num+=c['delta']*take
            if take>top[1]: top=(c,take)
        quality=(num/got) if got>0 else None
        best=top[0]
        out.append(dict(phase=ph,balls=round(got,1),budget=budget,quality=quality,
                        uncovered=round(max(budget-got,0),1),
                        occupant=(best['player'] if best else '__none__'),
                        kind=(best['kind'] if best else '')))
    return pd.DataFrame(out)


_GRP={1:'Opener',2:'Opener',3:'No3',4:'Middle',5:'Middle',6:'Lower',7:'Lower'}


def allocate_innings(xii):
    """How this XII's top seven would face its innings, position group by group.

       The batting mirror of allocate_overs, and it exists for the same reason the
       bowling one does. A hole used to be declared by comparing a man's SEASON
       pWAR to a bench par, while the auction filled it by comparing PER-BALL
       rates -- two different units. A low-exposure slot like Lower (twenty balls
       an innings) divides a season pWAR by a small number, which made the
       incumbent's implied rate larger than anything in the pool, so every
       candidate scored zero and the slot came back 'hole, 0% chance of filling'.

       Judging the group on strike rate against the league at that position, over
       the balls that position actually faces, puts detection and filling in the
       same units and the contradiction disappears."""
    B=bat_share(); out=[]
    byg={}
    for r in xii.itertuples():
        g=_GRP.get(int(r.bat_slot))
        if g: byg.setdefault(g,[]).append(r.player)
    for g,balls in SLOT_BALLS.items():
        men=byg.get(g,[])
        if not men:
            out.append(dict(slot=g,balls=balls,quality=None,occupant='__none__',n=0)); continue
        num=den=0.0; worst=(None,9e9)
        for pl in men:
            d=B[(B.player==pl)&(B.slot==g)]
            if not len(d): d=B[B.player==pl]          # fall back to his overall record
            if not len(d): continue
            sd=float(d.sr_delta.mean()); w=float(d.share.mean()) or 0.1
            num+=sd*w; den+=w
            if sd<worst[1]: worst=(pl,sd)
        q=(num/den) if den>0 else None
        out.append(dict(slot=g,balls=balls,quality=q,
                        occupant=(worst[0] or men[0]),n=len(men)))
    return pd.DataFrame(out)


def vacancies(P, team, bench_bat, bench_bowl, add=(), drop=()):
    """Holes in a squad's best XII -- batting AND bowling, both judged the same way.

       Every hole is now the same statement: over the balls this role actually
       sees, is the side above or below what the league gets there? Both halves
       report pWAR against a league-average par of zero, so a hole and the auction
       that fills it finally speak in one currency."""
    sq=squad_pwar(P,team,add=add,drop=drop)
    xii,val,msg=optimize_xii_pwar(sq)
    if xii is None: return None,np.nan,pd.DataFrame(),msg
    rows=[]

    # ---- batting, by innings allocation against the league ----
    for a in allocate_innings(xii).itertuples():
        q=a.quality
        if q is None: q=-30.0                      # nobody for the slot at all
        # runs below the league over a season, turned into pWAR (sr_delta is per 100)
        pw=(q/100.0)*a.balls*GAMES/RPW
        if pw>=0: continue
        rows.append(dict(team=team,unit='bat',slot=a.slot,occupant=a.occupant,
                         pWAR=pw,par=0.0,req_kind=None,
                         gap=-pw,weight=BAT_W.get(1,1.0) if a.slot=='Opener' else 1.0,
                         gap_value=-pw))

    # ---- bowling, by allocated overs against the league ----
    for a in allocate_overs(xii,sq).itertuples():
        q=a.quality
        if q is None: q=-2.0
        runs=q*(PHASE_BALLS[a.phase]/6.0)*GAMES
        if a.uncovered>0: runs-=a.uncovered/6.0*2.0*GAMES
        pw=runs/RPW
        if pw>=0: continue
        k=str(a.kind or '')
        kind='spin' if 'spin' in k else ('pace' if k else None)
        rows.append(dict(team=team,unit='bowl',slot=a.phase,occupant=a.occupant,
                         pWAR=pw,par=0.0,req_kind=kind,
                         gap=-pw,weight=BOWL_W.get(a.phase,1.0),gap_value=-pw*BOWL_W.get(a.phase,1.0)))

    v=pd.DataFrame(rows)
    if len(v): v=v.sort_values('gap_value',ascending=False).groupby(['team','unit','slot'],as_index=False).first()
    return xii,val,v,'ok'

# ---------------------------------------------------------------- purse
CAP = 130.0          # IPL 2027 salary cap. Official spent + remaining = 130.00 for
                     # every one of the ten clubs, which is the rule stated plainly.

USE_OFFICIAL_PURSE = True   # set False when evaluating a ROLLED-BACK state: the
                            # announced purse describes today, so applying it to
                            # the world before trade 4 would hand a club money it
                            # had not yet freed.

def official_purse():
    """Announced remaining purse per club, when the league has published it.

       The purse used to be rebuilt from last season's carry-over plus a 6 crore
       top-up. That is a reconstruction, and it drifted: against the announced
       figures it was 21.8 crore light on LSG and 8 crore light on SRH, which
       flows straight into bidding power, recovery probability and every net
       value on the site.

       The rule is simply cap minus committed salary, so that is what is computed
       below -- and where the league has announced the number, that is used
       instead, because an announced purse is a fact and a computed one is only
       as good as the salary table behind it. Same fallback shape as the release
       list: drop the file in, it takes over; leave it out, the model computes."""
    if not USE_OFFICIAL_PURSE: return {}
    f=_os.path.join(_DATA,'purse_2027_official.csv')
    if not _os.path.isfile(f): return {}
    try:
        d=pd.read_csv(f)
        return {str(r.team).strip(): float(r.purse) for r in d.itertuples()}
    except Exception:
        return {}


def purse_and_slots(P, releases, trades=None):
    """Purse and open squad slots per club.

       `trades` are HYPOTHETICAL moves being evaluated now; completed trades are
       already baked into P. So the baseline is the club's purse as it stands,
       and the hypothetical trade is applied on top of it."""
    trades=trades or []; traded=set(t['player'] for t in trades)
    OFF=official_purse(); rows=[]
    for tm in sorted(CARRY):
        sq=P[P.team==tm]
        rel=[r for r in releases.get(tm,[]) if r not in traded]
        freed=float(sq[sq.player.isin(rel)].salary.sum())
        on_books=sq[~sq.player.isin(rel)]
        committed=float(on_books.salary.fillna(0).sum())
        computed=CAP-committed
        base=OFF.get(tm, computed)
        # The IPL rule, stated plainly: the SELLING club frees the player's FULL
        # ORIGINAL fee, and the BUYING club is charged the NEW negotiated fee. The
        # difference simply leaves the league's books -- that is why Delhi freed
        # 10.75 on Natarajan while Hyderabad paid only 5.00.
        #
        # The original fee used to be read out of the selling club's own squad
        # rows, which silently returned ZERO whenever the player was not currently
        # listed there -- an all-cash sale with nobody coming back the other way,
        # or any evaluation run against data where the move has already been
        # applied. Harshal Patel left Hyderabad for four crore and Hyderabad's
        # purse did not move at all. The fee is now looked up across the whole
        # player table, with an explicit prev_fee on the trade winning if given.
        def _orig(t):
            if t.get('prev_fee') is not None: return float(t['prev_fee'])
            r=P[P.player==t['player']]
            if len(r) and pd.notna(r.salary.iloc[0]): return float(r.salary.iloc[0])
            return float(t.get('new_salary') or 0.0)
        out=sum(_orig(t) for t in trades if t['from']==tm)
        inn=sum(float(t['new_salary']) for t in trades if t['to']==tm)
        p=base+out-inn
        n_out=sum(1 for t in trades if t['from']==tm)
        n_in=sum(1 for t in trades if t['to']==tm)
        final=len(sq)-n_out+n_in-len(rel)
        rows.append(dict(team=tm,committed=round(committed,2),computed=round(computed,2),
                         base=round(base,2),trade_out=out,trade_in=inn,
                         releases=freed,n_rel=len(rel),purse=p,
                         slots=max(MAX_SQUAD-final,0),
                         purse_src=('announced' if tm in OFF else 'computed')))
    return pd.DataFrame(rows).set_index('team')

# ---------------------------------------------------------------- recovery
def recovery(pool, vac, purse, slots, pm2, sims=200, seed=7):
    """Can the vacancy be filled, and filled AT PAR, from the auction pool?"""
    if not len(vac): return pd.DataFrame()
    rng=np.random.default_rng(seed); out=[]
    for v in vac.itertuples():
        cand=pool[(pool.bat_group==v.slot)|(pool.bat_group.isna())]
        if not len(cand): out.append(dict(slot=v.slot,p_fill=0.0,p_at_par=0.0,e_pWAR=np.nan)); continue
        fills=at_par=0; q=[]
        for _ in range(sims):
            k=max(int(rng.poisson(max(len(cand)/6,1))),1)
            draw=cand.sample(min(k,len(cand)),replace=False,random_state=int(rng.integers(1e9)))
            aff=draw[draw.apply(lambda r: market_fair2(r,pm2),axis=1)<=purse]
            if len(aff):
                fills+=1; best=aff.pWAR.max(); q.append(best)
                if best>=v.par: at_par+=1
        out.append(dict(slot=v.slot,occupant=v.occupant,par=round(v.par,2),
            p_fill=fills/sims,p_at_par=at_par/sims,e_pWAR=round(np.mean(q),2) if q else np.nan))
    return pd.DataFrame(out)

# ---------------------------------------------------------------- league
def team_strength(xii_values):
    """XII value is a weighted pWAR sum; convert to expected wins.  An average side
       wins 7 of 14 and a replacement side 4.2, so the league mean XII value must map
       to 2.8 wins above replacement.  One scale factor, calibrated not guessed."""
    m=np.mean(list(xii_values.values())); k=2.8/m
    return {t: REPL_WIN*GAMES + v*k for t,v in xii_values.items()}, k

def wp(a,b): return float(np.clip(0.5+((a-b)/GAMES*RPW)*DENS,0.02,0.98))
def simulate(strength, sims=8000, seed=11):
    rng=np.random.default_rng(seed); N=list(strength); n=len(N); S=np.array([strength[t] for t in N])
    t4=np.zeros(n); t2=np.zeros(n); ti=np.zeros(n)
    P=np.array([[wp(S[i],S[j]) if i!=j else .5 for j in range(n)] for i in range(n)])
    for _ in range(sims):
        w=np.zeros(n)
        for i in range(n):
            for j in range(i+1,n):
                for _k in range(2):
                    if rng.random()<P[i,j]: w[i]+=1
                    else: w[j]+=1
        o=np.argsort(-(w+rng.random(n)*1e-6))
        t4[o[:4]]+=1; t2[o[:2]]+=1
        q1,q2,e1,e2=o[0],o[1],o[2],o[3]
        wq1=q1 if rng.random()<wp(S[q1],S[q2]) else q2; lq1=q2 if wq1==q1 else q1
        wel=e1 if rng.random()<wp(S[e1],S[e2]) else e2
        wq2=lq1 if rng.random()<wp(S[lq1],S[wel]) else wel
        ti[wq1 if rng.random()<wp(S[wq1],S[wq2]) else wq2]+=1
    return pd.DataFrame({'team':N,'p_top4':100*t4/sims,'p_top2':100*t2/sims,'p_title':100*ti/sims}).set_index('team')
