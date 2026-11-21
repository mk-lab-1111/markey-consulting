# -*- coding: utf-8 -*-
"""
住宅市場レポート ビルドスクリプト

  reports/_src/YYYY-MM-DD.md  →  reports/YYYY-MM-DD.html（個別ページ）と reports/index.html（一覧）

あわせて次の2か所の「最新号」表示を、静的なHTMLで書き換える。
  - 登竜門トップ（toryumon/index.html）の住宅市場レポート欄
  - MARKEY CONSULTING の案内ページ（/reports.html）

ヘッダー・ナビ・フッター・CSS は build_column.py と同じく toryumon/index.html から取る。

  python3 tools/build_reports.py [toryumonフォルダ]
"""
import io, os, re, sys, html, datetime

try:
    import markdown
except ImportError:
    print("NG: markdown が必要です →  pip install markdown")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".."))
sys.argv = [sys.argv[0], ROOT]          # build_column も同じルートを使う
import build_column as bc               # noqa: E402

TOP = os.path.join(ROOT, "index.html")
RDIR = os.path.join(ROOT, "reports")
SRC = os.path.join(RDIR, "_src")
COLSRC = os.path.join(ROOT, "column", "_src")
SITE = "https://markey-consulting.com/toryumon/"
MARKEY_REPORTS = os.path.join(ROOT, "..", "reports.html")
E = html.escape

ORG_LD = ('"author":{"@type":"Organization","@id":"https://markey-consulting.com/toryumon/#editorial",'
          '"name":"住宅営業登竜門編集部","url":"https://markey-consulting.com/toryumon/#profile",'
          '"parentOrganization":{"@id":"https://markey-consulting.com/toryumon/#org"}},'
          '"publisher":{"@type":"Organization","@id":"https://markey-consulting.com/toryumon/#org",'
          '"name":"住宅営業登竜門","url":"https://markey-consulting.com/toryumon/",'
          '"logo":{"@type":"ImageObject","url":"https://markey-consulting.com/toryumon/assets/toryumon-logo.png"},'
          '"parentOrganization":{"@type":"Organization","@id":"https://markey-consulting.com/#org",'
          '"name":"MARKEY CONSULTING","url":"https://markey-consulting.com/"}}')


def die(msg):
    print("NG:", msg)
    sys.exit(1)


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# ---------- 1. 共通パーツ（reports/ は column/ と同じ深さ） ----------
def chrome():
    s = read(TOP)
    css = re.search(r"<style>\s*(.*?)\s*</style>", s, re.S).group(1)
    head = re.search(r"(<!-- ===== 1\. .*?)<!-- ===== 4\.", s, re.S).group(1).rstrip()
    foot = re.search(r"(<!-- ===== FOOTER ===== -->.*?</footer>)", s, re.S).group(1)

    def deepen(t):
        t = t.replace('href="./"', 'href="../"')
        t = re.sub(r'href="column/', 'href="../column/', t)
        t = t.replace('href="corporate.html"', 'href="../corporate.html"')
        t = t.replace('href="../toryumon-lp/"', 'href="../../toryumon-lp/"')
        t = t.replace('href="../reports.html"', 'href="./"')
        t = t.replace('href="../events.html"', 'href="../../events.html"')
        t = t.replace('src="assets/', 'src="../assets/')
        t = re.sub(r'href="#(?!")', 'href="../#', t)
        t = t.replace('href="../#report"', 'href="./"')
        return t
    return css, deepen(head), deepen(foot)


