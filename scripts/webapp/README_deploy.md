# HITL アノテーション実験 — 配布・収集 運用手順（管理者用）

3人のアノテータに遠隔で作業してもらい、結果を自PCに集約するための手順です。
構成は **「自PCで1台のサーバを動かし、Cloudflare Tunnel で公開、共有パスワードで保護」**（案A）。

```
3人のブラウザ ──HTTPS──> xxxxx.trycloudflare.com ──tunnel──> 自PC localhost:8000
        ↑ Basic認証(共有PW)                                  ↑ 事前計算提案/画像/結果保存
```

- アノテータはブラウザでURLを開くだけ（インストール不要）
- 提案の lookup・採点・記録はすべて自PCで実行（GPU 不要）→ 結果は `outputs/results/` に全員分集約
- n・seed・モデル名・条件はクライアントに送られない（盲検はサーバが担保）。提案は事前計算のため応答時間が条件で変わらない

---

## 0. 前提（初回のみ確認）

- `cloudflared` インストール済み（確認: `cloudflared --version`）
  - 未導入なら: `winget install Cloudflare.cloudflared`
- システム Python に `fastapi` / `uvicorn` / `opencv-python` / `numpy` が入っていること（torch 不要）
- `scripts/webapp/config/experiment.json` と `outputs/proposals/proposals.json` が存在すること（起動時に整合性を検証）

---

## 1. 起動（毎回）

1. `scripts/webapp/run_server.ps1` を開き、先頭の `$Pass` を **本番用パスワード**に書き換える
   （3人に配る値。例: ある程度長い英数字。第三者が推測できないもの）
2. PowerShell で実行:
   ```powershell
   cd C:\Users\CorneAI\Eyelid_HITL_experiment\scripts\webapp
   .\run_server.ps1
   ```
3. 別ウィンドウで API サーバ（uvicorn）が立ち上がり、**このウィンドウに公開URLが表示される**:
   ```
   https://xxxxxxxx.trycloudflare.com
   ```
4. **各人専用のリンク**を生成し、本人にだけ個別に送る（＋ユーザ名 `annotator` / パスワード、配布資料 `annotator_guide.md`）:
   ```powershell
   python scripts\make_annotator_links.py --base-url https://xxxxxxxx.trycloudflare.com
   ```
   リンクは `https://…/?t=<個人コード>`。サーバがコードからアノテータを決めるため、**他人のIDを選ぶ操作自体が存在しない**
   （ID選択プルダウンは機能テスト用 `test` のみ）。コードの打ち間違い・無効リンクは「このリンクは無効です」で止まる。
   個人コードは `scripts/webapp/config/annotator_tokens.json`（git管理外）に保存され、再実行しても変わらない
   （初回生成・追加後はサーバを再起動）。漏れた場合は `--revoke <名前>` で再発行。

> スクリプトを使わず手動で起動する場合:
> ```powershell
> $env:HITL_AUTH_USER="annotator"; $env:HITL_AUTH_PASS="（パスワード）"
> cd scripts\webapp\backend; python -m uvicorn main:app --port 8000
> # 別ターミナルで:
> cloudflared tunnel --url http://localhost:8000
> ```

---

## 2. 作業中の注意

- **PCを起動したままにする**（スリープ/シャットダウンするとURLが切れる）。電源・スリープ設定をオフ推奨。
- **URLはトンネル再起動ごとに変わる**。途中で停止・再起動したら `make_annotator_links.py --base-url <新URL>` で
  各人のリンクを作り直して配り直す（個人コードは不変なので、新URLを開いて個人コードを入力してもらってもよい）。
- 6人が同時にアクセスしても可（提案は lookup のみ）。別々の時間でも問題なし。
- 進捗（どのセッションを終えたか・何回目の試行か）は **サーバ上の保存記録から判定**する（全画像を提出済みのセッション＝完了）。
  PC・ブラウザを変えても進捗は引き継がれる。中断・途中終了したセッションは未完了扱い。

---

## 3. 停止

- 公開URLを止める: トンネルのウィンドウで **Ctrl+C**
- API サーバを止める: uvicorn のウィンドウを閉じる

---

## 4. 収集データの場所

`outputs/results/<session_id>/` にセッション単位で保存。
`session_id` = `{annotator}_{session_key}_a{attempt}_{timestamp}`

- `records.jsonl` … 1画像1行の完全記録（ジオメトリ・操作metrics・採点・隠し条件 condition/n/seed/model/group/gaze・提案の事前計算指標・attempt）
- `summary.csv` … 解析用フラット表（クラス別Dice/IoU・所要時間・編集量・attempt 列）

アノテータは各自の個人リンクから入る（記録の `annotator` はサーバが個人コードから決めた名前）。リンク無しで開くと
機能テスト用 `test` のみ選べる（`test` の記録は `test_...` として別保存され、実データに混ざらない）。

---

## 5. セキュリティ・プライバシー

- 通信は HTTPS（TLS）。Cloudflare はトンネルの中継のみで画像を保存しない。
- Basic認証により、URLを知っていてもパスワードがなければ到達不可。
- パスワードは安全な手段（口頭・別チャネル）で共有し、実験終了後はサーバを停止する。
- `HITL_AUTH_PASS` を設定せずに起動すると認証が無効になり、起動時に警告が出る。
  **トンネル公開時は必ずパスワードを設定すること。**

---

## 6. トラブルシュート

| 症状 | 対処 |
|---|---|
| URLを開くとログインを聞かれる | 正常。ユーザ名 `annotator` とパスワードを入力 |
| `401 Authentication required` | パスワード誤り。再入力 |
| 「このリンクは無効です」 | リンクの末尾が欠けている / 古いコード。`make_annotator_links.py` で表示したリンクを送り直す |
| URLにアクセスできない | 自PCが起動中か / トンネルのウィンドウが生きているか確認 |
| 提案が出ない | uvicorn ウィンドウのログ確認（起動時に proposals.json の全 item を検証済み。失敗していれば起動しない） |
| ポート8000が使用中 | 古い uvicorn を終了（タスクマネージャ / `taskkill`）してから再起動 |
