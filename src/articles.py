# -*- coding: utf-8 -*-
"""Articles tab.

Separate from src/article.py, which is the Methodology essay and is untouched.

Articles are JSON in content/articles/, images in content/articles/images/,
both written by tools/substack_import.py. Nothing here links out to Substack:
clicking a card swaps st.session_state.article and the piece opens in place.

Order: likes descending. Set "order" to an integer in any json to pin it.
"""
import os, json, glob, base64, mimetypes
import streamlit as st
import streamlit.components.v1 as C

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART  = os.path.join(ROOT, "content", "articles")
IMGD = os.path.join(ART, "images")
DATA = os.path.join(ROOT, "Datasets")

CSS = """<style>
.artcard{background:#FFFDF7;border:1.5px solid #E0DACA;border-radius:14px;
  overflow:hidden;margin:26px 0 0}
.artcard .shot{display:block;width:100%;height:auto;
  border-bottom:1.5px solid #E0DACA;background:#EFEADF}
.artcard .noshot{height:120px;background:linear-gradient(115deg,#1D3324,#3A5B45);
  border-bottom:1.5px solid #E0DACA}
.artcard .pad{padding:20px 24px 16px}
.artcard .kick{font-family:'Archivo',sans-serif;font-weight:800;font-size:10.5px;
  letter-spacing:.15em;text-transform:uppercase;color:#8A9490;margin:0 0 8px}
.artcard h4{font-family:'Archivo',sans-serif;font-weight:900;font-size:27px;
  line-height:1.15;letter-spacing:-.8px;color:#16281C;margin:0 0 9px}
.artcard .desc{font-family:'Source Serif 4',Georgia,serif;font-size:16.5px;
  line-height:1.6;color:#5C6B60;margin:0}
.artcard .meta{font-family:'Archivo',sans-serif;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;color:#9A9488;margin:12px 0 0}
.artsub{font-family:'Source Serif 4',Georgia,serif;font-size:20px;line-height:1.5;
  color:#5C6B60;margin:4px 0 16px;max-width:760px}
.arthero{margin:10px 0 26px;border:1.5px solid #E0DACA;border-radius:12px;overflow:hidden}
.arthero img{display:block;width:100%}
.artrule{border:0;border-top:1px solid #E0DACA;margin:26px 0}
</style>"""


# ---------------------------------------------------------------- loading
@st.cache_data(show_spinner=False)
def load_all():
    out = []
    for p in sorted(glob.glob(os.path.join(ART, "*.json"))):
        base = os.path.basename(p)
        if base == "order.json" or base.startswith("_"):
            continue                      # config, not an article
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or "blocks" not in d:
            continue
        d.setdefault("slug", os.path.splitext(os.path.basename(p))[0])
        d.setdefault("by", "Omkar Walunj")
        out.append(d)
    # Sequence: content/articles/order.json first (a hand-editable list of
    # slugs), then any per-article "order" pin, then likes, then date.
    seq = {}
    try:
        raw = json.load(open(os.path.join(ART, "order.json"), encoding="utf-8"))
        seq = {s: i for i, s in enumerate(raw.get("order", []))}
    except Exception:
        pass
    out.sort(key=lambda d: (-int(d.get("likes") or 0), d.get("date_sort", "")))
    def rank(d):
        try:
            if d.get("order") is not None:
                return int(d["order"])
        except (TypeError, ValueError):
            pass
        return seq.get(d["slug"], 500)
    out.sort(key=rank)
    return out


def get(slug):
    return next((a for a in load_all() if a["slug"] == slug), None)


def _path(name):
    for base in (IMGD, ART, DATA):
        p = os.path.join(base, name)
        if os.path.isfile(p):
            return p
    return None


@st.cache_data(show_spinner=False)
def _src(name):
    """Inline as base64 -- Streamlit has no static file server here."""
    p = _path(name) if name else None
    if not p:
        return None
    mt = mimetypes.guess_type(p)[0] or "image/png"
    return "data:%s;base64,%s" % (mt, base64.b64encode(open(p, "rb").read()).decode())


def _scroll_top():
    """Streamlit keeps the scroll offset across reruns, so opening an article
    from halfway down the index lands you halfway down the article. This puts
    the view back at the top. Several selectors because the name of the scroll
    container has changed between Streamlit versions."""
    C.html("""<script>
      const d = window.parent.document;
      const sels = ['section.main', '[data-testid="stMain"]',
                    '[data-testid="stAppViewContainer"]', '.main', 'html', 'body'];
      const go = () => {
        for (const s of sels) {
          const e = d.querySelector(s);
          if (e && e.scrollHeight > e.clientHeight) { e.scrollTop = 0; }
        }
        window.parent.scrollTo(0, 0);
      };
      go(); setTimeout(go, 60); setTimeout(go, 220);
    </script>""", height=0)


