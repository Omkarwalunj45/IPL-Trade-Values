# -*- coding: utf-8 -*-
"""Import Substack posts into the site as local articles. Standard library only.

    python tools/substack_import.py

Pulls from two places and merges them:
  /feed                      full body HTML, title, subtitle, date, cover image
  /api/v1/archive?limit=50   reaction (like) counts, used as the display order

Writes content/articles/<slug>.json + downloads every image (cover and in-body)
into content/articles/images/. After this runs the site never touches Substack.

Re-running is safe: existing json is left alone unless --force, so any hand
edits you make to category/description survive the next import.
"""
import os, re, sys, json, html, argparse, urllib.request, urllib.parse, mimetypes
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART  = os.path.join(ROOT, "content", "articles")
IMGD = os.path.join(ART, "images")
UA   = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"}

SITE = "https://theunseengame.substack.com"

# Posts to leave off the website. Matched against the title AND the subtitle,
# normalised, so a line that is actually a subtitle still excludes its post.
EXCLUDE = [
    "When the Magic Becomes the Trap",
    "Why Control Becomes a Cage in T20s",
    "IPL Starts Tomorrow. The Model Just Updated to predict the IPL 2026 points table.",
    "If Finn Flicks, India Wins",
    "THE HIDDEN POWERPLAY: Why Overs 31-40 Are Now the Most Valuable Phase in ODI Cricket",
]

# Substack injects subscribe / share / comment buttons into the feed body.
# They are dropped rather than imported as text.
DROP_CLASS = re.compile(r"subscri|paywall|button-wrapper|poll|digest|footer", re.I)


def norm(s):
    """Loose title key: lowercase, alphanumerics only. Beats dash/quote drift."""
    return re.sub(r"[^a-z0-9]", "", html.unescape(s or "").lower())


EXCLUDE_KEYS = {norm(x) for x in EXCLUDE}


