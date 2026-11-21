# -*- coding: utf-8 -*-
"""
住宅市場レポートの原稿を、公開前に機械で点検する。

  python3 tools/check_report.py reports/_src/2026-11-24.md [...]

止める（エラー）：形が崩れていて、ページが正しく作れないもの
知らせる（注意）：人が確認したほうがよいもの（公開は止めない）
"""
import io, os, re, sys, datetime

REQUIRED = ["Executive Summary", "主なニュースTOPIC", "一次情報・公的参照元URL", "今週のインプリケーション"]


def week_label(d):
    return "%d月第%d週" % (d.month, (d.day + 6) // 7)


def check(path):
    errs, warns = [], []
    name = os.path.basename(path)
    raw = io.open(path, encoding="utf-8").read()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", name):
        errs.append("ファイル名が YYYY-MM-DD.md ではありません")
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        return ["先頭の --- で囲んだ設定（title, published, description）がありません"], warns
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = m.group(2)
    for k in ("title", "published", "description"):
        if not meta.get(k):
            errs.append("設定に %s がありません" % k)
    try:
        d = datetime.date.fromisoformat(meta.get("published", ""))
        if name[:10] != meta["published"]:
            errs.append("ファイル名の日付と published が違います")
        wm = re.match(r"^【(\d+月第\d週)】", meta.get("title", ""))
        if not wm:
            errs.append("タイトルが「【M月第N週】」で始まっていません")
        elif wm.group(1) != week_label(d):
            warns.append("タイトルの週（%s）が公開日から計算した週（%s）と違います" % (wm.group(1), week_label(d)))
        if (d - datetime.date.today()).days > 14:
            warns.append("公開日が2週間以上先です")
    except ValueError:
        errs.append("published の日付の形が YYYY-MM-DD ではありません")

    for h in REQUIRED:
        if not re.search(r"^##\s.*" + re.escape(h), body, re.M):
            errs.append("見出し「%s」がありません" % h)
    if len(re.findall(r"^###\s*[①②③④⑤]", body, re.M)) < 2:
        warns.append("主なニュースTOPIC（①②③）が2本未満です")
    src = re.search(r"##\s*一次情報・公的参照元URL[^\n]*\n(.*?)(?=\n## |\Z)", body, re.S)
    urls = re.findall(r"https?://\S+", src.group(1)) if src else []
    if len(urls) < 2:
        warns.append("参照元URLが2件未満です")
    if "|---" in body or re.search(r"^\|.*\|\s*$", body, re.M):
        warns.append("表（| 区切り）が入っています。受注速報などは文章で書くルールです")
    n = len(re.sub(r"\s|[#*\-]", "", body))
    if n < 1500:
        warns.append("本文が短すぎます（%d字）" % n)
    if re.search(r"(今週のテーマ|SELECTED_THEME|TITLE:|SECTION:)", body):
        warns.append("生成時の作業用の文字列が残っています")
    return errs, warns


def main(paths):
    bad = False
    for p in paths:
        errs, warns = check(p)
        print("■", os.path.basename(p))
        for e in errs:
            print("  エラー:", e)
        for w in warns:
            print("  注意:", w)
        if not errs and not warns:
            print("  OK")
        bad = bad or bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
