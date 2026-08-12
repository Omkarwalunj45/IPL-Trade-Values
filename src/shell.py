"""House style: cricket hero, evenly spaced nav, loading screen."""
import os, time, base64, streamlit as st
HERE = os.path.dirname(os.path.abspath(__file__))

def _hero_b64():
    p = os.path.join(os.path.dirname(HERE), 'Datasets', 'hero.b64')
    return open(p).read() if os.path.exists(p) else ''

CSS = """
<style>
/* ================= FORCE LIGHT TEXT COLOURS =================
   Streamlit Cloud may run the dark theme if .streamlit/config.toml is missing,
   which paints every label white on our cream background. These rules pin the
   colours regardless of theme. */
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],
.main,.block-container,.element-container,[data-testid="stVerticalBlock"]{
  color:#16281C!important;-webkit-text-fill-color:#16281C!important}
.stApp p,.stApp span,.stApp li,.stApp label,.stApp div,.stApp td,.stApp h1,.stApp h2,
.stApp h3,.stApp h4,.stApp h5,.stApp h6,.stMarkdown,.stMarkdown *,
[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] *,
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{
  color:#16281C!important;-webkit-text-fill-color:#16281C!important}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{
  color:#6B7A6F!important;-webkit-text-fill-color:#6B7A6F!important}
/* inputs and their dropdown menus */
input,textarea,select,div[data-baseweb="select"] *,div[data-baseweb="input"] *,
div[data-baseweb="popover"] *,li[role="option"],li[role="option"] *{
  color:#16281C!important;-webkit-text-fill-color:#16281C!important}
div[data-baseweb="popover"] ul,div[data-baseweb="popover"] div{background:#fff!important}
/* expander */
[data-testid="stExpander"] *{color:#16281C!important;-webkit-text-fill-color:#16281C!important}
[data-testid="stExpander"] summary p{font-weight:600!important}
/* dataframe */
[data-testid="stDataFrame"] *{color:#16281C!important;-webkit-text-fill-color:#16281C!important}
/* our own tables and cards keep their explicit colours */
.rk thead th,.rk thead th *{color:#fff!important;-webkit-text-fill-color:#fff!important}
.hero,.hero *{color:#fff!important;-webkit-text-fill-color:#fff!important}
.hero .tl{color:#E8F3EA!important;-webkit-text-fill-color:#E8F3EA!important}
.hero .au a{color:rgba(255,255,255,.72)!important;-webkit-text-fill-color:rgba(255,255,255,.72)!important}
button[kind="primary"],button[kind="primary"] *{color:#fff!important;-webkit-text-fill-color:#fff!important}
.essay .up,.rk .up{color:#1b5e3f!important;-webkit-text-fill-color:#1b5e3f!important}
.essay .dn,.rk .dn{color:#9b2226!important;-webkit-text-fill-color:#9b2226!important}
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800;900&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600;700&display=swap');

/* ---- page: soft cream with a fine pinstripe, like a broadsheet ---- */
.stApp,[data-testid="stAppViewContainer"]{
  background-color:#F7F5EE!important;
  background-image:repeating-linear-gradient(90deg,rgba(0,0,0,.022) 0 1px,transparent 1px 7px)!important;
  font-family:'Inter',sans-serif!important}
#MainMenu,footer,header,.stDeployButton{visibility:hidden!important;display:none!important}
.block-container{padding:0 2rem 4rem!important;max-width:1460px!important}
section[data-testid="stSidebar"]{display:none}

/* ---- hero ---- */
.hero{position:relative;height:210px;border-radius:0 0 4px 4px;overflow:hidden;margin:0 0 0;
  border:1px solid rgba(255,255,255,.25);box-shadow:0 3px 18px rgba(0,0,0,.18)}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.hero .sh{position:absolute;inset:0;background:linear-gradient(180deg,rgba(6,20,14,.62) 0%,
  rgba(6,20,14,.40) 45%,rgba(6,20,14,.72) 100%)}
.hero .ct{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center}
.hero .bn{font-family:'Archivo',sans-serif;font-weight:900;font-size:52px;letter-spacing:-1.6px;
  color:#fff;text-transform:uppercase;line-height:1;text-shadow:0 2px 22px rgba(0,0,0,.55)}
.hero .tl{margin-top:11px;font-size:11.5px;letter-spacing:.24em;text-transform:uppercase;
  color:rgba(255,255,255,.86);font-weight:600}
.byl{margin-top:9px;font-family:'Source Serif 4',Georgia,serif;font-size:14px;font-style:italic;
  color:rgba(255,255,255,.82)}
.hero .byl{margin-top:7px;font-size:13px;color:rgba(255,255,255,.9);font-weight:500;font-family:'Source Serif 4',Georgia,serif;font-style:italic}
.hero .au{position:absolute;top:15px;right:22px;text-align:right}
.hero .au b{display:block;font-size:12.5px;color:#fff;font-weight:600}
.hero .au a{font-size:9.6px;letter-spacing:.11em;text-transform:uppercase;color:rgba(255,255,255,.62);
  text-decoration:none;margin-left:9px}
.hero .au a:hover{color:#fff}

/* ---- nav: buttons spread evenly, active one bold with a rule ---- */
.navwrap{border-bottom:2px solid #2F4A38;background:#FFFDF7;margin:0 0 26px}
button[kind="secondary"]{background:transparent!important;border:none!important;box-shadow:none!important;
  border-radius:0!important;width:100%!important;padding:14px 4px!important;
  border-bottom:4px solid transparent!important;transition:none!important}
button[kind="secondary"] *{font-family:'Archivo',sans-serif!important;font-weight:700!important;
  font-size:14px!important;letter-spacing:.05em!important;text-transform:uppercase!important;
  color:#5B6B5F!important;-webkit-text-fill-color:#5B6B5F!important;opacity:1!important}
button[kind="secondary"]:hover{background:#F2EFE4!important;transform:none!important}
button[kind="secondary"]:hover *{color:#16281C!important;-webkit-text-fill-color:#16281C!important}
button[kind="primary"]{background:linear-gradient(135deg,#2F4A38,#1D3324)!important;color:#fff!important;
  border:none!important;border-radius:8px!important;font-weight:700!important;font-size:14.5px!important;
  padding:.65rem 1.6rem!important;box-shadow:0 4px 14px rgba(47,74,56,.3)!important}
button[kind="primary"] *{color:#fff!important;-webkit-text-fill-color:#fff!important}
.navon{border-bottom:4px solid #C9A227;margin-top:-4px}
.navoff{border-bottom:4px solid transparent;margin-top:-4px}

/* ---- inputs ---- */
.stSelectbox>div>div,.stNumberInput>div>div,div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{
  background:#fff!important;border:1px solid #D9D3C2!important;border-radius:8px!important;
  color:#16281C!important}
div[data-baseweb="select"] *,div[data-baseweb="input"] input{color:#16281C!important;
  -webkit-text-fill-color:#16281C!important}
div[data-baseweb="popover"] li{background:#fff!important;color:#16281C!important}
div[data-baseweb="popover"] li:hover{background:#F5F1E2!important}
.stSelectbox label,.stNumberInput label{color:#6B7A6F!important;font-size:10.5px!important;
  font-weight:700!important;text-transform:uppercase;letter-spacing:.07em}
.stNumberInput button{background:#F7F5EE!important;color:#16281C!important;border-color:#D9D3C2!important}
[data-testid="stDataFrame"]{background:#fff!important;border:1.5px solid #D9D3C2!important;
  border-radius:10px!important;overflow:hidden!important;
  box-shadow:0 1px 3px rgba(22,40,28,.05),0 8px 22px rgba(22,40,28,.04)!important}
[data-testid="stDataFrame"] thead th,[data-testid="stDataFrame"] [role="columnheader"]{
  background:#16281C!important;color:#fff!important;font-family:'Archivo',sans-serif!important;
  font-weight:700!important;font-size:11px!important;letter-spacing:.06em!important;
  text-transform:uppercase!important;border:none!important}
[data-testid="stDataFrame"] thead th *,[data-testid="stDataFrame"] [role="columnheader"] *{
  color:#fff!important;-webkit-text-fill-color:#fff!important;font-weight:700!important}
[data-testid="stDataFrame"] [role="gridcell"]{font-size:13.5px!important;border-color:#EFEBE0!important}
[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"]{background:#FBFAF5!important}
[data-testid="stExpander"]{background:#fff!important;border:1.5px solid #E0DACA!important;
  border-radius:10px!important}

.rk{width:100%;border-collapse:collapse;font-family:'Inter',sans-serif;font-size:13px;background:#fff}
.rk thead th{background:#1D3324;color:#fff!important;font-size:10px;font-weight:700;letter-spacing:.07em;
  text-transform:uppercase;padding:11px 10px;text-align:right;white-space:nowrap;position:sticky;top:0}
.rk thead th:first-child,.rk thead th:nth-child(2){text-align:left}
.rk td{padding:9px 10px;text-align:right;border-bottom:1px solid #EDEAE0;font-variant-numeric:tabular-nums;color:#16281C!important;-webkit-text-fill-color:#16281C!important}
.rk td:first-child{text-align:left;color:#8A9490!important;-webkit-text-fill-color:#8A9490!important;font-size:11.5px;width:38px}
.rk td:nth-child(2){text-align:left;font-weight:700;color:#16281C!important;-webkit-text-fill-color:#16281C!important;white-space:nowrap}
.rk tbody tr:nth-child(even){background:#FBFAF5}
.rk tbody tr:hover{background:#F3F7F0}
.rkwrap{border:1.5px solid #E0DACA;border-radius:12px;overflow:auto;max-height:640px;
  box-shadow:0 1px 3px rgba(22,40,28,.05)}
.sechead{font-family:'Archivo',sans-serif;font-weight:900;font-size:38px;letter-spacing:-1.1px;
  text-transform:uppercase;color:#16281C;margin:6px 0 3px}
.sechead+p{font-family:'Source Serif 4',Georgia,serif;font-size:13.5px;color:#6B7A6F;margin:0 0 20px}

/* ---- long-form typography for the methodology tab ---- */
.essay h2{font-family:'Archivo',sans-serif!important;font-weight:800!important;font-size:27px!important;
  text-transform:uppercase;letter-spacing:-.5px;color:#16281C!important;margin:34px 0 12px!important;
  padding-top:16px;border-top:1px solid #E0DACA}
.essay h3{font-family:'Archivo',sans-serif!important;font-weight:700!important;font-size:18px!important;
  color:#2F4A38!important;margin:26px 0 8px!important}
.essay p,.essay li{font-family:'Source Serif 4',Georgia,serif!important;font-size:17.5px!important;
  line-height:1.74!important;color:#1F2A22!important}
.essay strong{color:#16281C!important;font-weight:700}
.figbox{background:#fff;border:1.5px solid #D9D3C2;border-radius:10px;padding:16px;
  margin:8px 0 6px;box-shadow:0 1px 3px rgba(22,40,28,.05)}
.essay img,.figbox img{display:block;width:100%;border-radius:6px}
.figbox{background:#fff;border:1.5px solid #E0DACA;border-radius:12px;padding:18px;margin:20px 0 8px;
  box-shadow:0 1px 3px rgba(22,40,28,.05)}
.figcap{font-family:'Source Serif 4',Georgia,serif;font-size:13px;color:#6B7A6F;line-height:1.6;
  margin:-2px 0 26px;padding-left:2px}
.essay blockquote{border-left:3px solid #C9A227;padding:2px 0 2px 16px;margin:16px 0;
  font-family:'Source Serif 4',Georgia,serif;color:#3B4A40}
</style>
"""

