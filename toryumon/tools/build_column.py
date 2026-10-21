# -*- coding: utf-8 -*-
"""
住宅営業登竜門コラム ビルドスクリプト

  column/_src/*.md  →  column/<slug>.html  と  column/index.html

ヘッダー・ナビ・フッター・CSS は toryumon/index.html から抜き出して使い回す。
トップページを直せば記事ページにも自動で反映されるので、二重管理にならない。

  python3 tools/build_column.py [サイトのルート]
"""
import io, os, re, sys, math, html, datetime

try:
    import markdown
except ImportError:
    print("NG: markdown が必要です →  pip install markdown")
    sys.exit(1)

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.path.abspath(ROOT)
TOP = os.path.join(ROOT, "index.html")
COL = os.path.join(ROOT, "column")
SRC = os.path.join(COL, "_src")
SITE = "https://markey-consulting.com/toryumon/"

CAT_COLOR = {
    "営業スキルを上げたい": "#111111",
    "止まった受注を動かしたい": "#C2273F",
    "部下・チームを育てたい": "#17547E",
    "育成の仕組みを作りたい": "#7A5A10",
}
FW_COLOR = {
    "営業マインド": "#111111",
    "営業知識・営業スキル": "#C2273F",
    "商談戦略": "#17547E",
    "アピアランス・トナリティ": "#7A5A10",
    "顧客管理": "#4A2E6E",
}


FW_KEY = {
    "営業マインド": "mind",
    "営業知識・営業スキル": "skill",
    "商談戦略": "plan",
    "アピアランス・トナリティ": "look",
    "顧客管理": "mgmt",
}
FW_INTRO = "成約フレームワーク"          # 5つの総論。5分類の箱には入れず、「はじめに」として別に出す
FW_COLOR[FW_INTRO] = "#E8A33D"


def die(msg):
    print("NG:", msg)
    sys.exit(1)


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(s)


# ---------- 1. トップページから共通パーツを抜き出す ----------
def chrome():
    if not os.path.exists(TOP):
        die("トップページが見つかりません: " + TOP)
    s = read(TOP)

    m = re.search(r"<style>\s*(.*?)\s*</style>", s, re.S)
    if not m:
        die("トップページに <style> がありません")
    css = m.group(1)

    m = re.search(r"(<!-- ===== 1\. .*?)<!-- ===== 4\.", s, re.S)
    if not m:
        die("ヘッダー部分が見つかりません")
    head_html = m.group(1).rstrip()

    m = re.search(r"(<!-- ===== FOOTER ===== -->.*?</footer>)", s, re.S)
    if not m:
        die("フッターが見つかりません")
    foot_html = m.group(1)

    # column/ は1階層深いので参照先をずらす
    def deepen(t):
        t = t.replace('href="./"', 'href="../"')
        t = t.replace('href="column/#', 'href="./#').replace('href="column/"', 'href="./"')
        t = t.replace('href="corporate.html"', 'href="../corporate.html"')
        t = t.replace('href="../toryumon-lp/"', 'href="../../toryumon-lp/"')
        t = t.replace('href="../reports.html"', 'href="../../reports.html"')
        t = t.replace('href="../events.html"', 'href="../../events.html"')
        t = t.replace('src="assets/', 'src="../assets/')
        # トップページ内のアンカーはトップページへ戻す
        t = re.sub(r'href="#(?!")', 'href="../#', t)
        # ナビとフッターの「コラム」は一覧ページへ
        t = t.replace('href="../#column"', 'href="./"')
        return t

    return css, deepen(head_html), deepen(foot_html)


