# 検証用バックグラウンドサーバーは終了後に必ず停止しポートを解放する
- type: lesson
- created: 2026-07-13
- tags: [windows, uvicorn, port, workflow, verification]

## 教訓
Playwright/実API 検証のために立てた開発サーバー(uvicorn 等)をバックグラウンドで
起動したまま放置すると、そのプロセスがポート(例: 8000)を掴み続ける。後でユーザー自身が
同じポートで起動しようとすると **`[WinError 10048] bind on address ('127.0.0.1', 8000)`**
(=ポート使用中)で startup 直後に落ちる。医用画像サーバーでは公開リスクの面でも放置は不可。

## いつ効くか / 背景
- 本プロジェクトでは webapp の変更を実サーバー + Playwright で end-to-end 検証する運用が常態。
  検証のたびにバックグラウンド uvicorn を立てるため、**停止し忘れると次の起動と競合**する。
- フロントのみの変更は no-cache ヘッダで稼働中サーバーに即反映されるが、backend 変更時は
  再起動が要る=検証用サーバーを立て直す機会が多く、余計に停止漏れが起きやすい。

## 対処
- 検証が終わったら必ず停止する:
  `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*8000*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`
- 10048 が出たときの特定と停止:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess` → `Stop-Process -Id <PID> -Force`
- 停止確認は `curl http://localhost:8000/api/config`(無応答=空き)で行う。

## 教訓
- **立てたサーバーは自分で片付ける**。検証タスクの締めに「サーバー停止」を1手として組み込む。

## 関連リンク
- Experimental_record/20260713.md
