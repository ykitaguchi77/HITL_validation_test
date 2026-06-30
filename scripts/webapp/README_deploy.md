# HITL アノテーション実験 — 配布・収集 運用手順（管理者用）

3人のアノテータに遠隔で作業してもらい、結果を自PCに集約するための手順です。
構成は **「自PCで1台のサーバを動かし、Cloudflare Tunnel で公開、共有パスワードで保護」**（案A）。

```
3人のブラウザ ──HTTPS──> xxxxx.trycloudflare.com ──tunnel──> 自PC localhost:8000
        ↑ Basic認証(共有PW)                                  ↑ モデル/画像/GPU/結果保存
```

- アノテータはブラウザでURLを開くだけ（インストール不要）
- 推論・採点・記録はすべて自PCで実行 → 結果は `outputs/results/` に全員分集約
- モデル名・条件はクライアントに送られない（盲検はサーバが担保）

---

## 0. 前提（初回のみ確認）

- `cloudflared` インストール済み（確認: `cloudflared --version`）
  - 未導入なら: `winget install Cloudflare.cloudflared`
- システム Python に `fastapi` / `uvicorn` / `torch` / `transformers` が入っていること
- `scripts/webapp/config/experiment.json` と `outputs/models/seg*.pth` が存在すること

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
4. この **URL** と **ユーザ名 `annotator` / パスワード** を3人に配布
   （配布資料: `annotator_guide.md` を一緒に渡す）

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
- **URLはトンネル再起動ごとに変わる**。途中で停止・再起動したら新URLを配り直す。
- 3人が同時にアクセスしても可（推論は約0.1秒/枚で直列処理）。別々の時間でも問題なし。
- 進捗（どのセッションを終えたか）は **各人のブラウザ** に記録される。各自いつも同じPC・同じブラウザを使うよう伝える。
  実データは自PCに保存されるので、ブラウザ進捗が消えても提出済みデータは失われない。

---

## 3. 停止

- 公開URLを止める: トンネルのウィンドウで **Ctrl+C**
- API サーバを止める: uvicorn のウィンドウを閉じる

---

## 4. 収集データの場所

`outputs/results/<session_id>/` にセッション単位で保存。
`session_id` = `{annotator}_{session_key}_a{attempt}_{timestamp}`

- `records.jsonl` … 1画像1行の完全記録（ジオメトリ・操作metrics・採点・隠し条件 condition/model/train_size/block/gaze・attempt）
- `summary.csv` … 解析用フラット表（クラス別Dice/IoU・所要時間・編集量・attempt 列）

アノテータは UI で `1` / `2` / `3` を選択。`test`（動作テスト用）は本番では使わないよう伝える
（`test` の記録は `test_...` として別保存され、実データに混ざらない）。

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
| URLにアクセスできない | 自PCが起動中か / トンネルのウィンドウが生きているか確認 |
| 推論が出ない・遅い | uvicorn ウィンドウのログ確認。モデルは起動時にウォームアップ済み |
| ポート8000が使用中 | 古い uvicorn を終了（タスクマネージャ / `taskkill`）してから再起動 |
