"""Shared card renderer. One trade = a tall pair: the deal, and what it changed."""
CLR = {'CSK':('#F2B705','#1a1a1a','Chennai Super Kings'),'MI':('#0B5EA8','#fff','Mumbai Indians'),
 'RCB':('#B3282D','#fff','Royal Challengers Bengaluru'),'KKR':('#4A2A6B','#fff','Kolkata Knight Riders'),
 'RR':('#D5257E','#fff','Rajasthan Royals'),'DC':('#1B4B9C','#fff','Delhi Capitals'),
 'SRH':('#E2643B','#fff','Sunrisers Hyderabad'),'PBKS':('#C4303C','#fff','Punjab Kings'),
 'GT':('#232B3A','#fff','Gujarat Titans'),'LSG':('#0E7C9B','#fff','Lucknow Super Giants')}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
*{box-sizing:border-box}
body{margin:0;background:#F7F5EE;font-family:'IBM Plex Sans',sans-serif;color:#1a1a1a}
.wrap{max-width:960px;margin:0 auto;padding:4px 4px 44px}
h2.sec{font-family:'Archivo',sans-serif;font-weight:800;font-size:40px;letter-spacing:-1.1px;
  text-transform:uppercase;margin:4px 0 6px}
.lede{font-family:'Source Serif 4',Georgia,serif;font-size:13px;color:#8a8474;margin:0 0 24px}
.yr{display:flex;align-items:center;gap:12px;margin:28px 0 14px}
.yr span{font-family:'Archivo',sans-serif;font-weight:700;font-size:13.5px;letter-spacing:1.4px}
.yr .ln{flex:1;height:1px;background:#ded9cf}
.row{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px;align-items:stretch}
.card{background:#fff;border:1.5px solid #E0DACA;border-radius:12px;display:flex;flex-direction:column;min-height:418px;overflow:visible;box-shadow:0 1px 3px rgba(22,40,28,.05),0 8px 24px rgba(22,40,28,.045)}
.chead{display:flex;align-items:center;gap:10px;padding:20px 24px 16px;border-bottom:1px solid #f0ede6;flex-wrap:wrap}
.badge{width:27px;height:27px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:'Archivo',sans-serif;font-weight:800;font-size:9px;flex-shrink:0}
.tname{font-family:'Archivo',sans-serif;font-weight:700;font-size:12px}
.swap{color:#c3bdb0;font-size:14px}
.ctitle{padding:20px 24px 0;font-family:'Archivo',sans-serif;font-weight:700;font-size:10.5px;
  letter-spacing:.9px;text-transform:uppercase;color:#8a8474}
.cbody{display:flex;flex:1}
.blk{flex:1;padding:19px 23px 18px;display:flex;flex-direction:column}
.blk+.blk{border-left:1px solid #e6e3dc}
.gets{font-family:'Archivo',sans-serif;font-size:11px;letter-spacing:.7px;text-transform:uppercase;color:#3d3a34;font-weight:700;margin-bottom:7px;display:flex;align-items:center;gap:6px}
.hdr{display:flex;justify-content:space-between;font-size:8.6px;letter-spacing:.6px;text-transform:uppercase;color:#6b6459;font-weight:600;border-bottom:1px solid #1a1a1a;padding-bottom:5px}
.chip{position:relative;display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;
  border-bottom:1px dotted #eae6dd}
.chip:last-of-type{border-bottom:none}
.pn{font-size:13.5px;font-weight:500;border-bottom:1px dotted #c9c3b6;cursor:help}
.pv{font-size:13.5px;font-variant-numeric:tabular-nums;font-weight:600}
.none{font-size:12.5px;color:#b5afa2;padding:7px 0}
.pop{visibility:hidden;opacity:0;position:absolute;left:0;top:calc(100% + 3px);z-index:70;width:224px;
  background:#1f1d1a;color:#f3f0e9;border-radius:7px;padding:11px 13px;font-size:11.5px;line-height:1.7;
  box-shadow:0 10px 26px rgba(0,0,0,.26);transition:opacity .12s;pointer-events:none}
.chip:hover .pop{visibility:visible;opacity:1}
.pop b{font-family:'Archivo',sans-serif;font-size:12.5px;display:block;margin-bottom:4px;color:#fff}
.pop span{float:right;font-variant-numeric:tabular-nums}
.pop .ln{border-top:1px solid #3d3936;margin:6px 0 5px}
.net{display:flex;justify-content:space-between;align-items:baseline;margin-top:auto;padding-top:9px;
  border-top:1.4px solid #1a1a1a}
.net .l{font-family:'Archivo',sans-serif;font-weight:700;font-size:10px;letter-spacing:.7px;text-transform:uppercase;color:#6b6459}
.net .v{font-family:'Archivo',sans-serif;font-weight:800;font-size:17px;font-variant-numeric:tabular-nums}
.bar{height:7px;display:flex;border-radius:0 0 9px 9px;overflow:hidden;margin-top:auto}
table.m{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:6px}
table.m th{font-size:9px;letter-spacing:.6px;text-transform:uppercase;color:#a8a294;font-weight:600;
  padding:0 8px 7px;text-align:right;border-bottom:1px solid #1a1a1a}
table.m th:first-child{text-align:left}
table.m td{padding:11px 8px;text-align:right;border-bottom:.5px solid #f2efe8;font-variant-numeric:tabular-nums}
table.m td:first-child{text-align:left;font-size:11px;letter-spacing:.3px;text-transform:uppercase;
  color:#8a8474;font-weight:600}
table.m tr:last-child td{border-bottom:none;border-top:1.4px solid #1a1a1a;padding-top:11px}
table.m tr:last-child td:not(:first-child){font-family:'Archivo',sans-serif;font-weight:800;font-size:16px}
.thc{display:inline-flex;align-items:center;gap:6px}
.tdot{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:'Archivo',sans-serif;font-weight:800;font-size:7.5px}
.up{color:#1b5e3f;font-weight:600}.dn{color:#9b2226;font-weight:600}.mut{color:#c3bdb0;padding:0 2px}
.vd{font-family:'Source Serif 4',Georgia,serif;font-size:13px;color:#4A5A50;line-height:1.6;padding:17px 24px 21px;border-top:1px solid #f0ede6;margin-top:auto}
.foot{font-family:'Source Serif 4',Georgia,serif;font-size:11.5px;color:#8a8474;line-height:1.7;
  margin-top:28px;border-top:1px solid #e6e3dc;padding-top:13px}
"""

def badge(t, cls='badge'):
    bg, fg, _ = CLR.get(t, ('#555','#fff',t))
    return f'<div class="{cls}" style="background:{bg};color:{fg}">{t}</div>'

def _pop(p):
    s = p['surplus']; c = "#7fd1a5" if s >= 0 else "#e88b8b"
    return (f'<div class="pop"><b>{p["player"]}</b>{p["role"]}<br>Projected WAR <span>{p["pWAR"]:.2f}</span><br>'
            f'Salary <span>&#8377;{p["salary"]:.2f} cr</span><br>Market value <span>&#8377;{p["market"]:.2f} cr</span>'
            f'<div class="ln"></div>Surplus <span style="color:{c}">{s:+.2f} cr</span></div>')

def _ar(a, b, pct=False, up=True):
    f = "%.1f%%" if pct else "%.2f"
    c = "" if abs(b-a) < .005 else ("up" if (b > a) == up else "dn")
    return f'{f%a}<span class="mut">&rarr;</span><span class="{c}">{f%b}</span>'

def trade_pair(t):
    """One trade -> the two-card row."""
    A, B = t['A'], t['B']; rows = {r['team']: r for r in t['rows']}
    wn = max(t['rows'], key=lambda r: r['util']); ls = min(t['rows'], key=lambda r: r['util'])
    L = ['<div class="card"><div class="chead">', badge(A), f'<div class="tname">{CLR[A][2]}</div>',
         '<span class="swap">&#8646;</span>', badge(B), f'<div class="tname">{CLR[B][2]}</div></div>',
         '<div class="cbody">']
    for tm in (A, B):
        got = [p for p in t['players'] if p['to'] == tm]
        L.append(f'<div class="blk"><div class="gets">{badge(tm,"tdot")}{tm} receives</div>'
                 '<div class="hdr"><span>Player</span><span>Proj WAR</span></div>')
        L.append(''.join(f'<div class="chip"><span class="pn">{p["player"]}</span>'
                         f'<span class="pv">{p["pWAR"]:.2f}</span>{_pop(p)}</div>' for p in got)
                 or '<div class="none">cash only</div>')
        r = rows[tm]
        L.append(f'<div class="net"><span class="l">Net value</span>'
                 f'<span class="v {"up" if r["util"]>=0 else "dn"}">{r["util"]:+.2f}</span></div></div>')
    L.append('</div>')
    w = max(4, min(96, 50 + (wn['util'] - ls['util']) * 6))
    L.append(f'<div class="bar"><div style="width:{w}%;background:{CLR[wn["team"]][0]}"></div>'
             f'<div style="flex:1;background:{CLR[ls["team"]][0]};opacity:.3"></div></div></div>')
    ra, rb = rows[A], rows[B]
    def cell(r, k, pct=False, up=True): return _ar(r[k+'_no'], r[k+'_yes'], pct, up)
    body = ''.join([
        f'<tr><td>XII value</td><td>{cell(ra,"xii")}</td><td>{cell(rb,"xii")}</td></tr>',
        f'<tr><td>Playoff odds</td><td>{cell(ra,"top4",True)}</td><td>{cell(rb,"top4",True)}</td></tr>',
        f'<tr><td>Title odds</td><td>{cell(ra,"title",True)}</td><td>{cell(rb,"title",True)}</td></tr>',
        f'<tr><td>Purse &#8377;cr</td><td>{cell(ra,"purse")}</td><td>{cell(rb,"purse")}</td></tr>',
        f'<tr><td>Assets &#8377;cr</td><td class="{"up" if ra["assets"]>=0 else "dn"}">{ra["assets"]:+.2f}</td>'
        f'<td class="{"up" if rb["assets"]>=0 else "dn"}">{rb["assets"]:+.2f}</td></tr>',
        f'<tr><td>Net value</td><td class="{"up" if ra["util"]>=0 else "dn"}">{ra["util"]:+.2f}</td>'
        f'<td class="{"up" if rb["util"]>=0 else "dn"}">{rb["util"]:+.2f}</td></tr>'])
    R = ('<div class="card"><div class="ctitle">Without the trade &rarr; with it</div>'
         '<div style="padding:6px 24px 12px"><table class="m"><tr><th></th>'
         f'<th><span class="thc">{badge(A,"tdot")}{A}</span></th>'
         f'<th><span class="thc">{badge(B,"tdot")}{B}</span></th></tr>{body}</table></div>'
         f'<div class="vd"><b>{CLR[wn["team"]][2]}</b> came out ahead, {wn["util"]:+.2f} against '
         f'{ls["util"]:+.2f}.</div></div>')
    return f'<div class="row">{"".join(L)}{R}</div>'

FOOT = ('<p class="foot"><b>Projected WAR</b> is wins above replacement: 0 is a freely available player, a '
        'regular sits near 2, the best season in the data reads 6. <b>Market value</b> is what the auction '
        'would pay, fitted on 2023&ndash;26 prices. <b>XII value</b> is the strength of the best legal twelve '
        'a squad can field. Odds come from simulated seasons. <b>Net value</b> combines all three. '
        'Hover a player name for his card.</p>')

def featured(data):
    H = [f'<style>{CSS}</style><div class="wrap"><h2 class="sec">Featured Trades</h2>'
         '<p class="lede">Every deal below is evaluated against the world in which it never happened.</p>']
    for yr in sorted({t['year'] for t in data['trades']}, reverse=True):
        H.append(f'<div class="yr"><span>{yr} WINDOW</span><div class="ln"></div></div>')
        H += [trade_pair(t) for t in data['trades'] if t['year'] == yr]
    return ''.join(H) + FOOT + '</div>'
