# ブラウザ自動操作で外部サービスの画面が真っ白なときは、自動化を疑う前にサービスの status ページと API 応答時間を curl で確認する
- type: lesson
- created: 2026-09-15
- tags: [browser-automation, playwright, chrome-extension, osf, outage, troubleshooting]

## 概要
Playwright MCP や Claude in Chrome 拡張で SPA(単一ページアプリ)を操作しようとして
ページが空(`innerText` 空・スナップショット空)のとき、原因はセッションや自動化ツールではなく
**サービス側の API 障害**であることがある。数分ツール側を疑う前に、シェルから
①フロント(`https://site/`)と ②API(`https://api.site/`)の HTTP ステータス・応答時間、
③公式 status ページ(statuspage.io 系なら `/api/v2/status.json`)を `curl` で見る。
API が「200 だが 15 秒超」+ status が `minor`/`major` なら待つしかない。

## 背景・発見経緯
2026-09-15、OSF 事前登録の代行のため Playwright MCP で `osf.io/dashboard` に到達したが真っ白。
`wait_for` を延ばしても変わらず、コンソールに `api.osf.io/v2/` への fetch が CORS/`ERR_FAILED` で
落ちるエラーのみ。`curl` で `osf.io` は 0.2 秒、`api.osf.io/v2/` は 15 秒超、
`status.cos.io/api/v2/status.json` は `"indicator":"minor","description":"Minor Service Outage"`
→ OSF 側の障害と確定し、ユーザーに「拡張接続後も復旧待ちが必要」と正確に報告できた。

## 詳細
- 切り分けの順番(所要 1 分):
  ```
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" --max-time 15 https://osf.io/
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" --max-time 20 https://api.osf.io/v2/
  curl -s --max-time 15 https://status.cos.io/api/v2/status.json | head -c 400
  ```
- ブラウザ内の `fetch('https://api.osf.io/...')` は CORS で落ちるので API 疎通確認はブラウザ evaluate ではなくシェルで行う。
- Claude in Chrome 拡張はユーザーが Chrome 側で接続するまで `list_connected_browsers` が `[]` を返す。
  接続はユーザー操作が必要なので、待つ間に上記の疎通確認を済ませておく。
- 登録・投稿など**取消不可の送信**を代行するときは、最終ボタン押下の直前にユーザー確認を挟む。
- Playwright MCP は `.playwright-mcp/`(スナップショット yml・スクリーンショット png・コンソールログ)を
  プロジェクトルート直下に作る。git に混ぜないよう `.gitignore` に追加する。

## 適用場面
- OSF・GitHub・学会投稿システムなど外部 Web サービスをブラウザ自動操作で代行するとき。
- SPA が描画されない/無限ロード/API エラーのみ、という症状に遭遇したとき。

## 関連
- Experimental_record/20260915.md
- [[osf-preregistration-for-non-clinical-reader-study]]
- [[stop-background-verification-server-to-free-port]]

## 追記 (2026-09-15)
- 参照: Experimental_record/20260915.md(追記19)
- status ページの `status.json` が `minor` でも内容は分からない。**`/api/v2/incidents/unresolved.json`** を叩くと
  インシデント名・状態(`investigating`/`identified`/`monitoring`)・発生時刻が取れ、「前日から続く障害」と分かれば
  即座に「後日再試行」の判断ができる。
  ```
  curl -s https://status.cos.io/api/v2/incidents/unresolved.json | python -c "import sys,json; [print(i['name'],i['status'],i['updated_at']) for i in json.load(sys.stdin)['incidents']]"
  ```
- Claude in Chrome 拡張の `read_network_requests` は**初回呼び出し以降のリクエストしか記録しない**。しかも本件では
  リロード後も `api.osf.io` へのリクエストが記録に現れず(SPA 内部の fetch が捕捉されない)、API 疎通の判定には使えない。
  API の生死はシェルの `curl` で判定する。
- ユーザーが拡張を接続しても、サービス障害が続いていれば同じ症状(静的アセットは 200、画面はスピナーのみ)になる。
  拡張接続の成否とサービス障害は別問題として報告し、再試行のタイミング(半日〜1日後)はユーザーに委ねる。

## 追記 (2026-09-15, 2回目)
- 参照: Experimental_record/20260915.md(追記20)
- **status ページの「All Systems Operational」(`indicator: none`)は API が実用に戻ったことを意味しない。**
  本件では復旧表示に戻った後も `api.osf.io/v2/` が `60 秒タイムアウト ×2 → 200 (21.5 秒)` で、
  SPA の `myprojects` は 40 秒以上スピナーのままだった。インシデント解決 = ステータス更新であり、
  実効の応答時間はしばらく劣化したまま(あるいは特定地域からの経路だけ遅い)ことがある。
- 着手判定は status ページではなく**応答時間の閾値で機械的に決める**。SPA は 1 画面で API を多数呼ぶので
  「1 回でも 200 が返る」では不十分で、複数回連続で速いことを要求する:
  ```
  for i in 1 2 3; do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" --max-time 60 https://api.osf.io/v2/; done
  # 3 回連続 200 かつ 3 秒以内 → 着手。未満なら再度見送り(ユーザーへ計測表で報告)
  ```
- ブラウザ内で API 待ちのタブに対して `javascript_tool`/`evaluate` を投げると、**CDP `Runtime.evaluate` 自体が 45 秒でタイムアウト**
  する(レンダラが応答しない)。API の生死判定はやはりシェルの `curl` で行い、ブラウザ側の JS 実行は使わない。
