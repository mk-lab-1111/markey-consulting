# 作業ルール

## ブランチとデプロイ
- このリポジトリの本番公開ブランチは **main**（GitHub Pages: main / root、独自ドメイン markey-consulting.com）。CNAME は main に存在する。
- **push は原則すべて main に対して行う。**
- master ブランチは過去の経緯で残っているが、**明示的な指示がない限り master には push しない・master に切り替えない**。
- ユーザーから「master にpushして」等の明示指示があった場合のみ master を使う。
- push する前に、必ず現在のブランチ（git branch --show-current）を確認し、main であることを確かめてから push する。
- push 実行後は、push 先が origin/main であることを結果で報告する。

## リポジトリ構造と公開ファイル
- ルート直下は markey-consulting 本体サイト（markey-consulting.com）。
- `toryumon/` フォルダは「住宅営業登竜門」のサイト（markey-consulting.com/toryumon/ として公開）。
- 登竜門のLPを直す場合の対象は toryumon/index.html, toryumon/corporate.html など toryumon/ 内のファイル。
- ルート直下にも corporate.html などの同名ファイルがあるため、編集対象は必ずユーザーに確認する。

## 確認に関する注意
- master と main のファイル差分を扱うとき、git diff の報告だけで「どちらにある/ない」を断定しない。
  過去に diff の読み取りが実態と逆だった実例がある。重要ファイル（CNAME 等）は GitHub 上で実物を確認する。