# ---------- 2. 原稿 ----------
def parse(path):
    raw = read(path)
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        die("先頭の --- で囲んだ設定がありません: " + os.path.basename(path))
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    slug = os.path.splitext(os.path.basename(path))[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", slug):
        die("ファイル名は YYYY-MM-DD.md にしてください: " + slug)
    for k in ("title", "published"):
        if not meta.get(k):
            die("%s に %s がありません" % (slug, k))
    meta["slug"] = slug
    meta["updated"] = meta.get("updated") or meta["published"]
    meta["draft"] = meta.get("draft", "").lower() in ("true", "yes", "1")
    body = m.group(2).strip()
    # 書き込みの途中で【…】が消えた原稿の救済：空の「****」は【概要】に戻す
    body = re.sub(r"^\*\*\*\*\s*$", "**【概要】**", body, flags=re.M)
    meta["body"] = body
    # タイトルに「【M月第N週】」がなければ、公開日から付ける
    if not meta["title"].startswith("【"):
        d = datetime.date.fromisoformat(meta["published"])
        meta["title"] = "【%d月第%d週】%s" % (d.month, (d.day + 6) // 7, meta["title"])
    wm = re.match(r"^【([^】]+)】\s*(.*)$", meta["title"])
    meta["week"], meta["headline"] = (wm.group(1), wm.group(2)) if wm else ("", meta["title"])
    if not meta.get("description"):
        meta["description"] = summary_text(meta["body"], 118)
    meta["topics"] = topics(meta["body"])
    meta["impl"] = first_impl(meta["body"])
    return meta


def plain(t):
    t = re.sub(r"\*\*|==|%%|`", "", t)
    return re.sub(r"\s+", " ", t).strip()


def summary_text(body, n):
    m = re.search(r"##\s*Executive Summary[^\n]*\n(.*?)(?=\n## |\Z)", body, re.S)
    part = m.group(1) if m else body
    for line in part.split("\n"):
        t = line.strip()
        if t and not t.startswith("#"):
            t = re.sub(r"^-?\s*\*\*[^*]+\*\*[:：]\s*", "", t)
            t = plain(t)
            return t[:n] + ("…" if len(t) > n else "")
    return ""


def topics(body):
    out = []
    for m in re.finditer(r"^###\s*[①②③④⑤]\s*(?:【([^】]+)】)?\s*(.+)$", body, re.M):
        out.append((m.group(1) or "", plain(m.group(2))))
    return out[:3]


def first_impl(body):
    m = re.search(r"##\s*今週のインプリケーション[^\n]*\n(.*?)(?=\n## |\Z)", body, re.S)
    if not m:
        return ""
    h = re.search(r"^###\s*(?:\d+\.\s*)?(.+)$", m.group(1), re.M)
    return plain(h.group(1)) if h else ""


def render(md_text):
    conv = markdown.Markdown(extensions=["extra", "sane_lists"])
    out = conv.convert(md_text)
    # 参照元のURLはリンクにする
    out = re.sub(r'(?<!href=")(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)',
                 r'<a href="\1" target="_blank" rel="noopener">\1</a>', out)
    toc = []

    def tag(mo):
        toc.append(("s%d" % (len(toc) + 1), re.sub(r"<[^>]+>", "", mo.group(1))))
        return '<h2 id="%s">%s</h2>' % (toc[-1][0], mo.group(1))
    out = re.sub(r"<h2>(.*?)</h2>", tag, out, flags=re.S)
    return out, toc


def dot(d):
    return d.replace("-", ".")


def jstr(s):
    return bc.jstr(s)


# ---------- 3. 関連コラム（タグ・タイトルの言葉の重なりで3本） ----------
def columns():
    cols = []
    if not os.path.isdir(COLSRC):
        return cols
    for f in sorted(os.listdir(COLSRC)):
        if not f.endswith(".md"):
            continue
        raw = read(os.path.join(COLSRC, f))
        m = re.match(r"﻿?---\s*\n(.*?)\n---", raw, re.S)
        if not m:
            continue
        d = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip()
        if d.get("draft", "").lower() in ("true", "yes", "1"):
            continue
        d["slug"] = f[:-3]
        d["words"] = [t.strip() for t in d.get("tags", "").split(",") if t.strip() and t.strip() != "住宅営業"]
        cols.append(d)
    return cols


def related(r, cols):
    text = r["title"] + r["body"]
    scored = []
    for c in cols:
        s = sum(text.count(w) for w in c["words"])
        if s:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:3]]


# ---------- 4. 個別ページ ----------
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;700;800&display=swap">\n'

