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
.row{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;align-items:stretch}
.card{background:#fff;border:2px solid #1D3324;border-radius:12px;display:flex;flex-direction:column;min-height:430px;overflow:visible;box-shadow:0 2px 6px rgba(29,51,36,.10),0 12px 30px rgba(29,51,36,.07)}
.chead{display:flex;align-items:center;gap:10px;padding:22px 28px 18px;border-bottom:1px solid #E7E3D8;flex-wrap:wrap}
.badge{width:27px;height:27px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:'Archivo',sans-serif;font-weight:800;font-size:9px;flex-shrink:0}
.tname{font-family:'Archivo',sans-serif;font-weight:700;font-size:12px}
.swap{color:#c3bdb0;font-size:14px}
.ctitle{padding:22px 28px 4px;font-family:'Archivo',sans-serif;font-weight:700;font-size:10.5px;letter-spacing:.9px;text-transform:uppercase;color:#8a8474}
.cbody{display:flex;flex:1}
.blk{flex:1;padding:24px 28px 22px;display:flex;flex-direction:column}
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
  padding:0 8px 7px;text-align:right;border-bottom:1px solid #1D3324}
table.m th:first-child{text-align:left;border-bottom:none}
table.m th.grp:first-child{border-bottom:none}
table.m th.grp{text-align:center;border-bottom:none;padding-bottom:3px}
table.m th.sb{font-size:8.2px;letter-spacing:.5px;color:#b5afa2;font-weight:500}
table.m td.was{color:#b0a99b;font-weight:400}
table.m td.now{font-weight:600}
table.m .div{border-left:1px solid #EFEBE1}
table.m td{padding:11px 8px;text-align:right;border-bottom:.5px solid #f2efe8;font-variant-numeric:tabular-nums}
table.m td:first-child{text-align:left;font-size:11px;letter-spacing:.3px;text-transform:uppercase;
  color:#8a8474;font-weight:600}
table.m tr:last-child td{border-bottom:none;border-top:1.4px solid #1D3324;padding-top:12px}
table.m tr:last-child td:not(:first-child){font-family:'Archivo',sans-serif;font-weight:800;font-size:16px}
.thc{display:inline-flex;align-items:center;gap:6px}
.tdot{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:'Archivo',sans-serif;font-weight:800;font-size:7.5px}
.up{color:#1b5e3f;font-weight:600}.dn{color:#9b2226;font-weight:600}.mut{color:#c3bdb0;padding:0 2px}
.vd{font-family:'Source Serif 4',Georgia,serif;font-size:13px;color:#4A5A50;line-height:1.6;padding:18px 28px 22px;border-top:1px solid #E7E3D8;margin-top:auto}
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

def _pair(a, b, pct=False, first=False):
    """Before and after as two separate cells. No arrow: the reader compares across
       the gap, which is how a broadsheet table has always presented a change."""
    f = "%.1f%%" if pct else "%.2f"
    c = "" if abs(b - a) < .005 else ("up" if b > a else "dn")
    d = " div" if first else ""
    return f'<td class="was{d}">{f%a}</td><td class="now {c}">{f%b}</td>'

def _one(v, first=False):
    """A figure with no before-state."""
    c = "up" if v >= 0 else "dn"
    d = " div" if first else ""
    return f'<td class="was{d}">&mdash;</td><td class="now {c}">{v:+.2f}</td>'

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
    def line(label, k, pct=False):
        return (f'<tr><td>{label}</td>{_pair(ra[k+"_no"], ra[k+"_yes"], pct)}'
                f'{_pair(rb[k+"_no"], rb[k+"_yes"], pct, first=True)}</tr>')
    body = ''.join([
        line('XII value', 'xii'),
        line('Playoff odds', 'top4', True),
        line('Title odds', 'title', True),
        line('Purse &#8377;cr', 'purse'),
        f'<tr><td>Assets &#8377;cr</td>{_one(ra["assets"])}{_one(rb["assets"], first=True)}</tr>',
        f'<tr><td>Net value</td>{_one(ra["util"])}{_one(rb["util"], first=True)}</tr>'])
    head = (f'<tr><th></th><th class="grp" colspan="2"><span class="thc">{badge(A,"tdot")}{A}</span></th>'
            f'<th class="grp div" colspan="2"><span class="thc">{badge(B,"tdot")}{B}</span></th></tr>'
            '<tr><th></th><th class="sb">Before</th><th class="sb">After</th>'
            '<th class="sb div">Before</th><th class="sb">After</th></tr>')
    R = ('<div class="card"><div class="ctitle">Before the trade, and after</div>'
         f'<div style="padding:10px 28px 16px"><table class="m">{head}{body}</table></div>'
         f'<div class="vd"><b>{CLR[wn["team"]][2]}</b> came out ahead, {wn["util"]:+.2f} against '
         f'{ls["util"]:+.2f}.</div></div>')
    return f'<div class="row">{"".join(L)}{R}</div>' + _outcome(t)


def _outcome(t):
    """What the traded players were actually worth in the season that followed.

       Built from the same card, title and table classes as the two cards above it,
       so it inherits the site's styling rather than carrying its own -- a separate
       stylesheet was how the first version ended up invisible.  The three colours
       are set inline for the same reason.

       Graded on the GAP between projection and return, not on the sign of it.
       Samson at 2.97 against a 3.99 projection is a shortfall, but it is a good
       season by any reading, and colouring it the same red as a genuine collapse
       would say something false.  So a miss inside about a win reads amber, and red
       is kept for a player who was not remotely what was expected.

       A man who never took the field is marked as such rather than scored zero, and
       one who played too little to read is marked separately again: not playing and
       playing briefly are different things, and neither is a bad season."""
    o = t.get('outcome')
    if not o:
        return ''
    GRN, AMB, RED, GRY = '#1F6F3F', '#9A7B1B', '#A63A2B', '#8A9690'
    rows = []
    for p in o['players']:
        a, st = p.get('actual'), p.get('status')
        pr = p['projected']
        if a is None:
            act, dif, vd, col = '&mdash;', '&mdash;', (st or 'No record'), GRY
        else:
            d = a - pr
            act, dif = f"{a:+.2f}", f"{d:+.2f}"
            # Two different things were being collapsed into one label.  Markande was
            # projected at -0.68 and returned -0.28: the model read him correctly, and
            # he was still poor.  Calling that "beat projection" flatters the season;
            # calling it "as expected" hides that the call was right.  So the verdict
            # names the season, and the colour grades the call.
            lvl = 'Strong' if a >= 1.00 else 'Useful' if a >= 0.30 else 'Poor'
            if d >= 0.30:
                vd, col = f'{lvl}: better than projected', GRN
            elif d > -1.25:
                vd, col = f'{lvl}: as projected', AMB
            else:
                vd, col = f'{lvl}: well short', RED
        rows.append(f'<tr><td>{p["player"]}<span style="color:#8A9690;font-size:11px;'
                    f'margin-left:6px">to {p["to"]}</span></td>'
                    f'<td class="was">{pr:+.2f}</td>'
                    f'<td style="text-align:right;font-weight:700;color:{col}">{act}</td>'
                    f'<td style="text-align:right;color:{col}">{dif}</td>'
                    f'<td style="text-align:right;color:{col};font-weight:600">{vd}</td></tr>')
    head = ('<tr><th></th><th class="sb">Projected</th>'
            f'<th class="sb">Actual {o["season"]}</th><th class="sb">Difference</th>'
            '<th class="sb">Verdict</th></tr>')
    return ('<div class="row" style="grid-template-columns:1fr;margin-top:-14px">'
            '<div class="card" style="min-height:0">'
            f'<div class="ctitle">What actually happened in IPL {o["season"]} \u2014 with hindsight</div>'
            f'<div style="padding:2px 28px 18px">'f'<div style="font-size:12px;color:#8A9690;padding-bottom:8px">The two cards above use only what was known before the trade. This card is the season as it actually finished.</div>'f'<table class="m">{head}{"".join(rows)}</table></div>'
            '</div></div>')

FOOT = ('<p class="foot"><b>Projected WAR</b> is wins above replacement: 0 is a freely available player, a '
        'regular sits near 2, the best season in the data reads 6. <b>Market value</b> is what the auction '
        'would pay, fitted on 2023&ndash;26 prices. <b>XII value</b> is the strength of the best legal twelve '
        'a squad can field. Odds come from simulated seasons. <b>Net value</b> combines all three. '
        'Hover a player name for his card.</p>')

def featured(data):
    H = [f'<style>{CSS}</style><div class="wrap"><h2 class="sec">Featured Trades</h2>'
         '<p class="lede">Every deal below is evaluated against the world in which it never happened. The valuation cards use only information available to the clubs at the time of the trade; where the season has since been played, a third card reports what actually followed.</p>']
    for yr in sorted({t['year'] for t in data['trades']}, reverse=True):
        H.append(f'<div class="yr"><span>{yr} WINDOW</span><div class="ln"></div></div>')
        H += [trade_pair(t) for t in data['trades'] if t['year'] == yr]
    return ''.join(H) + FOOT + '</div>'


def footer_text():
    """The site footer, shared by Featured trades, Trade simulator and Methodology.

       app.py imports this but it was missing from render.py, so the app would not
       start from a clean checkout. Defined here so the three tabs stay identical.
    """
    q = 'Questions?'
    body = ("If you are a professional cricket team, a sports organisation, an analyst, "
            "or an individual interested in using IPL Trade Values, please get in touch. "
            "I&rsquo;d be happy to talk about the framework, its outputs, or how it can "
            "be applied to your specific questions.")
    copy = '&copy; 2026 Omkar Walunj. All Rights Reserved.'
    return q, body, copy


def featured_height(data):
    """Pixel height the Featured Trades iframe needs for this many trades.

       Derived from the content rather than hardcoded, so adding a window or a trade
       does not leave dead space below the last card or clip it. app.py and
       article.py both import this, so the number cannot drift between them.
    """
    tr = data['trades']
    n_tr = len(tr)
    n_out = sum(1 for t in tr if t.get('outcome'))
    n_yr = len({t['year'] for t in tr})
    return 150 + 56 * n_yr + 452 * n_tr + 150 * n_out + 120
