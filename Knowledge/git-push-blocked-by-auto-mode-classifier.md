# `git push` が auto モードの分類器でブロックされたらユーザーに `! git push` を委ねる
- type: technique
- created: 2026-09-15
- tags: [git, claude-code, workflow, permissions]

## 概要
Claude Code の auto(自動許可)モードでは、`git push` のような外部公開操作が
「Blocked by classifier」で拒否されることがある。再試行やツールの言い換えで回避しようとせず、
ユーザーがプロンプトに **`! git push origin main`** と打てば同セッション内で実行され、
結果(`4716de3..a5951a0 main -> main` 等)がそのまま会話に返るので、それを案内するのが最短。

## 背景・発見経緯
2026-09-15、コミット `a5951a0` の後にユーザーから「push もしておいて」と依頼。
`git remote -v && git push origin main` を実行したところ分類器に拒否された
(commit 自体は同じセッションで通っている=ブロック対象は push のみ)。
ユーザーへ `! git push origin main` を提示 → ユーザー実行で push 成功、GCM の資格情報が残って
いたため再サインインも不要だった。

## 詳細
- 案内時に添えると親切な情報: リモート名/URL(private か)、ブランチ、push されるコミット範囲、
  認証(GCM が残っていれば再サインイン不要)。ユーザーが安心して打てる。
- 拒否を別ツール(Python の subprocess 等)で迂回しない。分類器は「外部公開」を止めているので、
  迂回はユーザーの意図確認を飛ばすことになる。
- push 前のデータ衛生検証(患者ファイル名・`.pth`・認証情報の混入チェック)は分類器とは別に
  こちらで済ませておく([[medical-repo-pre-push-data-hygiene]])。

## 適用場面
- auto モードで commit まで済んだ後、push だけが拒否されたとき。
- その他「外部へ公開・送信する」操作(release 作成、外部 API への POST 等)が分類器で止まった場合も同様に、
  ユーザー実行に委ねる。

## 関連
- Experimental_record/20260915.md
- [[medical-repo-pre-push-data-hygiene]]