THEME = """
  .rp { --crimson:#C2273F; --crimson-deep:#6E1424; --crimson-soft:#FBEAEC; --navy:#1B2540; --navy-deep:#0E1626;
        --gold:#C49A2E; --gold-light:#E9CE82; --cream:#FBF7F0; --ink:#23262E; --mist:#83899B; --line:#EAE2D2; background: var(--cream); }
  .rp .mincho { font-family: 'Shippori Mincho', serif; }
  .rp-hero { position: relative; overflow: hidden; padding: 34px 0 58px; background: linear-gradient(160deg, var(--navy) 0%, var(--navy-deep) 100%); }
  .rp-hero::before { content: ""; position: absolute; inset: 0; background: radial-gradient(ellipse at 82% 28%, rgba(194,39,63,.22) 0%, transparent 60%); }
  .rp-hero .in { position: relative; max-width: 1060px; margin: 0 auto; padding: 0 24px; }
  .rp-crumb { font-size: 12px; color: rgba(255,255,255,.6); }
  .rp-crumb a { color: rgba(255,255,255,.78); }
  .rp-crumb a:hover { color: var(--gold-light); }
  .rp-eyebrow { margin-top: 22px; font-family: 'Archivo', sans-serif; font-size: 12px; font-weight: 600; letter-spacing: .22em; color: var(--gold-light); }
  .rp-hero h1 { margin-top: 12px; font-family: 'Shippori Mincho', serif; font-weight: 700; color: #FFFFFF; font-size: clamp(24px, 3.4vw, 36px); line-height: 1.5; }
  .rp-hero h1 .wk { color: var(--gold-light); }
  .rp-lead { margin-top: 14px; max-width: 720px; font-size: 14.5px; line-height: 1.9; color: rgba(255,255,255,.74); }
  .rp-badges { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
  .rp-badge { display: inline-flex; align-items: center; gap: 7px; border: 1px solid rgba(255,255,255,.24); background: rgba(255,255,255,.08);
              border-radius: 100px; padding: 6px 15px; font-size: 12.5px; font-weight: 600; color: rgba(255,255,255,.88); }
  .rp-badge .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--gold-light); }
  .rp-wave { display: block; width: 100%; height: 40px; margin-top: -1px; }
  .rp-body { max-width: 1060px; margin: -10px auto 0; padding: 0 16px 70px; display: flex; flex-wrap: wrap; gap: 22px; align-items: flex-start; }
  .rp-main { flex: 1 1 560px; min-width: 0; background: #FFFFFF; border: 1px solid var(--line); border-radius: 20px;
             box-shadow: 0 18px 50px -22px rgba(27,37,64,.28); padding: 34px 38px 40px; }
  .rp-side { flex: 0 0 290px; min-width: 0; }
  .rp-card { background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 18px 18px; margin-bottom: 18px; }
  .rp-card h2 { font-family: 'Shippori Mincho', serif; font-size: 17px; color: var(--navy); padding-bottom: 10px; border-bottom: 2px solid var(--crimson); }
  .rp-card li a { display: block; padding: 11px 2px; border-bottom: 1px solid var(--line); }
  .rp-card li a:hover .t { color: var(--crimson); }
  .rp-card .d { display: block; font-size: 11px; color: var(--mist); }
  .rp-card .t { display: block; margin-top: 3px; font-size: 13.5px; font-weight: 700; line-height: 1.6; color: var(--ink); }
  @media (max-width: 800px) { .rp-main { padding: 24px 20px 30px; border-radius: 14px; } .rp-side { flex: 1 1 100%; } }

  /* 本文 */
  .rp .art, .rp .art p, .rp .art li { font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif; color: var(--ink); letter-spacing: 0; }
  .rp .art p { font-size: 15px; line-height: 1.95; margin: 0 0 18px; }
  .rp .art li { font-size: 15px; line-height: 1.85; margin-bottom: 6px; }
  .rp .art ul { list-style: disc; padding-left: 1.3em; margin: 0 0 20px; }
  .rp .art h2 { font-family: 'Shippori Mincho', serif; font-size: 22px; font-weight: 700; line-height: 1.5; color: var(--crimson);
                background: none; border: 0; border-left: 4px solid var(--crimson); padding: 2px 0 2px 14px; margin: 46px 0 18px; }
  .rp .art h2:first-child { margin-top: 6px; }
  .rp .art h3 { font-family: 'Shippori Mincho', serif; font-size: 19px; font-weight: 700; line-height: 1.55; color: var(--navy);
                border: 0; border-bottom: 1px solid var(--line); padding-bottom: 8px; margin: 32px 0 14px; }
  .rp .art h4 { font-size: 15.5px; color: var(--navy); border-left: 3px solid var(--gold); padding-left: 10px; margin: 22px 0 8px; }
  .rp .art strong { color: var(--navy); font-weight: 700; }
  .rp .art a { color: var(--crimson); text-decoration: underline; word-break: break-all; }
  .rp .art .imp { margin-top: 40px; padding: 26px 28px 10px; border-radius: 16px; background: var(--crimson-soft); border-left: 5px solid var(--crimson); }
  .rp .art .imp h2 { margin-top: 0; }
  .rp .art .imp h3 { border-bottom-color: rgba(194,39,63,.25); }
  .rp .art .src li { font-size: 13px; line-height: 1.75; color: #555B6B; }
  .rp .toc { margin-top: 26px; border: 1px solid var(--line); border-radius: 14px; background: var(--cream); padding: 18px 22px; }
  .rp .toc a { color: var(--navy); }
  .rp .toc a:hover { color: var(--crimson); }
  .rp .note { font-size: 12px; color: var(--mist); line-height: 1.8; }
  .rp .pn a { border-radius: 12px; border-color: var(--line); background: #FFFFFF; }
  .rp .pn a:hover { border-color: var(--crimson); }
  .rp .btn { display: inline-block; background: linear-gradient(120deg, var(--crimson), #9A1B30); color: #FFFFFF; font-size: 14px; font-weight: 700;
             padding: 13px 30px; border-radius: 100px; box-shadow: 0 12px 28px -12px rgba(194,39,63,.5); }
  /* 見出しの改行：日本語は文字単位で自然に折り返す（コラムの keep-all を打ち消す） */
  .rp h1, .rp h2, .rp h3, .rp h4, .rp .t, .rp .mincho { word-break: normal; overflow-wrap: anywhere; line-break: strict; text-wrap: pretty; }
  @media (max-width: 640px) { .rp-hero { padding: 24px 0 44px; } .rp-hero h1 { font-size: 22px; line-height: 1.6; } .rp-lead { font-size: 13.5px; } .rp-badge { font-size: 11.5px; padding: 5px 12px; }
    .rp-body { padding: 0 10px 50px; } .rp .art h2 { font-size: 19px; } .rp .art h3 { font-size: 17px; } .rp .art p, .rp .art li { font-size: 14px; } }

  .rp-cta { margin-top: 40px; border-radius: 18px; overflow: hidden; border: 2px solid var(--navy); background: #FFFFFF; }
  .rp-cta .hd { background: linear-gradient(160deg, var(--navy) 0%, var(--navy-deep) 100%); color: var(--gold-light); font-size: 13px; font-weight: 700; letter-spacing: .08em; padding: 10px 20px; }
  .rp-cta .bd { display: block; padding: 20px 22px 24px; }
  .rp-cta img { display: block; width: 100%; height: auto; border-radius: 10px; }
  .rp-cta .ttl { display: block; margin-top: 16px; font-family: 'Shippori Mincho', serif; font-size: 20px; font-weight: 700; line-height: 1.6; color: var(--navy); }
  .rp-cta .txt { display: block; margin-top: 8px; font-size: 14px; line-height: 1.85; color: #4A4A4A; }
  .rp-cta .btn { margin-top: 16px; }
  .rp-cta a:hover .ttl { color: var(--crimson); }

  /* 一覧 */
  .rp .latest { display: block; border-radius: 18px; overflow: hidden; border: 1px solid var(--line); box-shadow: 0 18px 50px -22px rgba(27,37,64,.28); }
  .rp .latest .hd { background: linear-gradient(120deg, var(--crimson-deep) 0%, var(--crimson) 100%); padding: 24px 28px; }
  .rp .latest .bd { background: var(--cream); padding: 20px 28px 24px; }
  .rp .latest:hover .bd { background: #FFFFFF; }
  .rp .pill { display: inline-block; background: rgba(255,255,255,.18); color: #FFFFFF; font-size: 11px; font-weight: 700; letter-spacing: .1em; padding: 3px 12px; border-radius: 100px; }
  .rp .month { margin-top: 30px; font-family: 'Shippori Mincho', serif; font-size: 17px; color: var(--navy); padding-bottom: 6px; border-bottom: 2px solid var(--gold); background: none; border-left: 0; }
  .rp .rlist li { border-bottom: 1px solid var(--line); }
  .rp .rlist a { color: var(--navy); }
  .rp .rlist a:hover { color: var(--crimson); }
  .rp .sec { font-family: 'Shippori Mincho', serif; font-size: 22px; color: var(--crimson); border-left: 4px solid var(--crimson); padding-left: 14px; margin: 40px 0 14px; }
"""

