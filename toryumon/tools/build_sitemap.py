#!/usr/bin/env python3
"""sitemap.xml と robots.txt を作る。

使い方:  python3 tools/build_sitemap.py <リポジトリのルート>
  - ルート直下の公開ページ + 登竜門ポータル + LP + コラム記事（draft: true は除く）を載せる
  - 出力: <ルート>/sitemap.xml, <ルート>/robots.txt
"""
import datetime
import re
import sys
from pathlib import Path

SITE = "https://markey-consulting.com/"
ROOT_PAGES = ["", "cases.html", "corporate.html", "training.html", "events.html",
              "event_01.html", "event_02.html", "reports.html", "privacy.html",
              "toryumon-lp/", "sales-academy/", "toryumon/", "toryumon/corporate.html"]


def front(md):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, re.S)
    d = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def main(root):
    root = Path(root)
    today = datetime.date.today().isoformat()
    urls = [(SITE + p, today) for p in ROOT_PAGES]
    arts = []
    for f in sorted((root / "toryumon" / "column" / "_src").glob("*.md")):
        d = front(f.read_text(encoding="utf-8"))
        if d.get("draft", "").lower() == "true":
            continue
        arts.append((SITE + "toryumon/column/" + f.stem + ".html", d.get("updated") or d.get("published") or today))
    if arts:
        urls.append((SITE + "toryumon/column/", today))
        urls += arts
    body = "".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % u for u in urls)
    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n",
        encoding="utf-8")
    (root / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: " + SITE + "sitemap.xml\n", encoding="utf-8")
    print("sitemap.xml:", len(urls), "URL（うちコラム記事", len(arts), "本）")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