# ---------------------------------------------------------------- index
def index():
    if st.session_state.pop("_totop", False):
        _scroll_top()
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="sechead">Articles</div>'
                '<p>Writing on cricket valuation, trade economics and T20 strategy.</p>',
                unsafe_allow_html=True)

    arts = load_all()
    if not arts:
        st.info("No articles yet. Run `python tools/substack_import.py` from the "
                "repo root to pull them in.")
        return

    for a in arts:
        src = _src(a.get("cover") or a.get("hero"))
        shot = ('<img class="shot" src="%s">' % src) if src else '<div class="noshot"></div>'
        kick = ('<div class="kick">%s</div>' % a["category"]) if a.get("category") else ""
        st.markdown(
            '<div class="artcard">%s<div class="pad">%s<h4>%s</h4>'
            '<p class="desc">%s</p><div class="meta">%s</div></div></div>'
            % (shot, kick, a.get("title", ""),
               a.get("description") or a.get("subtitle") or "",
               " · ".join(x for x in (a.get("by"), a.get("date")) if x)),
            unsafe_allow_html=True)
        if st.button("Read article  →", key="open_%s" % a["slug"], type="tertiary"):
            st.session_state.article = a["slug"]
            st.session_state._totop = True
            st.rerun()


# ---------------------------------------------------------------- reader
def _blocks(bl, key):
    st.markdown('<div class="essay">', unsafe_allow_html=True)
    for i, b in enumerate(bl):
        k, v = b[0], (b[1] if len(b) > 1 else "")
        if k == "t":
            st.markdown(v)
        elif k == "H":
            st.markdown("## %s" % v)
        elif k == "h":
            st.markdown("### %s" % v)
        elif k == "q":
            st.markdown("> %s" % v)
        elif k == "r":
            st.markdown('<hr class="artrule">', unsafe_allow_html=True)
        elif k == "f":
            try:
                st.latex(v)
            except Exception:
                st.markdown("`%s`" % v)
        elif k == "x":
            tgt = get(v)
            if tgt:
                if st.button("→  %s" % tgt.get("title", v),
                             key="%s_x%d" % (key, i), type="tertiary"):
                    st.session_state.article = v
                    st.session_state._totop = True
                    st.rerun()
        elif k == "c":
            if st.button(v or "Contact me", key="%s_c%d" % (key, i), type="tertiary"):
                st.session_state.tab = "Contact"
                st.session_state.article = None
                st.rerun()
        elif k == "i":
            src = _src(v)
            if src:
                st.markdown('<div class="figbox"><img src="%s"></div>' % src,
                            unsafe_allow_html=True)
                cap = b[2] if len(b) > 2 else ""
                if cap:
                    st.markdown('<div class="figcap">%s</div>' % cap, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def reader(slug):
    a = get(slug)
    if not a:
        st.session_state.article = None
        st.rerun()

    if st.session_state.pop("_totop", False):
        _scroll_top()
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("""<style>
    div[data-testid="stButton"] button[kind="tertiary"] p{
        font-family:Archivo,sans-serif !important;font-size:15px !important;
        font-weight:700 !important;color:#1D3324 !important}
    div[data-testid="stButton"] button[kind="tertiary"]{padding-left:0 !important}
    </style>""", unsafe_allow_html=True)

    if st.button("←  All articles", key="back_%s" % slug, type="tertiary"):
        st.session_state.article = None
        st.session_state._totop = True
        st.rerun()

    st.markdown(
        '<div style="font-family:\'Archivo\',sans-serif;font-weight:900;font-size:42px;'
        'line-height:1.06;letter-spacing:-1.4px;color:#16281C;margin:14px 0 8px;'
        'text-transform:uppercase">%s</div>' % a.get("title", ""), unsafe_allow_html=True)
    if a.get("subtitle"):
        st.markdown('<div class="artsub">%s</div>' % a["subtitle"], unsafe_allow_html=True)
    st.markdown(
        '<div style="border-top:1px solid #E0DACA;border-bottom:1px solid #E0DACA;'
        'padding:12px 0"><div style="font-family:\'Archivo\',sans-serif;font-weight:800;'
        'font-size:14px;color:#16281C;letter-spacing:.04em;text-transform:uppercase">'
        '%s</div></div>' % " · ".join(x for x in (a.get("by"), a.get("date")) if x),
        unsafe_allow_html=True)

    src = _src(a.get("cover") or a.get("hero"))
    if src:
        st.markdown('<div class="arthero"><img src="%s"></div>' % src, unsafe_allow_html=True)

    _blocks(a.get("blocks", []), key="rd_%s" % slug)

    if not any(b[0] == "c" for b in a.get("blocks", [])):
        st.markdown('<div style="font-family:Archivo,sans-serif;font-size:15px;'
                    'font-weight:700;color:#1D3324;margin:30px 0 5px">Questions?</div>',
                    unsafe_allow_html=True)
        st.markdown('<div style="font-family:\'Source Serif 4\',Georgia,serif;'
                    'font-size:16px;color:#5C6B60;line-height:1.65;max-width:820px">'
                    'If you are a professional cricket team, a sports organisation, an '
                    'analyst, or an individual interested in this work, please get in '
                    'touch.</div>', unsafe_allow_html=True)
        if st.button("Contact me", key="rd_contact_%s" % slug, type="tertiary"):
            st.session_state.tab = "Contact"
            st.session_state.article = None
            st.rerun()

    st.markdown('<hr class="artrule">', unsafe_allow_html=True)
    if st.button("←  All articles", key="back_bottom_%s" % slug, type="tertiary"):
        st.session_state.article = None
        st.session_state._totop = True
        st.rerun()

    st.markdown('<div style="font-family:Arial,sans-serif;font-size:12px;color:#8a8474;'
                'margin-top:14px">© 2026 Omkar Walunj. All Rights Reserved.</div>',
                unsafe_allow_html=True)
