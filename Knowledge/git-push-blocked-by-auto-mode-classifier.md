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

## 追記 (2026-09-15)
- 参照: Experimental_record/20260915.md
- 同日2回目のコミット `e131aff` では、分類器のブロックを待たずにコミット完了報告と同時に
  `! git push origin main` を案内 → ユーザー実行で `a5951a0..e131aff` push 成功。
  一度ブロックが確認されたセッションでは、以後の push は最初からユーザー実行に委ねてよい
  (再試行して再ブロックされる往復を省ける)。

## 追記 (2026-09-15, 3回目)
- 参照: Experimental_record/20260915.md
- 同日3回目 `b7ded06` も同じ運用(コミット完了報告と同時に `! git push origin main` を案内 → ユーザー実行で
  `e131aff..b7ded06` push 成功)。3連続で安定して機能したため、このプロジェクトでは
  「Claude はコミットまで、push はユーザーが `! git push origin main`」を標準手順として固定する。

## 追記 (2026-09-15, 4回目: `!` は行頭必須)
- 参照: Experimental_record/20260915.md
- 4回目 `47cbd7d` で、ユーザーの入力が **` ! git push origin main`(先頭に半角スペース)** だったため
  bash モードとして解釈されず通常メッセージとして届き、コマンドは実行されなかった。
  「行頭を `!` から始めて再入力」を案内 → 再入力で push 成功(`3b9db4a..47cbd7d`)。
- 案内文には **「行頭に `!`、前にスペースを入れない」** を一言添えると往復が1回減る。
  また hook 側で push の成否を裏取りするには `git status -sb`(ahead の有無)や
  `git reflog show origin/main --date=iso`(`update by push` の時刻)が使える。