WAVE = ('<svg class="rp-wave" viewBox="0 0 1440 48" preserveAspectRatio="none" aria-hidden="true">'
        '<path d="M0,0 L1440,0 L1440,20 C1200,48 960,8 720,28 C480,48 240,4 0,24 Z" fill="#0E1626"/></svg>')


def hero(crumb, eyebrow, title_html, lead="", badges=()):
    b = "".join('<span class="rp-badge">%s</span>' % x for x in badges)
    return """<section class="rp-hero"><div class="in">
    <nav class="rp-crumb" aria-label="パンくず">%s</nav>
    <p class="rp-eyebrow">%s</p>
    <h1>%s</h1>
    %s<div class="rp-badges">%s</div>
  </div></section>
%s
""" % (crumb, eyebrow, title_html, ('<p class="rp-lead">%s</p>\n    ' % lead) if lead else "", b, WAVE)


def course_banner(campaign):
    """住宅営業登竜門（動画講座）のバナー。レポートの本文の終わりと一覧に置く"""
    href = "../../toryumon-lp/?utm_source=report&utm_medium=banner&utm_campaign=" + campaign
    return """      <aside class="rp-cta" aria-label="住宅営業登竜門 動画講座のご案内">
        <p class="hd">住宅営業登竜門 動画講座のご案内</p>
        <a class="bd" href="%s">
          <img src="../assets/video-course.jpg" alt="住宅営業登竜門 動画講座">
          <span class="ttl">市場が変わっても売れる営業へ。トップセールスの「型」を動画で学べます。</span>
          <span class="txt">全16プログラム・100本以上。1本10〜15分で、要約と目次付き。スマホ・PC・タブレットで、倍速でも視聴できます。</span>
          <span class="btn">動画講座の詳細を見る ›</span>
        </a>
      </aside>
""" % E(href)


def wrap_rp(hero_html, main_inner, side_html):
    return """
<main class="rp">
%s<div class="rp-body">
  <div class="rp-main">
%s
  </div>
  <div class="rp-side">
%s  </div>
</div>
</main>
""" % (hero_html, main_inner, side_html)