# ---------------------------------------------------------------- html -> blocks
class Body(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buf, self.mode, self.skip = [], [], None, 0
        self._href, self._alen = "", 0
        self.em = []          # open <strong>/<em>: (tag, marker, index in buf)

    def _flush(self):
        t = re.sub(r"[ \t]+", " ", "".join(self.buf)).strip()
        t = t.strip()
        if t and self.mode:
            self.blocks.append([self.mode, t])
        self.buf, self.mode, self.em = [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if self.skip:
            self.skip += 1
            return
        if tag in ("script", "style", "svg", "path", "polyline", "line", "g"):
            self.skip = 1
            return
        if cls and DROP_CLASS.search(cls):
            self.skip = 1
            return

        # A rendered LaTeX block carries its source in data-attrs.
        if tag == "div" and "latex" in cls.lower():
            try:
                expr = json.loads(html.unescape(a.get("data-attrs", "{}")))\
                        .get("persistentExpression", "").strip()
                if expr:
                    self._flush()
                    self.blocks.append(["f", expr])
            except Exception:
                pass
            self.skip = 1
            return

        if tag == "img":
            src = a.get("src") or ""
            if not src and a.get("data-attrs"):
                try:
                    src = json.loads(html.unescape(a["data-attrs"])).get("src", "")
                except Exception:
                    src = ""
            if src.startswith("http"):
                self._flush()
                self.blocks.append(["i", src, ""])
        elif tag == "hr":
            self._flush()
            self.blocks.append(["r", ""])
        elif tag in ("h1", "h2"):
            self._flush(); self.mode = "H"
        elif tag in ("h3", "h4", "h5", "h6"):
            self._flush(); self.mode = "h"
        elif tag == "blockquote":
            self._flush(); self.mode = "q"
        elif tag == "figcaption":
            self._flush(); self.mode = "cap"
        elif tag == "li":
            self._flush(); self.mode = "t"; self.buf.append("- ")
        elif tag in ("p", "div"):
            if self.mode is None:
                self.mode = "t"
        elif tag in ("strong", "b", "em", "i"):
            mark = "**" if tag in ("strong", "b") else "*"
            self.em.append((tag, mark, len(self.buf)))
            self.buf.append(mark)
        elif tag == "br":
            self.buf.append("  \n")
        elif tag == "a":
            self._href, self._alen = a.get("href", ""), len(self.buf)

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
            return
        if tag == "a":
            txt = "".join(self.buf[self._alen:]).strip()
            bad = ("/subscribe" in self._href or "action=share" in self._href
                   or "substack.com/@" in self._href)
            if self._href.startswith("http") and txt and not bad:
                del self.buf[self._alen:]
                self.buf.append("[%s](%s)" % (txt, self._href))
            self._href = ""
        elif tag in ("strong", "b", "em", "i"):
            # Substack nests <strong><span> </span></strong> constantly. An
            # emphasis span that wrapped no text must not leave stray markers.
            for j in range(len(self.em) - 1, -1, -1):
                if self.em[j][0] == tag:
                    _, mark, at = self.em.pop(j)
                    inner = "".join(self.buf[at + 1:])
                    del self.buf[at:]
                    if inner.strip():
                        # Markdown ignores "**text **" -- a marker with a space
                        # against it renders as literal asterisks. Push any
                        # surrounding whitespace outside the markers.
                        lead  = inner[:len(inner) - len(inner.lstrip())]
                        trail = inner[len(inner.rstrip()):]
                        self.buf.append(lead + mark + inner.strip() + mark + trail)
                    elif inner:
                        self.buf.append(inner)
                    break
        elif tag == "figcaption":
            cap = "".join(self.buf).strip()
            self.buf, self.mode = [], None
            for b in reversed(self.blocks):          # attach to the image above
                if b[0] == "i":
                    b[2] = cap
                    break
        elif tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "div"):
            self._flush()

    def handle_data(self, d):
        if not self.skip:
            self.buf.append(d)

    def close(self):
        super().close(); self._flush()


JUNK = re.compile(r"^(subscribe now|share|leave a comment|thanks for reading)\.?$", re.I)

# Sign-off paragraphs that belong on Substack, not on the site. A paragraph
# matching one of these is dropped UNLESS it links to another of his articles,
# in which case it is kept and the link becomes an in-site button.
CTA = re.compile(
    r"(subscribe|do give me a follow|share (the |this )?(article|it)|"
    r"if you enjoyed|if you made it this far|thanks for reading|"
    r"let me know what you think|in the comments|"
    r"i write about cricket strategy|found this interesting)", re.I)

POSTLINK = re.compile(r"\[([^\]]*)\]\(https?://[^)]*?/p/([a-z0-9\-]+)[^)]*\)", re.I)


def link_and_cta(bl, known):
    """Turn links to his own posts into internal cross-references, and strip
    Substack call-to-action paragraphs that have nothing else in them."""
    out = []
    for b in bl:
        if b[0] != "t":
            out.append(b)
            continue
        hits = [m for m in POSTLINK.finditer(b[1]) if m.group(2) in known]
        refs = [m.group(2) for m in hits]
        labels = {(m.group(1) or "").strip().lower() for m in hits}
        txt = POSTLINK.sub(lambda m: m.group(1) or "", b[1]).strip()
        txt = re.sub(r"\s{2,}", " ", txt).rstrip(" :\u2014-")
        # A paragraph that was nothing but the link becomes just the button.
        if txt.strip("*").lower() in labels:
            txt = ""
        if refs:
            if txt:
                out.append(["t", txt])
            for slug in dict.fromkeys(refs):
                out.append(["x", slug])
        elif CTA.search(b[1]):
            continue                      # pure sign-off, drop it
        else:
            out.append(b)
    while out and out[-1][0] == "r":
        out.pop()
    return out


def parse_html(raw):
    p = Body(); p.feed(raw); p.close()
    out = []
    for b in p.blocks:
        if b[0] == "cap":
            continue
        if b[0] == "r":
            if out and out[-1][0] != "r":
                out.append(b)
            continue
        if b[0] in ("H", "h"):
            # Substack bolds nearly every heading; the heading style already is.
            b[1] = b[1].strip("* ")
        if b[0] not in ("i", "f") and (len(b[1]) < 2 or JUNK.match(b[1])):
            continue
        out.append(b)
    while out and out[-1][0] == "r":
        out.pop()
    return out


# ---------------------------------------------------------------- net helpers
def get(url, timeout=45):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def fetch_image(url, slug, n):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data, ct = r.read(), r.headers.get("Content-Type", "")
    except Exception as e:
        print("    ! image failed (%s) %s" % (e, url[:60]))
        return None
    ext = mimetypes.guess_extension((ct or "").split(";")[0].strip()) or ".jpg"
    ext = {".jpe": ".jpg", ".jpeg": ".jpg"}.get(ext, ext)
    os.makedirs(IMGD, exist_ok=True)
    name = "%s-%02d%s" % (slug, n, ext)
    open(os.path.join(IMGD, name), "wb").write(data)
    return name


def archive(site, cap=200):
    """Every post ever published, newest first, via the paged archive endpoint.

    The RSS feed only carries the ~20 most recent posts, so anything older
    (the ICR piece, for one) is invisible to it. This is also the only place
    reaction counts exist."""
    out, seen, off = [], set(), 0
    while off < cap:
        url = "%s/api/v1/archive?sort=new&limit=50&offset=%d" % (site.rstrip("/"), off)
        try:
            page = json.loads(get(url))
        except Exception as e:
            print("! archive endpoint failed at offset %d (%s)" % (off, e))
            break
        if not page:
            break
        # Substack caps a page below the requested limit, so a short page does
        # NOT mean the end of the archive -- keep paging until one comes back
        # empty or repeats. Advance by what was actually returned.
        fresh = [p for p in page if p.get("slug") and p["slug"] not in seen]
        if not fresh:
            break
        out += fresh
        seen |= {p["slug"] for p in fresh}
        off += len(page)
    print("archive: %d posts" % len(out))
    return out


def feed_bodies(site):
    """slug -> (body_html, enclosure_url). The feed markup is the cleanest
    source for a post body, so it wins wherever it is available."""
    try:
        root = ET.fromstring(get(site.rstrip("/") + "/feed"))
    except Exception as e:
        print("! feed unavailable (%s)" % e)
        return {}
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    out = {}
    for it in root.findall(".//item"):
        link = (it.findtext("link") or "").strip()
        slug = urllib.parse.urlparse(link).path.rsplit("/", 1)[-1]
        body = it.findtext("content:encoded", default="", namespaces=ns) or ""
        enc = it.find("enclosure")
        out[slug] = (body, (enc.get("url") if enc is not None else "") or "")
    print("feed: %d posts" % len(out))
    return out


BODY_OPEN  = re.compile(r'<div[^>]*class="[^"]*\bbody\b[^"]*markup[^"]*"[^>]*>')
BODY_STOP  = re.compile(r'class="[^"]*(post-ufi|subscribe-widget|post-footer|'
                        r'comments-page|footer-wrap)', re.I)


def body_from_page(url):
    """Last resort for posts the feed does not carry: pull the article body out
    of the rendered page. Bounded at the first post-footer widget so navigation
    and comment chrome do not get imported as article text."""
    try:
        page = get(url).decode("utf-8", "replace")
    except Exception as e:
        print("    ! page fetch failed (%s)" % e)
        return ""
    m = BODY_OPEN.search(page)
    if not m:
        return ""
    rest = page[m.end():]
    stop = BODY_STOP.search(rest)
    return rest[:stop.start()] if stop else rest[:400000]


def body_for(site, p, feed):
    """Body html for one archive post, best source first."""
    slug = p.get("slug") or ""
    if slug in feed and len(feed[slug][0]) > 500:
        return feed[slug][0], "feed"
    if p.get("body_html"):
        return p["body_html"], "archive"
    try:
        d = json.loads(get("%s/api/v1/posts/%s" % (site.rstrip("/"), slug)))
        if d.get("body_html"):
            return d["body_html"], "post api"
    except Exception:
        pass
    url = p.get("canonical_url") or "%s/p/%s" % (site.rstrip("/"), slug)
    b = body_from_page(url)
    return b, ("page" if b else "none")


ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
MONTHS = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
FULL = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"]


def when(p):
    m = ISO.search(p.get("post_date") or "")
    if not m:
        return "", ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return "%s %d" % (FULL[mo - 1], y), "%04d-%02d-%02d" % (y, mo, d)


ORDERF = os.path.join(ART, "order.json")

# Default ranking when order.json does not exist yet: the framework pieces (the
# work the site is actually about) lead, then everything else newest first.
TIER0 = re.compile(r"integrated contextual|\bicr\b|trade|\bwar\b|framework|"
                   r"model|metric|valuation|rating", re.I)


def write_order(slugs_meta, force=False):
    """slugs_meta: list of (slug, title, subtitle, date_sort). One editable file
    controls the running order of the whole tab."""
    if os.path.exists(ORDERF) and not force:
        print("order.json already exists -- left alone (use --reorder to rebuild)")
        return
    ranked = sorted(slugs_meta,
                    key=lambda m: (0 if TIER0.search(m[1] + " " + m[2]) else 1,
                                   "" if not m[3] else [-ord(c) for c in m[3]]))
    json.dump({"_comment": "Display order, top first. Reorder these slugs freely. "
                           "Any article missing from this list falls to the bottom, "
                           "sorted by likes.",
               "order": [m[0] for m in ranked]},
              open(ORDERF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s -- edit it to set the running order" % ORDERF)


def import_one(site, p, feed, known, force):
    """Import a single archive post dict. Returns slug or None."""
    slug  = p.get("slug") or ""
    title = html.unescape((p.get("title") or "").strip())
    sub   = html.unescape((p.get("subtitle") or "").strip())
    if not slug:
        return None
    if norm(title) in EXCLUDE_KEYS or (sub and norm(sub) in EXCLUDE_KEYS):
        print("  - %s  (excluded)" % title)
        return None

    path = os.path.join(ART, slug + ".json")
    if os.path.exists(path) and not force:
        print("  = %s  (exists, skipped)" % slug)
        return slug

    r = p.get("reactions") or {}
    likes = max(sum(v for v in r.values() if isinstance(v, int)),
                int(p.get("reaction_count") or 0))
    body, srcname = body_for(site, p, feed)
    if not body:
        print("  ! %s  NO BODY FOUND -- skipped" % slug)
        return None
    print("  + %s  (%d likes, body via %s)" % (slug, likes, srcname))

    date, date_sort = when(p)
    n, cover = 0, None
    cov_url = p.get("cover_image") or (feed.get(slug, ("", ""))[1])
    if cov_url and cov_url.startswith("http"):
        n += 1
        cover = fetch_image(cov_url, slug, n)

    bl = []
    for b in parse_html(body):
        if b[0] == "i":
            n += 1
            name = fetch_image(b[1], slug, n)
            if name:
                bl.append(["i", name, b[2]])
        else:
            bl.append(b)
    bl = link_and_cta(bl, known)

    first = next((b[1] for b in bl if b[0] == "t"), "")
    json.dump({
        "title": title, "subtitle": sub,
        "description": sub or re.sub(r"[*_\[\]]", "", first)[:180],
        "category": "", "by": "Omkar Walunj",
        "date": date, "date_sort": date_sort,
        "cover": cover, "likes": likes, "order": None,
        "blocks": bl,
    }, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return slug


def add_url(site, url, force):
    """Import one post by URL, for anything the archive does not list."""
    slug = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    print("adding %s" % slug)
    body = body_from_page(url)
    if not body:
        print("! could not find an article body at that URL")
        return
    title = slug.replace("-", " ").title()
    m = re.search(r"<title>(.*?)</title>", get(url).decode("utf-8", "replace"), re.S)
    if m:
        title = html.unescape(re.sub(r"\s*\|.*$", "", m.group(1))).strip()
    p = {"slug": slug, "title": title, "subtitle": "", "canonical_url": url,
         "reactions": {}, "post_date": ""}
    import_one(site, p, {}, set(), True)
    print("done -- open content/articles/%s.json and set title/date/likes by hand" % slug)


# ---------------------------------------------------------------- main import
def run(site, force, limit, reorder=False):
    os.makedirs(ART, exist_ok=True)
    posts, feed = archive(site), feed_bodies(site)

    # If the archive endpoint is unreachable, fall back to feed-only so the
    # import still produces something rather than nothing.
    if not posts:
        print("! falling back to the feed alone -- older posts will be missing")
        posts = [{"slug": s_, "title": s_.replace("-", " ").title(), "subtitle": "",
                  "reactions": {}, "post_date": ""} for s_ in feed]

    # Full inventory first. If something you expect is not on this list then
    # Substack is not reporting it and no importer can find it -- use --add.
    print("\n--- everything Substack reports ---")
    for p_ in posts:
        print("    %-52s %s" % ((p_.get("slug") or "?")[:52],
                                (p_.get("title") or "")[:60]))
    print("--- end inventory ---\n")

    known = {p_.get("slug") for p_ in posts if p_.get("slug")}

    kept = []
    for p_ in posts:
        if limit and len(kept) >= limit:
            break
        got = import_one(site, p_, feed, known, force)
        if got:
            kept.append(got)

    meta = [(p_["slug"], p_.get("title") or "", p_.get("subtitle") or "",
             when(p_)[1]) for p_ in posts if p_.get("slug") in set(kept)]
    write_order(meta, force=reorder)

    print("\n%d articles in content/articles/" % len(kept))
    print("Commit content/articles/ to GitHub -- the site reads it directly "
          "and never calls Substack.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=SITE)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="re-import and overwrite json")
    ap.add_argument("--reorder", action="store_true", help="rebuild order.json")
    ap.add_argument("--add", default="", help="import one post by URL")
    a = ap.parse_args()
    if a.add:
        add_url(a.url, a.add, True)
    else:
        run(a.url, a.force, a.limit, a.reorder)


if __name__ == "__main__":
    main()