def hero():
    st.markdown(CSS, unsafe_allow_html=True)
    b = _hero_b64()
    img = f'<img src="data:image/jpeg;base64,{b}">' if b else ''
    st.markdown(f"""<div class="hero">{img}<div class="sh"></div>
      <div class="au"><b>Omkar Walunj</b>
        <a href="https://substack.com/@theunseengame" target="_blank">Substack</a>
        <a href="https://twitter.com/the_cricketest" target="_blank">Twitter</a>
        <a href="https://www.linkedin.com/in/omkar-walunj-8256a4280/" target="_blank">LinkedIn</a></div>
      <div class="ct"><div class="bn">IPL Trade Values</div>
        <div class="tl">Objective valuation for IPL trades</div>
        <div class="byl">by Omkar Walunj</div></div></div>""", unsafe_allow_html=True)

_SPIN = """
<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:%dvh;font-family:'Inter',sans-serif">
 <div style="font-family:'Archivo',sans-serif;font-size:%dpx;font-weight:900;color:#16281C;
   text-transform:uppercase;letter-spacing:-1px;animation:pl 1.6s infinite">IPL Trade Values</div>
 <div style="font-size:12.5px;color:#6B7A6F;margin-top:10px;letter-spacing:.05em">%s</div>
 <div style="width:250px;height:4px;background:#E0DACA;border-radius:2px;overflow:hidden;margin-top:20px">
  <div style="width:45%%;height:100%%;background:linear-gradient(90deg,#2F4A38,#C9A227);
    animation:ld 1.2s infinite"></div></div></div>
<style>@keyframes pl{0%%,100%%{opacity:1}50%%{opacity:.45}}
@keyframes ld{0%%{transform:translateX(-100%%)}100%%{transform:translateX(320%%)}}</style>
"""

def splash(msg="Initialising the trade engine", vh=58, size=34):
    box = st.empty(); box.markdown(_SPIN % (vh, size, msg), unsafe_allow_html=True); return box

def boot_splash():
    if st.session_state.get("_booted"): return
    b = splash(); time.sleep(1.4); b.empty(); st.session_state["_booted"] = True