CSS = """
  .rp-meta { margin-top: 14px; padding-bottom: 18px; border-bottom: 1px solid #D4D4D4; font-size: 12px; color: #6B6B6B; line-height: 1.9; }
  .art h4 { font-size: 16px; line-height: 1.6; margin: 22px 0 8px; padding-left: 10px; border-left: 4px solid #17547E; }
  .art a { word-break: break-all; }
  .pn { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 40px; }
  .pn a { flex: 1 1 260px; display: block; border: 1px solid #D4D4D4; padding: 14px 16px; }
  .pn a:hover { border-color: #111111; }
  .pn .l { display: block; font-size: 11px; font-weight: 700; color: #8A8A8A; }
  .pn .t { display: block; margin-top: 4px; font-size: 14px; font-weight: 700; line-height: 1.6; }
  .rlist li { display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 12px 4px; border-bottom: 1px solid #E2E2E2; }
  .rlist .d { flex: 0 0 auto; min-width: 92px; font-size: 13px; color: #666666; }
  .rlist a { flex: 1 1 300px; font-size: 15px; font-weight: 700; line-height: 1.6; color: #111111; }
  .rlist a:hover { color: #C2273F; }
  .rlist .w { font-size: 12px; font-weight: 700; color: #C2273F; margin-right: 8px; }
  .month { margin-top: 30px; font-size: 15px; font-weight: 900; padding: 8px 12px; background: #F2F2F2; border-left: 5px solid #E8A33D; }
  .latestcard { display: block; margin-top: 18px; border: 2px solid #111111; padding: 22px 24px; }
  .latestcard:hover { border-color: #C2273F; }
  .note { font-size: 12px; color: #6B6B6B; line-height: 1.8; }
"""


def side(reps, current=None):
    others = [r for r in reps if r["slug"] != current][:5]
    rows = "".join('        <li><a href="%s.html"><span class="d en">%s</span><span class="t">%s</span></a></li>\n'
                   % (r["slug"], dot(r["published"]), E(r["title"])) for r in others)
    return """    <div class="rp-card">
      <h2>最新のレポート</h2>
      <ul>
%s      </ul>
      <a href="./" style="display: block; margin-top: 10px; text-align: right; font-size: 13px; font-weight: 700; color: #C2273F;">レポート一覧 ›</a>
    </div>
    <a class="rp-card" href="../column/" style="display: block;">
      <span class="en" style="display: block; font-size: 11px; font-weight: 600; letter-spacing: .2em; color: #83899B;">COLUMN</span>
      <span style="display: block; margin-top: 6px; font-size: 15px; font-weight: 900; line-height: 1.6;">住宅営業の「型」を学ぶコラム</span>
      <span style="display: block; margin-top: 6px; font-size: 12px; color: #5C5C5C;">初回接客からクロージングまで ›</span>
    </a>
    <a class="rp-card" href="../../toryumon-lp/" style="display: block; border: 3px solid #C2273F;">
      <img src="../assets/video-course.jpg" alt="住宅営業登竜門 動画講座" style="display: block; width: 100%%; height: auto; border-radius: 8px;">
      <span style="display: block; margin-top: 12px; font-size: 14px; font-weight: 700; line-height: 1.7;">トップセールス直伝の動画講座（月額制）</span>
    </a>
    <a class="rp-card" href="../../" style="display: block;">
      <span style="display: block; font-size: 14px; font-weight: 900; line-height: 1.5;">住宅会社の経営・営業組織のご相談</span>
      <span style="display: block; margin-top: 6px; font-size: 12px; line-height: 1.8; color: #5C5C5C;">MARKEY CONSULTING ›</span>
    </a>
""" % rows


def wrap(main_inner, side_html):
    return """
<main class="artwrap" style="background: #2E2E2E; padding: 24px 16px 70px;">
  <div class="wrapx" style="max-width: 960px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-start;">
  <div class="colbox ix" style="flex: 1 1 0; min-width: 0; background: #FFFFFF; border-top: 6px solid #E8A33D;">
%s
  </div>
  <div class="sidebx" style="flex: 0 0 290px; min-width: 0; background: #FFFFFF; padding: 16px 14px; border-top: 6px solid #E8A33D;">
%s  </div>
  </div>
</main>
""" % (main_inner, side_html)