# ---------- 2. 原稿を読む ----------
def parse(path):
    raw = read(path)
    m = re.match(r"\ufeff?---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        die("先頭の --- で囲んだ設定が見つかりません: " + os.path.basename(path))
    meta, body = {}, m.group(2).strip()
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            die("設定の書き方が違います（key: value）: " + line)
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()

    for k in ("title", "description", "framework", "audience", "published"):
        if not meta.get(k):
            die("%s に %s がありません" % (os.path.basename(path), k))
    if meta["framework"] not in FW_COLOR:
        die("framework が一覧にありません: " + meta["framework"])

    meta["slug"] = os.path.splitext(os.path.basename(path))[0]
    meta["updated"] = meta.get("updated", meta["published"])
    meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    meta["draft"] = meta.get("draft", "").lower() in ("true", "yes", "1")
    meta["body"] = body
    return meta


def minutes(md_text):
    plain = re.sub(r"[#>*\-`\[\]()!|]", "", md_text)
    plain = re.sub(r"\s+", "", plain)
    return max(3, math.ceil(len(plain) / 550))


# ---------- 3. 本文を組み立てる ----------
def render_body(md_text):
    """markdown → (本文HTML, 目次, FAQ)"""
    conv = markdown.Markdown(extensions=["extra", "sane_lists"])

    # 強調の書き方:  **太字**   ==黄色マーカー==   %%赤字%%
    md_text = re.sub(r"==(.+?)==", r'<mark class="mk">\1</mark>', md_text)
    md_text = re.sub(r"%%(.+?)%%", r'<span class="rd">\1</span>', md_text)

    # 「よくある質問」セクションを切り出す
    faq = []
    m = re.search(r"\n##\s*よくある質問\s*\n(.*)$", md_text, re.S)
    if m:
        md_text = md_text[:m.start()]
        for q, a in re.findall(r"###\s*(.+?)\n(.*?)(?=\n###\s|\Z)", m.group(1), re.S):
            faq.append((q.strip(), conv.reset().convert(a.strip())))

    body = conv.reset().convert(md_text)

    # h2 に id を振って目次を作る
    toc = []

    def tag(mo):
        n = len(toc) + 1
        t = re.sub(r"<[^>]+>", "", mo.group(1))
        toc.append((("s%d" % n), t))
        return '<h2 id="s%d">%s</h2>' % (n, mo.group(1))

    body = re.sub(r"<h2>(.*?)</h2>", tag, body, flags=re.S)
    return body, toc, faq


# ---------- 4. 部品 ----------
def chip(text, color, small=False):
    fs = "11px" if small else "12px"
    return ('<span style="display: inline-flex; align-items: center; gap: 8px; '
            'font-size: %s; font-weight: 700; color: %s;">'
            '<span style="width: 8px; height: 8px; background: %s; flex-shrink: 0;"></span>%s</span>'
            % (fs, color, color, html.escape(text)))


def card_row(a, base=""):
    """一覧・関連記事の1行"""
    return """        <li style="border-bottom: 1px solid #D4D4D4;">
          <a href="%s%s.html" class="row" style="display: flex; flex-wrap: wrap; gap: 20px; padding: 20px 8px; align-items: flex-start;">
            <div style="flex: 0 0 auto; display: flex; flex-direction: column; gap: 7px; min-width: 180px;">
              %s
              <span class="en" style="font-size: 12px; color: #8A8A8A;">%s ・ 読了 %d分</span>
            </div>
            <div style="flex: 1 1 380px; min-width: 0;">
              <h3 style="font-size: 18px; line-height: 1.6;">%s%s</h3>
              <p style="margin-top: 7px; font-size: 13px; line-height: 1.85; color: #5C5C5C;">%s</p>
            </div>
          </a>
        </li>
""" % (base, a["slug"], chip(a["framework"], FW_COLOR[a["framework"]], True),
       a["published"].replace("-", "."), a["min"],
       '<span style="font-size: 11px; font-weight: 700; color: #FFFFFF; background: #8A8A8A; padding: 3px 9px; margin-right: 9px; vertical-align: middle;">下書き</span>' if a["draft"] else "",
       html.escape(a["title"]), html.escape(a["description"]))


def rail(arts, current=None):
    """記事ページの右カラム"""
    latest = [a for a in arts if a["slug"] != current][:4]
    rows = "".join("""            <li style="border-bottom: 1px solid #D4D4D4;">
              <a href="%s.html" class="row" style="display: block; padding: 13px 6px;">
                <span class="en" style="display: block; font-size: 11px; color: #8A8A8A;">%s</span>
                <span style="display: block; margin-top: 4px; font-size: 14px; font-weight: 700; line-height: 1.6;">%s</span>
              </a>
            </li>
""" % (a["slug"], a["published"].replace("-", "."), html.escape(a["title"])) for a in latest)
    if not rows:
        rows = ('            <li style="padding: 13px 6px; font-size: 13px; color: #8A8A8A;">'
                '記事が増えるとここに並びます。</li>\n')

    return """        <aside style="flex: 1 1 290px; min-width: 0; display: flex; flex-direction: column;">
          <h2 style="font-size: 18px; line-height: 1.4; background: #333333; color: #FFFFFF; text-align: center; padding: 16px 12px;">最新コラム</h2>
          <ul style="margin-top: 14px;">
%s          </ul>
          <a href="./" style="display: block; margin-top: 12px; text-align: right; font-size: 13px; font-weight: 700;">コラム一覧 ›</a>

          <a href="../../toryumon-lp/" style="display: block; margin-top: 26px; border: 4px solid #C2273F; padding: 14px;">
            <img src="../assets/video-course.jpg" alt="住宅営業登竜門 動画講座" style="display: block; width: 100%%; height: auto;">
            <span style="display: block; margin-top: 12px; font-size: 14px; font-weight: 700; line-height: 1.7;">トップセールス直伝の動画が見放題。<span style="color: #C2273F;">～キャンペーン実施中～</span></span>
          </a>

          <div style="margin-top: 26px; border-top: 2px solid #111111; padding-top: 16px;">
            <a href="../../events.html" class="dk grad" style="min-height: 250px; padding: 26px 24px; display: flex; flex-direction: column; justify-content: center;">
              <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .22em; color: #E8A33D;">SEMINAR</p>
              <p style="margin-top: 12px; font-size: 20px; font-weight: 900; line-height: 1.5; color: #FFFFFF;">受注UPセミナーを<br>随時開催しています</p>
              <p style="margin-top: 10px; font-size: 12px; line-height: 1.8; color: #B8B8B8;">オンライン／動画視聴／リアル参加　各回20名・無料</p>
              <span style="display: inline-block; align-self: flex-start; margin-top: 16px; background: #C2273F; color: #FFFFFF; font-size: 13px; font-weight: 700; padding: 11px 22px;">開催予定を見る ›</span>
            </a>
            <a href="../#contact" class="row" style="display: block; margin-top: 14px; border: 1px dashed #9B9B9B; padding: 16px 18px;">
              <span style="display: block; font-size: 14px; font-weight: 900; line-height: 1.5;">広告掲載のご案内</span>
              <span style="display: block; margin-top: 6px; font-size: 12px; line-height: 1.8; color: #5C5C5C;">工務店・住宅会社向けにサービスを提供されている企業様へ ›</span>
            </a>
          </div>

          <div class="dk grad" style="margin-top: 26px; padding: 26px 24px;">
            <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .22em; color: #E8A33D;">MAIL MAGAZINE</p>
            <p style="margin-top: 12px; font-size: 19px; font-weight: 900; line-height: 1.55; color: #FFFFFF;">住宅市場レポートを<br>メールでお届けします</p>
            <p style="margin-top: 12px; font-size: 13px; line-height: 1.85; color: #B8B8B8;">金利・建材・競合・来場動向などの市場情報をメールで。登録は無料です。</p>
            <form style="margin-top: 16px;">
              <label for="mm-col" style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);">メールアドレス</label>
              <input id="mm-col" type="email" placeholder="メールアドレス" style="width: 100%%; border: 1px solid #4A4A4A; background: #000000; color: #FFFFFF; font-family: 'Zen Kaku Gothic New', sans-serif; font-size: 13px; padding: 13px 14px;">
              <button type="button" style="width: 100%%; margin-top: 9px; border: 0; background: #C2273F; color: #FFFFFF; font-size: 14px; font-weight: 700; padding: 14px;">無料で登録する</button>
            </form>
          </div>
        </aside>
""" % rows


EXTRA_CSS = """
  h1, h2, h3 { word-break: keep-all; overflow-wrap: anywhere; }
  .art h2 { font-size: 27px; line-height: 1.55; margin: 48px 0 18px;
            padding-bottom: 12px; border-bottom: 2px solid #111111; }
  .art h3 { font-size: 20px; line-height: 1.6; margin: 34px 0 12px; }
  .art p { font-size: 16px; line-height: 2.05; margin: 0 0 20px; color: #222222; }
  .art ul, .art ol { margin: 0 0 22px; padding-left: 1.4em; }
  .art ul { list-style: disc; }
  .art ol { list-style: decimal; }
  .art li { font-size: 16px; line-height: 2; margin-bottom: 8px; }
  .art strong { font-weight: 900; }
  .art mark.mk { background: linear-gradient(transparent 52%, #FFE94A 52%); color: inherit; padding: 0 2px; font-weight: 700; }
  .art .rd { color: #D3202F; font-weight: 700; }
  .art table { width: 100%; border-collapse: collapse; margin: 0 0 8px; font-size: 14px; }
  .art th { background: #333333; color: #FFFFFF; text-align: left; padding: 10px 14px; font-weight: 700; }
  .art td { border-bottom: 1px solid #DDDDDD; padding: 10px 14px; line-height: 1.6; }
  .art tr:nth-child(even) td { background: #F6F6F6; }
  .art td:first-child { white-space: nowrap; font-weight: 700; }
  @media (max-width: 640px) { .art td:first-child { white-space: normal; width: 38%; } .art th, .art td { padding: 8px 8px; font-size: 13px; } }
  .art table.chk { border: 1px solid #BBBBBB; }
  .art table.chk th, .art table.chk td { border: 1px solid #CCCCCC; }
  .art table.chk tr.fw th { border-color: #C2273F; }
  .art table.chk thead th { border-color: #555555; font-size: 18px; line-height: 1.2; }
  .art table.chk th, .art table.chk td { text-align: center; }
  .art table.chk th:first-child, .art table.chk td:first-child { text-align: left; }
  .art table.chk td:first-child { white-space: normal; font-weight: 400; }
  .art table.chk tr.fw th { background: #C2273F; text-align: left; font-size: 14px; }
  .art table.chk td.m { width: 52px; color: #333333; cursor: pointer; font-size: 24px; line-height: 1; font-weight: 900; user-select: none; }
  .art table.chk td.m:hover { background: #FFF6D6; }
  .art table.chk td.m.on-o { color: #D3202F; background: #FFF0F0; }
  .art table.chk td.m.on-t { color: #B36B00; background: #FFF6D6; }
  .art table.chk td.m.on-x { color: #111111; background: #E6E6E6; }
  .art p.note { font-size: 12px; color: #666666; }
  .art img { display: block; max-width: 100%; height: auto; margin: 26px auto; }
  .endcta { margin-top: 48px; border: 2px solid #111111; }
  .endcta .hd { background: #111111; color: #FFFFFF; padding: 10px 18px; font-size: 13px; font-weight: 700; letter-spacing: .08em; }
  .endcta .bd { padding: 20px 20px 22px; }
  .endcta img { display: block; width: 100%; height: auto; margin: 0 0 16px; }
  .endcta .bt { display: inline-block; margin-top: 14px; background: #C2273F; color: #FFFFFF; font-size: 15px; font-weight: 700; padding: 13px 26px; }
  .endcta a:hover .bt { background: #A81F34; }
  .art blockquote { margin: 0 0 22px; padding: 16px 22px; border-left: 4px solid #C2273F;
                    background: #F6F6F6; }
  .art blockquote p { margin: 0; font-size: 15px; }
  .art a { color: #C2273F; text-decoration: underline; }
  .toc a { color: #111111; text-decoration: none; }
  .toc a:hover { color: #C2273F; }
  .flt { border: 1px solid #D4D4D4; background: #FFFFFF; font-family: inherit;
         font-size: 13px; font-weight: 700; padding: 9px 16px; color: #333333; }
  .colbox { padding: 26px 20px 48px; }
  .ix { font-family: "Noto Sans JP", "Noto Sans CJK JP", "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif; }
  .bar { font-size: 22px; line-height: 1.5; margin: 40px 0 18px; padding: 14px 18px; background: #333333; color: #FFFFFF; border-left: 8px solid #E8A33D; }
  .subbar { display: flex; align-items: center; gap: 10px; font-size: 16px; line-height: 1.5; padding: 11px 14px; background: #333333; color: #FFFFFF; }
  .g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 26px 22px; }
  .pick:hover span { opacity: .85; }
  .intro { display: block; margin-top: 20px; padding: 16px 20px; border: 1px solid var(--line, #D4D4D4); border-left: 6px solid #E8A33D; background: #FAFAFA; }
  .intro:hover { border-color: #111111; border-left-color: #E8A33D; }
  .blist { margin-top: 6px; }
  .blist li { position: relative; padding-left: 17px; margin-top: 8px; font-size: 15px; line-height: 1.6; }
  .blist li::before { content: ""; position: absolute; left: 3px; top: .62em; width: 7px; height: 7px; border-radius: 50%; background: #444444; }
  .dlist li { display: flex; gap: 14px; padding: 5px 0; font-size: 15px; line-height: 1.6; }
  .dlist .d { flex: 0 0 auto; color: #666666; }
  .blist a, .dlist a { color: #17547E; }
  .blist a:hover, .dlist a:hover { color: #C2273F; text-decoration: underline; }
  .none, .blist li.none { color: #8A8A8A; font-size: 14px; }
  .blist li.none::before { background: #BBBBBB; }
  @media (max-width: 640px) { .g2 { grid-template-columns: 1fr; } }
  .art, .art p, .art li, .art blockquote p { font-family: "Noto Sans JP", "Noto Sans CJK JP", "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif; font-feature-settings: normal; letter-spacing: 0; color: #333333; }
  .art p { font-size: 15px; line-height: 1.8; margin: 0 0 22px; font-weight: 400; }
  .art ul, .art ol { margin: 0 0 24px; }
  .art li { font-size: 15px; line-height: 1.75; margin-bottom: 4px; }
  .art h2 { font-size: 22px; line-height: 1.5; margin: 44px 0 20px; padding: 14px 18px; background: #333333; color: #FFFFFF; border-left: 8px solid #E8A33D; border-bottom: none; }
  .art h3 { font-size: 19px; line-height: 1.5; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 3px solid #E8A33D; }
  @media (max-width: 800px) {
    .artwrap { padding: 0 0 50px !important; }
    .colbox { padding: 24px 20px 40px; box-shadow: none !important; flex: 1 1 100% !important; }
    .sidebx { flex: 1 1 100% !important; }
  }
  @media (max-width: 860px) {
    header a[href="../"] { flex: 1 1 100% !important; min-width: 0 !important; }
    header a[href="../"] img { width: 100% !important; max-width: 400px; }
    header form { flex: 1 1 180px; }
  }
  .flt.on { background: #111111; color: #FFFFFF; border-color: #111111; }
"""


def page(title, desc, canon, css, head_html, foot_html, main, noindex=False, ld=""):
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-46Y18YF9H5"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-46Y18YF9H5');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">%s
<meta property="og:type" content="article">
<meta property="og:site_name" content="住宅営業登竜門">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../favicon.ico">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&amp;family=Zen+Kaku+Gothic+New:wght@400;500;700;900&amp;family=Noto+Sans+JP:wght@400;500;700&amp;display=swap">
%s<style>
%s
%s
</style>
</head>
<body>
%s
%s
%s
<script>
document.addEventListener("click", function (e) {
  var c = e.target.closest ? e.target.closest("td.m") : null;
  if (!c) { return; }
  var row = c.parentNode, was = c.className.indexOf("on-") > -1, i, cells = row.querySelectorAll("td.m");
  for (i = 0; i < cells.length; i++) { cells[i].className = "m"; }
  if (!was) { c.className = "m on-" + c.getAttribute("data-k"); }
});
</script>
</body>
</html>
""" % (html.escape(title), html.escape(desc), canon,
       '\n<meta name="robots" content="noindex">' if noindex else "",
       html.escape(title), html.escape(desc), canon,
       ld, css, EXTRA_CSS, head_html, main, foot_html)


# ---------- 5. 記事ページ ----------
def cta_block():
    return """<div style="max-width: 760px; margin: 28px auto 0;">
    <a href="../../toryumon-lp/" style="display: block; background: #FFFFFF; box-shadow: 0 0 0 1px #D4D4D4; border-left: 5px solid #C2273F; padding: 22px 26px;">
      <span class="en" style="display: block; font-size: 11px; font-weight: 600; letter-spacing: .22em; color: #C2273F;">VIDEO COURSE</span>
      <span style="display: block; margin-top: 8px; font-size: 19px; font-weight: 900; line-height: 1.6;">トップセールスのフレームワークを動画で学ぶ</span>
      <span style="display: block; margin-top: 8px; font-size: 13px; color: #5C5C5C;">動画講座「住宅営業登竜門」の詳細を見る ›</span>
    </a>
  </div>
"""



def toryumon_cta(a):
    """全記事共通: 記事の終わりに置く、住宅営業登竜門（動画講座）への案内"""
    href = "../../toryumon-lp/?utm_source=column&utm_medium=article&utm_campaign=" + a["slug"]
    return """          <aside class="endcta" aria-label="住宅営業登竜門のご案内">
            <p class="hd">住宅営業登竜門のご案内</p>
            <a class="bd" href="%s" style="display: block;">
              <img src="../assets/video-course.jpg" alt="住宅営業登竜門 動画講座">
              <span style="display: block; font-size: 19px; font-weight: 900; line-height: 1.6;">トップセールスのフレームワークを、動画で体系的に学べます。</span>
              <span style="display: block; margin-top: 8px; font-size: 14px; line-height: 1.85; color: #333333;">全16プログラム・100本以上。1本10〜15分で、要約と目次が付いています。スマホ・PC・タブレットで、倍速でも視聴できます。</span>
              <span class="bt">住宅営業登竜門の詳細を見る ›</span>
            </a>
          </aside>
""" % html.escape(href)


def article_page(a, arts, css, head_html, foot_html):
    # 原稿中の <!--after-cta--> より後ろは、記事末の登竜門バナーの後ろに表示する
    main_md, _, after_md = a["body"].partition("<!--after-cta-->")
    body, toc, faq = render_body(main_md)
    after_html = ""
    if after_md.strip():
        after_html = '          <div class="art aftercta" style="margin-top: 8px;">' + render_body(after_md)[0] + '</div>\n'
    url = SITE + "column/" + a["slug"] + ".html"

    hero = ""
    if a.get("hero"):
        hero = """          <figure style="margin: 26px 0 0;">
            <img src="%s" alt="%s" style="display: block; width: 100%%; height: auto;">
            <figcaption style="margin-top: 7px; font-size: 11px; color: #8A8A8A; text-align: right;">%s</figcaption>
          </figure>
""" % (html.escape(a["hero"]), html.escape(a.get("heroAlt", "")),
            html.escape(a.get("heroCredit", "")))

    toc_html = ""
    if len(toc) >= 2:
        items = "".join('            <li style="border-bottom: 1px solid #E2E2E2;">'
                        '<a href="#%s" style="display: block; padding: 11px 2px; '
                        'font-size: 14px; font-weight: 700; line-height: 1.6;">%s</a></li>\n'
                        % (i, html.escape(t)) for i, t in toc)
        toc_html = """          <nav class="toc" aria-label="このページの目次" style="margin: 34px 0 0; border: 1px solid #D4D4D4; padding: 22px 24px;">
            <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .2em; color: #8A8A8A;">CONTENTS</p>
            <p style="margin-top: 7px; font-size: 16px; font-weight: 900;">このページの目次</p>
            <ul style="margin-top: 12px;">
%s            </ul>
          </nav>
""" % items

    faq_html = ""
    if faq:
        items = "".join("""            <div style="border-bottom: 1px solid #D4D4D4; padding: 20px 4px;">
              <p style="font-size: 17px; font-weight: 900; line-height: 1.65;"><span style="color: #C2273F; margin-right: 10px;">Q</span>%s</p>
              <div style="margin-top: 10px; padding-left: 26px;">%s</div>
            </div>
""" % (html.escape(q), ans) for q, ans in faq)
        faq_html = """          <section style="margin-top: 48px;">
            <h2 style="font-size: 27px; line-height: 1.55; padding-bottom: 12px; border-bottom: 2px solid #111111;">よくある質問</h2>
            <div class="art" style="margin-top: 6px;">
%s            </div>
          </section>
""" % items

    rel = [x for x in arts
           if x["slug"] != a["slug"] and x["framework"] == a["framework"]][:3]
    rel_html = ""
    if rel:
        rel_html = """          <section style="margin-top: 48px;">
            <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .22em; color: #8A8A8A;">RELATED</p>
            <h2 style="margin-top: 8px; font-size: 22px; padding-bottom: 12px; border-bottom: 2px solid #111111;">同じフレームワークの記事</h2>
            <ul>
%s            </ul>
          </section>
""" % "".join(card_row(x) for x in rel)

    ld = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Article",
 "headline":%s,"description":%s,"url":%s,
 "datePublished":"%s","dateModified":"%s","inLanguage":"ja",
 "author":{"@type":"Person","name":"鶴田 槙人"},
 "publisher":{"@type":"Organization","name":"住宅営業登竜門"},
 "mainEntityOfPage":{"@type":"WebPage","@id":%s}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"name":"住宅営業登竜門","item":"%s"},
 {"@type":"ListItem","position":2,"name":"コラム","item":"%scolumn/"},
 {"@type":"ListItem","position":3,"name":%s}]}
</script>
""" % (jstr(a["title"]), jstr(a["description"]), jstr(url),
       a["published"], a["updated"], jstr(url), SITE, SITE, jstr(a["title"]))

    if faq:
        ld += """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[%s]}
</script>
""" % ",".join('{"@type":"Question","name":%s,"acceptedAnswer":{"@type":"Answer","text":%s}}'
               % (jstr(q), jstr(re.sub(r"<[^>]+>", "", ans).strip())) for q, ans in faq)

    draft = ""  # 下書き帯は表示しない（draft: true の記事は noindex のみ）

    main = """
<main class="artwrap" style="background: #2E2E2E; padding: 24px 16px 70px;">
  <div class="wrapx" style="max-width: 960px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-start;">
  <div class="colbox" style="flex: 1 1 0; min-width: 0; background: #FFFFFF; border-top: 6px solid #E8A33D;">
  <nav aria-label="パンくず" style="font-size: 12px; color: #5C5C5C;">
    <a href="../">住宅営業登竜門</a> ›
    <a href="./">コラム</a> ›
    <span>%s</span>
  </nav>

  <div>
    <article style="min-width: 0;">
      %s
      <div style="display: flex; flex-wrap: wrap; gap: 14px 20px; align-items: center;">
        %s
      </div>
      <h1 style="margin-top: 16px; background: #333333; color: #FFFFFF; border-left: 10px solid #E8A33D; padding: 22px 26px; font-size: 30px; line-height: 1.5; letter-spacing: -.01em;">%s</h1>
      <p style="margin-top: 18px; font-size: 16px; line-height: 2; color: #4A4A4A;">%s</p>
      <p class="en" style="margin-top: 16px; padding-bottom: 20px; border-bottom: 1px solid #D4D4D4; font-size: 12px; color: #8A8A8A;">対象 %s　読了 %d分　公開 %s%s</p>
%s%s
      <div class="art" style="margin-top: 34px;">
%s
      </div>
%s%s
      <section style="margin-top: 48px; border-top: 2px solid #111111; padding-top: 28px; display: flex; flex-wrap: wrap; gap: 26px; align-items: flex-start;">
        <div style="flex: 1 1 320px; min-width: 0;">
          <p class="en" style="font-size: 11px; font-weight: 600; letter-spacing: .2em; color: #8A8A8A;">AUTHOR</p>
          <p style="margin-top: 8px; font-size: 20px; font-weight: 900;">鶴田 槙人<span style="font-size: 13px; font-weight: 400; color: #5C5C5C; margin-left: 12px;">MARKEY CONSULTING 代表</span></p>
          <p style="margin-top: 12px; font-size: 14px; line-height: 1.95; color: #333333;">住宅会社の営業力強化・育成の仕組み構築を専門とするコンサルタント。年商10億から1,300億規模まで、新築部門の立ち上げ、業績回復、販売戦略構築を支援。</p>
        </div>
      </section>
    </article>
  </div>
  </div>
%s
  </div>
</main>
""" % (html.escape(a["title"]), draft,
       chip(a["framework"], FW_COLOR[a["framework"]]),
       html.escape(a["title"]), html.escape(a["description"]),
       html.escape(a["audience"]), a["min"], a["published"].replace("-", "."),
       ("　更新 " + a["updated"].replace("-", ".")) if a["updated"] != a["published"] else "",
       hero, toc_html, body, faq_html + toryumon_cta(a) + after_html, rel_html,
       '<div class="sidebx" style="flex: 0 0 290px; min-width: 0; background: #FFFFFF; padding: 16px 14px; border-top: 6px solid #E8A33D;">' + rail(arts, a["slug"]) + '</div>')

    return page(a["title"] + "｜住宅営業登竜門", a["description"], url,
                css, head_html, foot_html, main, noindex=a["draft"], ld=ld)


def jstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


# ---------- 6. 一覧ページ ----------
def index_page(arts, css, head_html, foot_html):
    url = SITE + "column/"
    E = html.escape

    def badge(a):
        return ('<span style="font-size: 11px; font-weight: 700; color: #FFFFFF; background: #8A8A8A; '
                'padding: 2px 7px; margin-right: 7px; vertical-align: 1px;">下書き</span>') if a["draft"] else ""

    # おすすめ記事: 原稿に pickup: true があればそれ、無ければ新しい順に4本
    picks = [a for a in arts if str(a.get("pickup", "")).lower() in ("true", "yes", "1")]
    if not picks:
        picks = arts[:4]
    cards = []
    for a in picks[:6]:
        if a.get("hero"):
            visual = ('<img src="%s" alt="%s" style="display: block; width: 100%%; aspect-ratio: 4 / 3; object-fit: cover;">'
                      % (E(a["hero"]), E(a.get("heroAlt", a["title"]))))
        else:
            visual = ('<span class="grad" style="display: flex; align-items: center; aspect-ratio: 4 / 3; padding: 20px 22px; '
                      'border-left: 6px solid %s; color: #FFFFFF; font-size: 19px; font-weight: 900; line-height: 1.55;">%s</span>'
                      % (FW_COLOR[a["framework"]] if FW_COLOR[a["framework"]] != "#111111" else "#E8A33D", E(a["title"])))
        cards.append(
            '        <a href="%s.html" class="pick" style="display: block;">\n'
            '          <span style="display: block; text-align: center; font-size: 14px; line-height: 1.6; color: #444444; margin-bottom: 7px;">%s%s</span>\n'
            '          %s\n'
            '        </a>\n' % (a["slug"], badge(a), E(a["framework"]), visual))
    pick_html = "".join(cards) if cards else '        <p class="none">記事が増えるとここに並びます。</p>\n'

    # はじめに読む: 5つの成約フレームワークの総論
    intro = [a for a in arts if a["framework"] == FW_INTRO]
    intro_html = ""
    if intro:
        a = intro[0]
        intro_html = (
            '    <a href="%s.html" class="intro">\n'
            '      <span class="en" style="display: block; font-size: 11px; font-weight: 600; letter-spacing: .22em; color: #C2273F;">START HERE</span>\n'
            '      <span style="display: block; margin-top: 6px; font-size: 18px; font-weight: 900; line-height: 1.55;">%s%s</span>\n'
            '      <span style="display: block; margin-top: 6px; font-size: 13px; color: #666666;">コラムは、この5つの要素に沿って分けています。最初にこの記事を読むと、全体がつかめます。 ›</span>\n'
            '    </a>\n' % (a["slug"], badge(a), E(a["title"])))

    # 最新記事・更新記事: 日付つきの一覧
    def stamp(a):
        return max(a["published"], a["updated"])
    latest = sorted(arts, key=stamp, reverse=True)[:20]
    rows = "".join(
        '        <li><span class="d">%s</span><a href="%s.html">%s%s</a></li>\n'
        % (stamp(a)[5:].replace("-", "/"), a["slug"], badge(a), E(a["title"])) for a in latest)
    latest_html = rows if rows else '        <li class="none">記事はまだありません。</li>\n'

    # 目的別・フレームワーク別のボックス
    def boxes(key, colors):
        out = []
        for name, color in colors.items():
            if name == FW_INTRO:
                continue
            items = [a for a in arts if a[key] == name]
            lis = "".join('              <li><a href="%s.html">%s%s</a></li>\n'
                          % (a["slug"], badge(a), E(a["title"])) for a in items[:8])
            if not lis:
                lis = '              <li class="none">準備中</li>\n'
            out.append(
                '          <div id="%s">\n'
                '            <h3 class="subbar"><span style="width: 10px; height: 10px; background: %s; flex-shrink: 0; box-shadow: 0 0 0 1px rgba(255,255,255,.6);"></span>%s</h3>\n'
                '            <ul class="blist">\n%s            </ul>\n'
                '          </div>\n' % (FW_KEY[name], color, E(name), lis))
        return "".join(out)

    main = """
<main class="artwrap" style="background: #2E2E2E; padding: 24px 16px 70px;">
  <div class="wrapx" style="max-width: 960px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-start;">
  <div class="colbox ix" style="flex: 1 1 0; min-width: 0; background: #FFFFFF; border-top: 6px solid #E8A33D;">
    <nav aria-label="パンくず" style="font-size: 12px; color: #5C5C5C;">
      <a href="../">住宅営業登竜門</a> › <span>コラム</span>
    </nav>

    <h1 class="bar" style="margin-top: 16px; font-size: 26px;">住宅営業登竜門コラム</h1>
    <p style="font-size: 15px; line-height: 1.75; color: #333333;">受注を上げるための型を、つまずく場所ごとに解説しています。全文無料・登録不要です。</p>
""" + intro_html + """

    <section>
      <h2 class="bar">おすすめ記事</h2>
      <div class="g2">
""" + pick_html + """      </div>
    </section>

    <section>
      <h2 class="bar">最新記事・更新記事</h2>
      <ul class="dlist">
""" + latest_html + """      </ul>
    </section>

    <section>
      <h2 class="bar">5つの成約フレームワークから探す</h2>
      <div class="g2">
""" + boxes("framework", FW_COLOR) + """      </div>
    </section>
  </div>
""" + '<div class="sidebx" style="flex: 0 0 290px; min-width: 0; background: #FFFFFF; padding: 16px 14px; border-top: 6px solid #E8A33D;">' + rail(arts) + """</div>
  </div>
</main>
"""

    return page("コラム｜住宅営業登竜門",
                "住宅営業の受注を上げるためのコラム。初回接客からクロージング、追客、育成まで、つまずく場所ごとに解説しています。",
                url, css, head_html, foot_html, main)


# ---------- 7. 実行 ----------
def main():
    css, head_html, foot_html = chrome()
    if not os.path.isdir(SRC):
        die("原稿フォルダがありません: " + SRC)

    files = sorted(f for f in os.listdir(SRC) if f.endswith(".md"))
    arts = []
    for f in files:
        a = parse(os.path.join(SRC, f))
        a["min"] = minutes(a["body"])
        arts.append(a)
    arts.sort(key=lambda a: a["published"], reverse=True)

    for a in arts:
        write(os.path.join(COL, a["slug"] + ".html"),
              article_page(a, arts, css, head_html, foot_html))
        print("  記事:", a["slug"] + ".html",
              "（下書き）" if a["draft"] else "", a["min"], "分")

    write(os.path.join(COL, "index.html"),
          index_page(arts, css, head_html, foot_html))
    print("  一覧: column/index.html　記事", len(arts), "本")


if __name__ == "__main__":
    main()
