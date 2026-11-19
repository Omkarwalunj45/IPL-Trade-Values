# -*- coding: utf-8 -*-
"""Rebuild the Featured cards, each against the world it actually faced.

    python tools/rebuild_featured.py            # print, change nothing
    python tools/rebuild_featured.py --write    # write Datasets/featured.json

Why this exists
---------------
final_pwar.csv holds today's squads: every completed trade is already in it.
That is right for the simulator, because a user building a new deal should start
from the squads as they stand. It is wrong for the cards. Trade 4 did not happen
in a world where trades 5 and 6 had already been done, so pricing it against
today's squads charges Delhi for a Pant deal they had not yet made.

So each card is built after rolling the squads back to just before its own
trade, using core.rewind(). The rollback is applied by swapping final_pwar.csv
for the rolled-back frame, booting the engine against it, and restoring the file
afterwards -- the engine caches a great deal at boot, and this is the one way to
get a clean state without threading an as-of date through every call.

Run it in trade order and each deal is priced against the purse and squads left
by the ones before it, which is what "chained" means here.
"""
import os, sys, shutil, argparse, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
DATA = os.path.join(ROOT, 'Datasets')
PWAR = os.path.join(DATA, 'final_pwar.csv')


def evaluate_at(n, tA, tB, a_gets, b_gets, sal):
    """Evaluate a trade against the squads as they stood just before trade n."""
    import importlib, pandas as pd
    import core
    importlib.reload(core)
    rolled = core.squads_before(n)
    bak = PWAR + '.asof_backup'
    shutil.copy2(PWAR, bak)
    try:
        rolled.to_csv(PWAR, index=False)
        for m in ('core', 'ipl_trade_optimizer', 'trade', 'trade_eval', 'fast',
                  'entrants', 'engine'):
            if m in sys.modules: importlib.reload(sys.modules[m])
        import trade, core as _c
        # the announced purse describes today, not the world before trade n
        trade.USE_OFFICIAL_PURSE = False
        # and every completed trade was made before the retention deadline, when
        # the only release information in existence was the projection
        _c.USE_ANNOUNCED_RELEASES = False
        import ipl_trade_optimizer as _io
        _io._REL_CACHE.clear()
        import engine
        importlib.reload(engine)
        engine._C.clear()
        engine.boot()
        return engine.evaluate(tA, tB, a_gets, b_gets, sal)
    finally:
        shutil.move(bak, PWAR)
        try:
            import trade as _t; _t.USE_OFFICIAL_PURSE = True
            import core as _cc; _cc.USE_ANNOUNCED_RELEASES = True
            import ipl_trade_optimizer as _io2; _io2._REL_CACHE.clear()
        except Exception: pass
        for m in ('core', 'ipl_trade_optimizer', 'trade', 'trade_eval', 'fast',
                  'entrants', 'engine'):
            if m in sys.modules: importlib.reload(sys.modules[m])
        import engine as _e
        _e._C.clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', type=int, default=0, help='rebuild one trade number')
    a = ap.parse_args()

    import core, pandas as pd
    T = core.completed_trades()
    if not len(T):
        print('no trades_2027.csv -- nothing to rebuild'); return

    out = []
    for n, g in T.groupby('trade'):
        if a.only and n != a.only: continue
        label = g.label.iloc[0]
        teams = sorted(set(g.from_team) | set(g.to_team))
        if len(teams) != 2:
            print('  ! trade %d touches %s -- skipped, needs exactly two clubs'
                  % (n, teams)); continue
        tA, tB = teams
        a_gets = list(g[g.to_team == tA].player)
        b_gets = list(g[g.to_team == tB].player)
        sal = {r.player: float(r.fee) for r in g.itertuples()}
        print('\n--- trade %d: %s' % (n, label))
        print('    %s receives %s | %s receives %s' % (tA, a_gets or '-', tB, b_gets or '-'))
        try:
            res = evaluate_at(n, tA, tB, a_gets, b_gets, sal)
        except Exception as e:
            print('    ! failed: %s' % e); continue
        for r in res['rows']:
            print('    %-4s xii %.2f->%.2f  top4 %.1f->%.1f  purse %.2f->%.2f  util %+.2f'
                  % (r['team'], r['xii_no'], r['xii_yes'], r['top4_no'], r['top4_yes'],
                     r['purse_no'], r['purse_yes'], r['util']))
        out.append((n, label, tA, tB, res))

    if a.write and out:
        print('\n--write given: merging into featured.json is left as the next step '
              'so the card copy (label, note, prev fees) is not clobbered.')


if __name__ == '__main__':
    main()