def report_page(r, reps, cols, css, head_html, foot_html):
    i = reps.index(r)
    newer = reps[i - 1] if i > 0 else None
    older = reps[i + 1] if i + 1 < len(reps) else None
    url = SITE + "reports/" + r["slug"] + ".html"
    body, toc = render(r["body"])

    # インプリケーションの節は色付きの箱に、参照元の節は小さい文字に
    body = re.sub(r'(<h2 id="s\d+">今週のインプリケーション.*?)(?=<h2 id=|\Z)', r'<div class="imp">\1</div>', body, flags=re.S)
    body = re.sub(r'(<h2 id="s\d+">一次情報.*?</h2>\s*)<ul>', r'\1<ul class="src">', body, flags=re.S)

    toc_html = ""
    if len(toc) >= 2:
        toc_html = ('      <nav class="toc" aria-label="このレポートの目次">\n'
                    '        <p class="mincho" style="font-size: 16px; font-weight: 700; color: #1B2540;">このレポートの目次</p>\n        <ul style="margin-top: 8px;">\n'
                    + "".join('          <li style="border-bottom: 1px solid #EAE2D2;"><a href="#%s" style="display: block; padding: 8px 2px; font-size: 14px; font-weight: 700; line-height: 1.6;">%s</a></li>\n' % (a, E(t)) for a, t in toc)
                    + "        </ul>\n      </nav>\n")

    pn = '      <div class="pn">\n'
    if older:
        pn += '        <a href="%s.html"><span class="l">‹ 前の号</span><span class="t">%s</span></a>\n' % (older["slug"], E(older["title"]))
    if newer:
        pn += '        <a href="%s.html" style="text-align: right;"><span class="l">次の号 ›</span><span class="t">%s</span></a>\n' % (newer["slug"], E(newer["title"]))
    pn += '      </div>\n      <p style="margin-top: 22px; text-align: center;"><a class="btn" href="./">住宅市場レポートの一覧へ</a></p>\n'

    rel = related(r, cols)
    rel_html = ""
    if rel:
        rel_html = ('      <section>\n        <h2 class="sec">営業の現場で使う：関連コラム</h2>\n        <ul class="rlist">\n'
                    + "".join('          <li><a href="../column/%s.html">%s</a></li>\n' % (c["slug"], E(c.get("title", ""))) for c in rel)
                    + "        </ul>\n      </section>\n")

    badges = ['<span class="dot"></span>公開 %s' % dot(r["published"])]
    if r["updated"] != r["published"]:
        badges.append("更新 %s" % dot(r["updated"]))
    if r.get("period"):
        badges.append("対象期間 %s" % E(r["period"]))
    badges.append("編集：住宅営業登竜門編集部")
    title_html = ('<span class="wk">【%s】</span><br>%s' % (E(r["week"]), E(r["headline"]))) if r["week"] else E(r["title"])
    hero_html = hero('<a href="../">住宅営業登竜門</a> › <a href="./">住宅市場レポート</a> › <span>%s</span>' % E(r["week"] or "レポート"),
                     "WEEKLY MARKET REPORT", title_html, "", badges)

    inner = """    <article style="min-width: 0;">
%s      <div class="art" style="margin-top: 30px;">
%s
      </div>
      <p class="note" style="margin-top: 30px;">※本レポートは、公表資料・報道をもとに編集部がまとめた情報提供です。数値・制度は各発表元の最新情報をご確認ください。「背景とポイント」「インプリケーション」は編集部の考察です。運営：MARKEY CONSULTING</p>
%s%s%s    </article>""" % (toc_html, body, course_banner("report-" + r["slug"]), pn, rel_html)

    ld = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Article",
 "headline":%s,"description":%s,"url":%s,
 "datePublished":"%s","dateModified":"%s","inLanguage":"ja",
 %s,
 "mainEntityOfPage":{"@type":"WebPage","@id":%s}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"name":"住宅営業登竜門","item":"%s"},
 {"@type":"ListItem","position":2,"name":"住宅市場レポート","item":"%sreports/"},
 {"@type":"ListItem","position":3,"name":%s}]}
</script>
""" % (jstr(r["title"][:110]), jstr(r["description"]), jstr(url), r["published"], r["updated"],
       ORG_LD, jstr(url), SITE, SITE, jstr(r["title"]))

    page = bc.page(r["title"] + "｜住宅市場レポート｜住宅営業登竜門", r["description"], url,
                   css + CSS + THEME, head_html, foot_html, wrap_rp(hero_html, inner, side(reps, r["slug"])),
                   noindex=r["draft"], ld=FONT + ld)
    return page


# ---------- 5. 一覧ページ ----------
def index_page(reps, css, head_html, foot_html):
    url = SITE + "reports/"
    lt = reps[0]
    tp = "".join('          <li style="margin-top: 7px; font-size: 14px; line-height: 1.6;"><span class="w" style="color: #C2273F; font-weight: 700; margin-right: 8px;">%s</span>%s</li>\n'
                 % (E(c), E(t)) for c, t in lt["topics"])
    latest = """    <h2 class="sec" style="margin-top: 4px;">最新号</h2>
    <a class="latest" href="%s.html">
      <div class="hd">
        <span class="pill">LATEST</span>
        <span class="en" style="margin-left: 10px; font-size: 13px; color: rgba(255,255,255,.75);">%s　%s</span>
        <span class="mincho" style="display: block; margin-top: 10px; font-size: 22px; font-weight: 700; line-height: 1.55; color: #FFFFFF;">%s</span>
      </div>
      <div class="bd">
        <span style="display: block; font-size: 14px; line-height: 1.85; color: #4A4A4A;">%s</span>
        <ul style="margin-top: 8px;">
