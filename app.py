"""IPL TRADE VALUES  --  streamlit run app.py"""
import os, sys, json, base64
import streamlit as st, streamlit.components.v1 as C
HERE = os.path.dirname(os.path.abspath(__file__))
SRC, DATA = os.path.join(HERE, "src"), os.path.join(HERE, "Datasets")
# Modules may sit in src/ or beside app.py depending on how the repo was uploaded;
# both are searched so a file in either place is found.
for _p in (SRC, HERE):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

st.set_page_config(page_title="IPL Trade Values", layout="wide", initial_sidebar_state="collapsed")
from shell import hero, splash, boot_splash
from render import featured, trade_pair, CSS as CARDCSS

boot_splash(); hero()

NAV = ["Featured trades", "Trade simulator", "Team opportunities", "Player rankings", "Methodology", "Contact"]
if "tab" not in st.session_state: st.session_state.tab = NAV[0]
st.markdown('<div class="navwrap">', unsafe_allow_html=True)
cols = st.columns(len(NAV)); clicked = None
for i, n in enumerate(NAV):
    if cols[i].button(n, key=f"nav{i}", use_container_width=True): clicked = n
if clicked: st.session_state.tab = clicked
for i, n in enumerate(NAV):
    cols[i].markdown('<div class="%s"></div>' % ('navon' if st.session_state.tab == n else 'navoff'),
                     unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
TAB = st.session_state.tab

# ---------------------------------------------------------------- FEATURED
if TAB == "Featured trades":
    D = json.load(open(os.path.join(DATA, "featured.json")))
    C.html('<body style="margin:0;background:#F7F5EE">' + featured(D) + '</body>',
           height=3500, scrolling=False)

# ---------------------------------------------------------------- OPPORTUNITIES
elif TAB == "Team opportunities":
    import pandas as pd
    import engine, opportunities as OP
    from render import trade_pair, CSS as RCSS
    if not st.session_state.get("_eng"):
        b = splash("Loading squads, purses and the no-trade baseline", vh=34, size=25)
        engine.boot(); b.empty(); st.session_state["_eng"] = True
    B = engine.boot()
    st.markdown('<div class="sechead">Team Opportunities</div><p>The side each franchise last '
                'put out, set against par, and what could be done about the gaps.</p>',
                unsafe_allow_html=True)
    team = st.selectbox("Team", B['teams'], index=B['teams'].index('CSK'))
    R = OP.report(team, top=None, B=B)
    S = R['summary']

    m = st.columns(5)
    m[0].metric("Best XII now", f"{S['xii_value']:.2f}")
    m[1].metric("After the auction", f"{S['xii_after_auction']:.2f}", f"{S['recovery']:+.2f}")
    m[2].metric("Purse after releases", f"\u20b9{S['purse']:.2f} cr")
    m[3].metric("Squad slots free", S['slots'])
    m[4].metric("Holes in the XII", S['holes'])

    st.markdown('<div style="font-family:Archivo,sans-serif;font-weight:700;font-size:12px;'
                'letter-spacing:.7px;text-transform:uppercase;color:#6B7A6F;margin:24px 0 6px">'
                f'{OP.FULL_NAME.get(team, team)} 2026</div>', unsafe_allow_html=True)
    p = R['positions'].copy()
    p['overseas'] = p.overseas.map({1: "Overseas", 0: "Indian"})
    p = p[['bat_slot', 'group', 'basis', 'player', 'pWAR', 'par', 'gap',
           'importance', 'gap_value', 'status', 'overseas']]
    p.columns = ['Slot', 'Position', 'Against', 'Player', 'Projected WAR',
                 'Par', 'Shortfall', 'Importance', 'Weighted shortfall', 'Verdict',
                 'Nationality']
    st.dataframe(p, hide_index=True, use_container_width=True)

    H = R['holes']
    if not len(H):
        st.success(f"Nothing in {team}'s last XII sits more than {OP.HOLE_TOL} WAR below par.")
    else:
        st.markdown('<div style="font-family:Archivo,sans-serif;font-weight:700;font-size:12px;'
                    'letter-spacing:.7px;text-transform:uppercase;color:#6B7A6F;margin:26px 0 6px">'
                    'The holes worth fixing</div>', unsafe_allow_html=True)
        h = H.copy()
        for c in ['p_fill', 'p_at_par']:
            h[c] = (h[c] * 100).round(0).astype('Int64').astype(str).replace('<NA>', '\u2014') + '%'
        h = h[['slot', 'basis', 'occupant', 'pWAR', 'par', 'gap', 'gap_value',
               'pool_n', 'pool_at_par', 'pool_affordable', 'best_available', 'p_fill', 'p_at_par']]
        h.columns = ['Position', 'Against', 'Current occupant', 'His WAR', 'Par',
                     'Shortfall', 'Weighted shortfall', 'Players in the pool', 'Of those, at par',
                     'At par and affordable', 'Best available', 'Fills at all', 'Fills at par']
        st.dataframe(h, hide_index=True, use_container_width=True)

        st.markdown('<div style="font-family:Archivo,sans-serif;font-weight:700;font-size:12px;'
                    'letter-spacing:.7px;text-transform:uppercase;color:#6B7A6F;margin:30px 0 6px">'
                    'Trades that could be made</div>'
                    '<p style="margin-top:0">Only players their own club can afford to lose, and '
                    'only deals that leave the other side close to level.</p>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        pick_slot = c1.selectbox("Which hole", H.slot.tolist(), key="oppslot")
        go = c2.button("Recommend trades", type="primary", use_container_width=True)
        if go:
            box = splash("Re-solving both XIs for every candidate on the other nine squads", vh=30, size=22)
            PK = OP.package(team, slot=pick_slot, top=8, C=B)
            P = PK.get('packages')
            good = P[P.both_gain] if (P is not None and len(P)) else None
            html = OP.confirm(team, good, B, top=3) if (good is not None and len(good)) else []
            box.empty()
            if not html:
                st.info("No deal here passes the fair value test.")
            else:
                for k, (ev, r) in enumerate(html, 1):
                    st.markdown(f'<div style="font-family:Archivo,sans-serif;font-weight:700;'
                                f'font-size:12px;letter-spacing:.6px;text-transform:uppercase;'
                                f'color:#9A7B1B;margin:20px 0 2px">Option {k}</div>',
                                unsafe_allow_html=True)
                    C.html('<body style="margin:0;background:#F7F5EE"><style>%s</style>'
                           '<div class="wrap">%s</div></body>' % (RCSS, trade_pair(ev)),
                           height=490, scrolling=False)
                    if r.replaces:
                        st.markdown(
                            f'<div style="border-left:3px solid #C9A227;padding:7px 0 7px 13px;'
                            f'margin:2px 0 8px;font-family:\'Source Serif 4\',Georgia,serif;'
                            f'font-size:14px;color:#4A5A50">{r.replaces}</div>',
                            unsafe_allow_html=True)
                    with st.expander("More analysis"):
                        r0, r1 = ev['rows']
                        dw = lambda x: x['xii_yes'] - x['xii_no']
                        dt = lambda x: x['title_yes'] - x['title_no']
                        brk = pd.DataFrame({"Where the value came from":
                            ["Change in best XII", "Title probability, in points", "Asset value, \u20b9cr",
                             "Purse after the trade, \u20b9cr", "Net value"],
                            r0['team']: [f"{dw(r0):+.2f}", f"{dt(r0):+.1f}", f"{r0['assets']:+.2f}",
                                         f"{r0['purse_yes']:.2f}", f"{r0['util']:+.2f}"],
                            r1['team']: [f"{dw(r1):+.2f}", f"{dt(r1):+.1f}", f"{r1['assets']:+.2f}",
                                         f"{r1['purse_yes']:.2f}", f"{r1['util']:+.2f}"]})
                        st.dataframe(brk, hide_index=True, use_container_width=True)
                        if ev.get('holes'):
                            h = pd.DataFrame(ev['holes']).groupby('team').agg(
                                H=('slot', 'size'), F=('p_fill', 'mean'), P=('p_at_par', 'mean'),
                                R=('recovery', 'sum')).reset_index()
                            h.columns = ['Team', 'Holes after the trade', 'Fills at all',
                                         'Fills at the required standard', 'Expected recovery (WAR)']
                            for c in ['Fills at all', 'Fills at the required standard']:
                                h[c] = (h[c] * 100).round(0).astype(int).astype(str) + '%'
                            st.dataframe(h.round(2), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- SIMULATOR
elif TAB == "Trade simulator":
    import engine
    if not st.session_state.get("_eng"):
        b = splash("Loading squads, purses and the no-trade baseline", vh=34, size=25)
        engine.boot(); b.empty(); st.session_state["_eng"] = True
    B = engine.boot(); TEAMS, SQ = B['teams'], B['squads']
    st.markdown('<div class="sechead">Trade Simulator</div><p>Build any deal between two squads. '
                'Salaries pre-fill from the 2026 contract and stay editable.</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    A = c1.selectbox("Team A", TEAMS, index=TEAMS.index('CSK'))
    B_ = c2.selectbox("Team B", [t for t in TEAMS if t != A], index=0)

    def pick(col, label, src, key):
        col.markdown(f'<div style="font-family:Archivo,sans-serif;font-weight:700;font-size:11px;'
                     f'letter-spacing:.7px;text-transform:uppercase;color:#6B7A6F;margin:16px 0 3px">'
                     f'{label}</div>', unsafe_allow_html=True)
        out = []
        for i in range(3):
            n = col.selectbox(f"p{i}", ["—"] + SQ.get(src, []), key=f"{key}p{i}",
                              label_visibility="collapsed")
            if n == "—": continue
            cur = engine.salary_of(n)
            s = col.number_input(f"{n} — salary ₹cr (was ₹{cur:.2f})", value=cur, step=0.05,
                                 key=f"{key}s{i}_{n}")
            out.append((n, float(s)))
        return out
    ag = pick(c1, f"{A} receives", B_, "a")
    bg = pick(c2, f"{B_} receives", A, "b")

    if st.button("Evaluate trade", type="primary", use_container_width=True):
        if not ag and not bg:
            st.warning("Pick at least one player.")
        else:
            box = splash("Re-optimising both XIs, running the auction and the season", vh=34, size=25)
            res = engine.evaluate(A, B_, [p for p, _ in ag], [p for p, _ in bg],
                                  {p: s for p, s in ag + bg})
            box.empty()
            poor = res.get('unaffordable', [])
            if poor:
                who = " and ".join(poor)
                st.markdown(f'''<div style="background:#FFF6E6;border:1.5px solid #E6C98A;border-radius:10px;
                  padding:16px 22px;margin-top:8px">
                  <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:14px;color:#8A5A08;
                    margin-bottom:5px">{who} cannot afford this trade</div>
                  <div style="font-family:'Source Serif 4',Georgia,serif;font-size:14px;color:#7A5A2A;
                    line-height:1.6">The incoming salary is larger than the purse available after releases.
                    They would need to free up more money first, so the numbers below assume they somehow
                    could.</div></div>''', unsafe_allow_html=True)
            bad = res.get('infeasible', [])
            if bad:
                who = " and ".join(bad)
                st.markdown(f'''<div style="background:#FCEDED;border:1.5px solid #E4B4B4;border-radius:10px;
                  padding:18px 22px;margin-top:8px">
                  <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:15px;color:#9B2226;
                    margin-bottom:6px">This trade cannot be made</div>
                  <div style="font-family:'Source Serif 4',Georgia,serif;font-size:14.5px;color:#7A3A3A;
                    line-height:1.6">{who} cannot field a legal side even with replacement-level cover.
                    Send back a player who fills the gap, or take fewer players away.</div></div>''', unsafe_allow_html=True)
            else:
                C.html('<body style="margin:0;background:#F7F5EE"><style>%s</style><div class="wrap">%s</div>'
                       '</body>' % (CARDCSS, trade_pair(res)), height=490, scrolling=False)
                with st.expander("More analysis"):
                    import pandas as pd
                    r0, r1 = res['rows']
                    dw = lambda r: r['xii_yes'] - r['xii_no']
                    dt = lambda r: r['title_yes'] - r['title_no']
                    brk = pd.DataFrame({"Where the value came from":
                        ["Change in best XII", "Title probability, in points", "Asset value, ₹cr",
                         "Purse after the trade, ₹cr", "Net value"],
                        r0['team']: [f"{dw(r0):+.2f}", f"{dt(r0):+.1f}", f"{r0['assets']:+.2f}",
                                     f"{r0['purse_yes']:.2f}", f"{r0['util']:+.2f}"],
                        r1['team']: [f"{dw(r1):+.2f}", f"{dt(r1):+.1f}", f"{r1['assets']:+.2f}",
                                     f"{r1['purse_yes']:.2f}", f"{r1['util']:+.2f}"]})
                    st.dataframe(brk, hide_index=True, use_container_width=True)
                    if res.get('holes'):
                        h = pd.DataFrame(res['holes']).groupby('team').agg(
                            H=('slot', 'size'), F=('p_fill', 'mean'), P=('p_at_par', 'mean'),
                            R=('recovery', 'sum')).reset_index()
                        h.columns = ['Team', 'Holes after the trade', 'Fills at all',
                                     'Fills at the required standard', 'Expected recovery (WAR)']
                        for c in ['Fills at all', 'Fills at the required standard']:
                            h[c] = (h[c] * 100).round(0).astype(int).astype(str) + '%'
                        st.dataframe(h.round(2), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- RANKINGS
elif TAB == "Player rankings":
    import pandas as pd
    st.markdown('<div class="sechead">Player Rankings</div><p>Every player with an IPL record, valued on '
                'one scale.</p>', unsafe_allow_html=True)
    d = pd.read_csv(os.path.join(DATA, "final_pwar.csv"))
    d = d[d.source.astype(str).str.contains("IPL", na=False)].copy()
    d['capped'] = d.capped.map({1: "Capped", 0: "Uncapped"}).fillna("Uncapped")
    d['overseas'] = d.overseas.map({1: "Overseas", 0: "Indian"}).fillna("Indian")
    d = d[['player', 'pWAR_final', 'team', 'role', 'salary', 'capped', 'overseas',
           'bat_group', 'bowl_phase', 'bowl_kind']]
    d.columns = ['Player', 'Projected WAR', 'Team', 'Role', 'Salary (₹cr)', 'Capped status',
                 'Nationality', 'Batting position', 'Bowling phases', 'Bowling type']
    f1, f2, f3, f4 = st.columns(4)
    tm = f1.selectbox("Team", ["All"] + sorted(d.Team.dropna().unique()))
    ro = f2.selectbox("Role", ["All"] + sorted(d.Role.dropna().unique()))
    bg = f3.selectbox("Batting position", ["All"] + sorted(d['Batting position'].dropna().unique()))
    na = f4.selectbox("Nationality", ["All", "Indian", "Overseas"])
    for col, v in [('Team', tm), ('Role', ro), ('Batting position', bg), ('Nationality', na)]:
        if v != "All": d = d[d[col] == v]
    d = d.sort_values('Projected WAR', ascending=False).reset_index(drop=True)
    st.caption(f"{len(d)} players")
    head = "".join(f"<th>{c}</th>" for c in ["#"] + list(d.columns))
    rows = ""
    for i, r in d.iterrows():
        cells = "".join(
            f"<td>{'' if pd.isna(v) else (f'{v:.2f}' if isinstance(v, float) else v)}</td>"
            for v in r)
        rows += f"<tr><td>{i+1}</td>{cells}</tr>"
    st.markdown(f'<div class="rkwrap"><table class="rk"><thead><tr>{head}</tr></thead>'
                f'<tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- METHODOLOGY
elif TAB == "Methodology":
    import article
    L, M, R = st.columns([1, 5.2, 1])
    with M:
        st.markdown(f'''<div style="font-family:'Archivo',sans-serif;font-weight:900;font-size:42px;
          line-height:1.06;letter-spacing:-1.4px;color:#16281C;margin:12px 0 16px;text-transform:uppercase">
          {article.TITLE}</div>
          <div style="border-top:1px solid #E0DACA;border-bottom:1px solid #E0DACA;padding:12px 0">
          <div style="font-family:'Archivo',sans-serif;font-weight:800;font-size:15px;color:#16281C;
            letter-spacing:.04em;text-transform:uppercase">{article.BY}</div>''',
          unsafe_allow_html=True)
        st.markdown('<div class="essay">', unsafe_allow_html=True)
        for b in article.B:
            if b[0] == 't':   st.markdown(b[1])
            elif b[0] == 'h': st.markdown(f"### {b[1]}")
            elif b[0] == 'H': st.markdown(f"## {b[1]}")
            elif b[0] == 'f': st.latex(b[1])
            else:
                enc = base64.b64encode(open(os.path.join(DATA, b[1]), 'rb').read()).decode()
                st.markdown(f'<div class="figbox"><img src="data:image/png;base64,{enc}"></div>',
                            unsafe_allow_html=True)
                if b[2]: st.markdown(f'<div class="figcap">{b[2]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- CONTACT
else:
    st.markdown('<div class="sechead">Contact</div><p>Questions, corrections and franchise enquiries '
                'are all welcome.</p>', unsafe_allow_html=True)
    st.markdown('''<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;max-width:680px">
      <a href="mailto:omkarvwalunj45@gmail.com" style="text-decoration:none"><div style="background:#fff;
        border:1.5px solid #E0DACA;border-radius:12px;padding:18px 20px">
        <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8A9490">Email</div>
        <div style="font-size:15px;font-weight:600;color:#16281C;margin-top:5px">omkarvwalunj45@gmail.com</div>
      </div></a>
      <a href="https://substack.com/@theunseengame" target="_blank" style="text-decoration:none">
        <div style="background:#fff;border:1.5px solid #E0DACA;border-radius:12px;padding:18px 20px">
        <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8A9490">Substack</div>
        <div style="font-size:15px;font-weight:600;color:#16281C;margin-top:5px">The Unseen Game</div>
      </div></a>
      <a href="https://twitter.com/the_cricketest" target="_blank" style="text-decoration:none">
        <div style="background:#fff;border:1.5px solid #E0DACA;border-radius:12px;padding:18px 20px">
        <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8A9490">Twitter</div>
        <div style="font-size:15px;font-weight:600;color:#16281C;margin-top:5px">@the_cricketest</div>
      </div></a>
      <a href="https://www.linkedin.com/in/omkar-walunj-8256a4280/" target="_blank" style="text-decoration:none">
        <div style="background:#fff;border:1.5px solid #E0DACA;border-radius:12px;padding:18px 20px">
        <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8A9490">LinkedIn</div>
        <div style="font-size:15px;font-weight:600;color:#16281C;margin-top:5px">Omkar Walunj</div>
      </div></a></div>''', unsafe_allow_html=True)
