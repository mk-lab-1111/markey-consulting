/**
 * 住宅市場レポート：ドライブの「02_承認済み」→ サイトへ送る（Google Apps Script）
 *
 * 動き
 *   1. 「02_承認済み」フォルダにある原稿（YYYY-MM-DD.md、またはGoogleドキュメント）を見つける
 *   2. GitHub（mk-lab-1111/markey-consulting）の toryumon/reports/_src/ に送る
 *   3. 送れたら、ファイルを「03_公開済み」へ移す
 *   → GitHub側の自動処理が、ページ・一覧・サイトマップを作って公開する
 *
 * 初回の設定（ボスが1回だけ）
 *   - このスクリプトを、Novi Drive の持ち主（novi.ai.ceo@gmail.com）で作る
 *   - 「プロジェクトの設定」→「スクリプト プロパティ」に GITHUB_TOKEN を登録する
 *     （GitHubの Fine-grained token。対象は markey-consulting だけ、Contents: Read and write）
 *   - 関数 publishApproved を1回手動で実行して許可を出す
 *   - 「トリガー」で publishApproved を「時間主導型・30分ごと」に設定する
 */
var REPO = 'mk-lab-1111/markey-consulting';
var BRANCH = 'main';
var DEST = 'toryumon/reports/_src/';
var APPROVED_ID = '1d98-PrVFwPQklMaMJaO1otENMieem07N';   // 住宅市場レポート/02_承認済み
var PUBLISHED_ID = '1IOcwuTraXY75pDHQUxAiuoVdrAY3PZZ9';  // 住宅市場レポート/03_公開済み

function publishApproved() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) { throw new Error('スクリプト プロパティに GITHUB_TOKEN がありません'); }
  var approved = DriveApp.getFolderById(APPROVED_ID);
  var published = DriveApp.getFolderById(PUBLISHED_ID);
  var files = approved.getFiles();
  while (files.hasNext()) {
    var f = files.next();
    var name = f.getName().replace(/\.(md|txt)$/i, '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(name)) {
      Logger.log('飛ばしました（ファイル名が YYYY-MM-DD.md ではない）: ' + f.getName());
      continue;
    }
    var text = (f.getMimeType() === MimeType.GOOGLE_DOCS)
      ? DocumentApp.openById(f.getId()).getBody().getText()
      : f.getBlob().getDataAsString('UTF-8');
    text = text.replace(/^﻿/, '').replace(/\r\n/g, '\n');
    if (!/^---\n(?:[\s\S]*?\n)?title:/.test(text)) {
      Logger.log('飛ばしました（先頭の設定がない）: ' + f.getName());
      continue;
    }
    putToGitHub_(token, DEST + name + '.md', text, '住宅市場レポート ' + name + ' を承認・公開');
    f.moveTo(published);
    Logger.log('送りました: ' + name);
  }
}

function putToGitHub_(token, path, text, message) {
  var url = 'https://api.github.com/repos/' + REPO + '/contents/' + encodeURI(path);
  var headers = { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' };
  var sha = null;
  var cur = UrlFetchApp.fetch(url + '?ref=' + BRANCH, { headers: headers, muteHttpExceptions: true });
  if (cur.getResponseCode() === 200) { sha = JSON.parse(cur.getContentText()).sha; }  // 同じ日付の原稿は上書き
  var body = {
    message: message,
    content: Utilities.base64Encode(Utilities.newBlob(text, 'text/plain', 'x').getBytes()),
    branch: BRANCH
  };
  if (sha) { body.sha = sha; }
  var res = UrlFetchApp.fetch(url, {
    method: 'put', headers: headers, contentType: 'application/json',
    payload: JSON.stringify(body), muteHttpExceptions: true
  });
  if (res.getResponseCode() >= 300) {
    throw new Error('GitHubへの送信に失敗: ' + res.getResponseCode() + ' ' + res.getContentText().slice(0, 300));
  }
}