%s        </ul>
        <span class="btn" style="margin-top: 16px;">最新号を読む ›</span>
      </div>
    </a>
""" % (lt["slug"], E(lt["week"] or "最新号"), dot(lt["published"]), E(lt["headline"]), E(lt["description"]), tp)

    months, cur = [], None
    for r in reps:
        ym = r["published"][:7]
        if ym != cur:
            months.append((ym, []))
            cur = ym
        months[-1][1].append(r)
    arch = ""
    for ym, rs in months:
        arch += '      <p class="month">%s年%d月</p>\n      <ul class="rlist">\n' % (ym[:4], int(ym[5:]))
        arch += "".join('        <li><span class="d en">%s</span><a href="%s.html">%s</a></li>\n'
                        % (dot(r["published"]), r["slug"], E(r["title"])) for r in rs)
        arch += "      </ul>\n"

    hero_html = hero('<a href="../">住宅営業登竜門</a> › <span>住宅市場レポート</span>', "WEEKLY MARKET REPORT",
                     '住宅市場<span class="wk">レポート</span>',
                     "大手ハウスメーカーの受注速報、顧客マインド、不動産価格、倒産動向など、住宅会社の経営と営業の受注判断に効く業界ニュースを、毎週まとめてお届けしています。各号の数字には出典を付けています。",
                     ['<span class="dot"></span>毎週更新', "出典付き", "全%d号" % len(reps), "編集：住宅営業登竜門編集部"])
    inner = """%s%s
    <section>
      <h2 class="sec">バックナンバー</h2>
%s    </section>""" % (latest, course_banner("report-index"), arch)

    ld = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"CollectionPage","name":"住宅市場レポート","url":%s,"inLanguage":"ja",
 "isPartOf":{"@id":"https://markey-consulting.com/toryumon/#org"},
 "mainEntity":{"@type":"ItemList","itemListElement":[%s]}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"name":"住宅営業登竜門","item":"%s"},
 {"@type":"ListItem","position":2,"name":"住宅市場レポート"}]}
</script>
""" % (jstr(url), ",".join('{"@type":"ListItem","position":%d,"url":%s}' % (k + 1, jstr(SITE + "reports/" + r["slug"] + ".html")) for k, r in enumerate(reps[:30])), SITE)

    return bc.page("住宅市場レポート（毎週更新）｜住宅営業登竜門",
                   "住宅会社の経営者・営業責任者向けの週次レポート。大手ハウスメーカーの受注速報、住宅ローン金利、制度、倒産動向などを出典付きでまとめています。最新号とバックナンバーはこちら。",
                   url, css + CSS + THEME, head_html, foot_html, wrap_rp(hero_html, inner, side(reps)), ld=FONT + ld)


# ---------- 6. 登竜門トップ・MARKEYの案内ページ ----------
def replace_block(s, name, new, path):
    a, b = "<!-- %s:START -->" % name, "<!-- %s:END -->" % name
    if a not in s or b not in s:
        die("%s に %s の目印がありません" % (path, name))
    i, j = s.index(a) + len(a), s.index(b)
    return s[:i] + "\n" + new + s[j:]


