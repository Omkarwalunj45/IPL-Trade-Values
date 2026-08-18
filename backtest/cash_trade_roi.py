import warnings, os, sys; warnings.filterwarnings('ignore'); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import pandas as pd, numpy as np, war3
from names import fix
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'validate_projection.py')).read().split("V = {y:")[0])          # reuse prep/vintage/actual
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Datasets')
cash = pd.read_csv(os.path.join(DATA,'ipl_cash_trades.csv'))
cash['Player'] = fix(cash.Player)
cash = cash[cash.Year.isin([2021,2023,2024])].copy()         # vintage WAR exists for these
V = {y: vintage(y).set_index('player') for y in sorted(cash.Year.unique())}
rows=[]
for r in cash.itertuples():
    v = V[r.Year]
    before = float(v.loc[r.Player,'WAR']) if r.Player in v.index else np.nan
    after  = actual(r.Player, [r.Year, r.Year+1])
    fee = float(r._6)
    rows.append(dict(year=r.Year, player=r.Player, frm=r.From, to=r.To, fee=fee,
        war_before=round(before,2) if pd.notna(before) else np.nan,
        war_after=round(after,2) if pd.notna(after) else np.nan,
        exp_cost_per_war=round(fee/before,1) if (pd.notna(before) and before>0.05) else np.nan,
        real_cost_per_war=round(fee/after,1) if (pd.notna(after) and after>0.05) else np.nan))
B=pd.DataFrame(rows).sort_values(['year','fee'],ascending=[True,False])
B.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),'cash_trade_roi.csv'),index=False)
print(B.to_string(index=False))