- 見送るときは「復旧表示だが実測は遅い」ことを計測表(試行 × 結果)で示し、次回の着手条件を数値で残しておくと
  ユーザーも自分で判断できる。

## 追記 (2026-09-16)
- 参照: Experimental_record/20260916.md
- **status ページの表示はどちらの方向にも実用性の指標にならない。** 前日は「All Systems Operational」でも API が 20〜60 秒だったが、
  翌朝は `indicator: maintenance`(Service Under Maintenance)表示のまま `api.osf.io/v2/` が **0.38s / 1.29s / 0.24s** で実用可だった。
  着手判定は前回明文化した「`curl` 3 回連続 200 かつ 3 秒以内」だけで機械的に決めてよい(status は参考情報)。
- **「サービスが生きているか」と「ログイン済みか」は別々に確認する。** 障害中はスピナーで止まるためログイン状態が判定できないが、
  復旧後に開くと `osf.io/myprojects/` → `osf.io/`(トップ)→ `/dashboard` → `accounts.osf.io/login` へ落ちることがある
  (セッション失効)。ブラウザ代行ではパスワード入力ができないので、サインイン画面に到達したら
  「Chrome 上で自分でログイン → 完了したら合図」をユーザーに依頼し、そこから再開する。
- Claude in Chrome 拡張の `browser_batch` 内の `screenshot` が、ナビゲーション直後にドメインが変わった
  (`osf.io` → `accounts.osf.io`)タイミングで「Permission denied for this action on this domain」で失敗した。
  単発の `computer.screenshot` は同じタブで成功するので、batch 内で失敗したら単発で再試行する。

## 追記 (2026-09-16, 2回目)
- 参照: Experimental_record/20260916.md
- **ユーザーの「ログインした」を鵜呑みにせず、対象サービスの認証必須ページ(OSF なら `osf.io/dashboard`)を開いて描画されるかで判定する。**
  本件ではユーザーは ORCID 側の認証を完了していたが、OSF は **ORCID 初回連携時にメール確認**を要求するため
  (`osf.io/external-login/email` に留まり、`/dashboard` を開くと「Sign In With ORCID」フォームに戻る)、OSF セッションは未確立だった。
- 外部 ID 連携(ORCID・機関 SSO)はメール確認や同意画面が挟まって代行が中断しやすい。既存アカウントがあるなら
  **メール+パスワードの直接ログイン**を先に案内する方が早い。規約同意・パスワード入力・確認メールのクリックはユーザー操作に委ねる。
- ドメイン遷移を伴わない `browser_batch` 内の `screenshot` は成功した。前回の「Permission denied」は `osf.io` → `accounts.osf.io` の
  遷移直後に限った事象で、batch で失敗したら単発 `computer.screenshot` で再試行、という運用で十分。

## 追記 (2026-09-16, 3回目)
- 参照: Experimental_record/20260916.md
- ログイン確立後の長いフォーム入力(OSF Preregistration 8 ステップ)は、**`find`(自然言語で欄を指定)→ `ref_*` を取得 →
  `browser_batch` で `left_click(ref)` + `type(text)` を欄ごとに連結 → 最後に `wait` + `screenshot`** の 1 往復/ページで進むと速い。
  タグのように Enter で確定する入力は `type` と `key: Return` を交互に並べる。ページ末尾のテキストは `get_page_text` で
  ✓(保存済み)表示を確認してから Next を押す。
- **ファイル添付は `mcp__claude-in-chrome__file_upload` にローカル絶対パスを渡すだけで動く**(`<input type=file>` の ref を指定)。
  OS のファイル選択ダイアログは開かないのでユーザー操作は不要。添付前にパスの実在を確認しておく。
- 取消不可の最終送信(OSF なら Register → Embargo 設定 → Submit)は、**ダイアログを開いた状態で止めて要約表を提示**し、
  ユーザーの Yes を待つ。タブは閉じずに残す(閉じるとダイアログの入力=Embargo 日付が失われる)。

## 追記 (2026-09-16, 4回目)
- 参照: Experimental_record/20260916.md
- **座標クリック(`left_click coordinate`)はブラウザ窓のサイズが変わると空振りする。** 取消不可の最終送信(OSF の Submit)で
  1 回目の座標クリックが空振りし、screenshot が 512×218(coordinate frame 732×311)と極端に小さかったことで窓の縮小に気づいた。
  対処: `javascript_exec` で `innerWidth/innerHeight`・ダイアログの有無・フォーム値(Embargo 日付)を確認 → `find` で
  ボタンの `ref` を取得 → `resize_window`(1600×900)で既知サイズへ戻す → `left_click ref` で押す。
  重要なボタンは**座標ではなく `ref` で押す**、押す直前に**窓サイズを固定する**、の 2 点で再発防止できる。
- 空振り後に再クリックする前は、**二重送信になっていないこと**(URL がまだドラフト `registries/drafts/<id>/review` のまま、
  ダイアログの入力値が残っている)を確認してから押す。今回は登録が 1 件だけで済んだ。
- 送信完了の判定は screenshot ではなく **URL の変化(`/registries/drafts/<id>` → `/<id>/overview`)と `get_page_text` の状態文言**
  (Pending Embargo Approval)で行う。cookie バナーが被る場合は先に閉じる。