def top_block(lt, n):
    colors = ["#17547E", "#7A5A10", "#C2273F"]
    link = "reports/%s.html" % lt["slug"]
    lis = "".join(
        '            <li style="border-bottom: 1px solid #D4D4D4;"><a href="%s" class="row" style="display: flex; gap: 12px; padding: 15px 6px;"><span class="en" style="flex: 0 0 auto; font-size: 13px; font-weight: 800; color: #C2273F;">0%d</span><span>%s<span style="display: block; margin-top: 4px; font-size: 15px; font-weight: 700; line-height: 1.65;">%s</span></span></a></li>\n'
        % (link, k + 1, ('<span style="display: block; font-size: 11px; font-weight: 700; color: %s;">%s</span>' % (colors[k], E(c))) if c else "", E(t[:48] + ("…" if len(t) > 48 else "")))
        for k, (c, t) in enumerate(lt["topics"]))
    if lt["impl"]:
        lis += ('            <li style="border-bottom: 1px solid #D4D4D4;"><a href="%s" class="row" style="display: block; padding: 15px 6px;"><span style="display: block; font-size: 11px; font-weight: 700; color: #8A8A8A;">今週のインプリケーション</span><span style="display: block; margin-top: 4px; font-size: 15px; font-weight: 700; line-height: 1.65;">%s ›</span></a></li>\n'
                % (link, E(lt["impl"][:60])))
    return """        <a id="rp-link" href="%s" class="lead" style="flex: 2 1 440px; min-width: 0; display: block;">
          <div style="position: relative; width: 100%%; height: 250px; overflow: hidden;">
            <img src="assets/report-photo.jpg" alt="建築中の木造住宅の軸組" style="display: block; width: 100%%; height: 100%%; object-fit: cover;">
            <span style="position: absolute; left: 0; bottom: 0; background: #111111; color: #FFFFFF; font-size: 12px; font-weight: 700; letter-spacing: .06em; padding: 9px 18px;">住宅市場レポート　最新号</span>
          </div>
          <p id="rp-date" style="margin-top: 14px; font-size: 12px; font-weight: 700; color: #C2273F;">最新号　%s　<span class="en">%s</span></p>
          <h3 id="rp-title" style="margin-top: 8px; font-size: 25px; line-height: 1.5;">%s</h3>
          <p id="rp-sum" style="margin-top: 12px; font-size: 14px; line-height: 1.9; color: #4A4A4A;">%s</p>
          <p style="margin-top: 14px; font-size: 13px; font-weight: 700; color: #C2273F;">レポートを読む ›</p>
        </a>

        <!-- バックナンバー -->
        <div style="flex: 1 1 320px; min-width: 0;">
          <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .2em; color: #8A8A8A; padding-bottom: 10px; border-bottom: 1px solid #111111;">THIS WEEK'S TOPICS</p>
          <ul id="rp-topics">
%s          </ul>
          <a href="reports/" class="rp-allbtn" style="display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 16px; background: #1B2540; color: #FFFFFF; font-size: 15px; font-weight: 700; padding: 16px 18px; border-left: 6px solid #C49A2E;">過去のレポート一覧を見る（全%d号） <span style="color: #E9CE82;">›</span></a>
""" % (link, E(lt["week"]), dot(lt["published"]), E(lt["headline"]), E(lt["description"]), lis, n)


def markey_block(reps):
    rows = "".join(
        '      <li><a href="toryumon/reports/%s.html"><span class="d">%s</span><span class="t">%s</span></a></li>\n'
        % (r["slug"], dot(r["published"]), E(r["title"])) for r in reps[:10])
    return """<style>
.rp-wrap{padding:64px 0 72px;background:var(--paper);}
.rp-list{list-style:none;margin-top:22px;border-top:1px solid var(--line);}
.rp-list li{border-bottom:1px solid var(--line);}
.rp-list a{display:flex;flex-wrap:wrap;gap:4px 18px;padding:16px 6px;text-decoration:none;color:var(--ink);}
.rp-list a:hover .t{color:var(--crimson);}
.rp-list .d{flex:0 0 auto;min-width:96px;font-size:13px;color:var(--mist);}
.rp-list .t{flex:1 1 320px;font-size:15.5px;font-weight:700;line-height:1.65;}
.rp-more{text-align:center;margin-top:34px;}
.rp-note{margin-top:12px;font-size:13px;color:var(--mist);}
</style>
<section class="rp-wrap">
  <div class="container">
    <div class="sec-head">
      <p class="eyebrow">LATEST</p>
      <h2 style="font-size:clamp(22px,2.8vw,30px);">最新のレポート</h2>
      <p>タイトルを押すと、各号の全文（住宅営業登竜門のページ）が開きます。</p>
    </div>
    <ul class="rp-list">
%s    </ul>
    <div class="rp-more">
      <a class="btn btn-primary" href="toryumon/reports/">すべてのレポートを見る（住宅営業登竜門）</a>
      <p class="rp-note">全%d号のバックナンバーを、住宅営業登竜門に掲載しています。</p>
    </div>
  </div>
</section>
""" % (rows, len(reps))


# ---------- 7. 実行 ----------
def main():
    if not os.path.isdir(SRC):
        die("原稿フォルダがありません: " + SRC)
    css, head_html, foot_html = chrome()
    reps = [parse(os.path.join(SRC, f)) for f in sorted(os.listdir(SRC)) if f.endswith(".md")]
    reps = [r for r in reps if not r["draft"]]
    if not reps:
        die("公開する原稿がありません")
    reps.sort(key=lambda r: r["published"], reverse=True)
    cols = columns()

    for r in reps:
        write(os.path.join(RDIR, r["slug"] + ".html"), report_page(r, reps, cols, css, head_html, foot_html))
    write(os.path.join(RDIR, "index.html"), index_page(reps, css, head_html, foot_html))
    print("  レポート:", len(reps), "号（最新", reps[0]["slug"] + "）")

    s = read(TOP)
    write(TOP, replace_block(s, "REPORT-LATEST", top_block(reps[0], len(reps)), TOP))
    print("  登竜門トップの最新号を更新")

    if os.path.exists(MARKEY_REPORTS):
        s = read(MARKEY_REPORTS)
        write(MARKEY_REPORTS, replace_block(s, "REPORT-LIST", markey_block(reps), MARKEY_REPORTS))
        print("  reports.html（MARKEY）の一覧を更新")


if __name__ == "__main__":
    main()
