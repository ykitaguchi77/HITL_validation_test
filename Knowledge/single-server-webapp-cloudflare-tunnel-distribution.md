# GPU推論WebAppを複数リモート作業者へ配布する（Cloudflare Tunnel + Basic認証・中央集約）

- type: technique
- created: 2026-06-24
- tags: [webapp, deployment, cloudflare-tunnel, fastapi, auth, HITL, blinding]

## 概要
GPU推論を伴う単一サーバ型 WebApp（FastAPI/uvicorn）を、インストール不要で N名のリモート作業者に
配布する構成。「アプリを配る」のではなく「URLを配る」ことで、モデル/データ/盲検正解をすべて
1台のサーバに集約したまま外部公開する。

## 背景・発見経緯
眼瞼セグメンテーションHITL課題を3名のアノテータに配布する方法を検討。デスクトップアプリ化は
8チェックポイント約430MB＋torch+CUDA環境＋全画像を各端末に配る必要があり、データが分散して
盲検整合性が崩れるため不採用。推論が重くデータは中央集約したい場合、URL配布が正解。

## 詳細

### 構成
```
N人のブラウザ ──HTTPS──> *.trycloudflare.com ──tunnel──> localhost:8000
       ↑ HTTP Basic（共有PW）              ↑ 既存 uvicorn（GPU/モデル/画像/結果保存すべてここ）
```
- 起動: `cloudflared tunnel --url http://localhost:8000`（quick tunnel）で即時に外部URL発行。
  独自ドメイン不要・当日から動く。
- 結果は全員分が自PCの `outputs/results/` に集約 → 中央サーバが盲検（隠し条件のサーバ側記録）を担保。
- リアルタイム同時編集ではないので別時間作業でOK。同時でも推論0.1秒程度で直列処理可能。

### アクセス制御（医用画像なので必須）
- trycloudflare URL は「知っていれば誰でも到達可能」→ URLの不明瞭さに頼らず**認証を1枚必ずかませる**。
- 案A（推奨・最小実装）: **共有パスワード1個の HTTP Basic**。全員同じID/PW、作業者番号はUIで各自選択。
- 実装は環境変数ゲート方式が安全: `HITL_AUTH_PASS` が設定されている時のみ全リクエスト
  （API・静的ファイル両方）を Basic 認証で保護するミドルウェアを通す。
  - **未設定（localhost開発）時は認証なしで従来通り動作し、起動時に「access control DISABLED」警告**を出す
    → 公開時の設定忘れ（=無防備公開）を防ぐ。本番で設定し忘れても警告で気付ける。
  - 失敗時は `401` ＋ `WWW-Authenticate: Basic realm="..."` を返しブラウザのログインダイアログを出す。

### 検証手順
- パスワードを設定して再起動し、curl等で **認証なし→401 / 誤り→401 / 正→200 / `WWW-Authenticate` 返却** を確認。
- localhost だけでなく**発行された公開URL(`*.trycloudflare.com`)経由でも** 認証なし→401 / 正PW→200 / トップページ→200 を確認する（外部到達＋認証が tunnel 越しに効くことの実証。localhost で通っても公開側で 502/認証素通り等が起きうるため必須）。
- 公開URLでのテストが済んだら、**医用画像を公開状態で放置しないため cloudflared と uvicorn を必ず停止**する（`taskkill` 後に port 8000 が listening でない・cloudflared プロセス無しを確認）。
- 検証後はローカル開発の挙動に戻すため認証なし（localhost既定）で再起動しておく。
- 起動ログのモデル読み込み警告（例: SegFormer の `classifier ... MISMATCH / Reinit due to size mismatch`）は、ベースモデルのクラス数を作り直して学習済み重みを被せる設計なら**正常**。ウォームアップで全モデル先読みすると同警告が複数回出る。quick tunnel の `cert.pem / origin certificate path` ERR も無害（接続は `Registered tunnel connection` で確立済み）。

### 運用上の注意（落とし穴）
- **quick tunnel の URL はトンネル再起動ごとに変わる** → 毎回URL再配布が必要。固定URLが要るなら
  Cloudflare 管理下の独自ドメインで「named tunnel + Cloudflare Access（メールPIN認証）」へ移行。
- 作業中はサーバPCを起動したまま（**スリープ無効推奨**）。
- 進捗（どのセッションを終えたか）が各人ブラウザの localStorage 保存方式なら、各自が決まった
  ブラウザ/PCを使えばOK（実データはサーバに集約されるので消えない）。
- 一括起動スクリプト（uvicorn＋トンネル）の先頭にPW変数を置き、既定値のままなら警告する作りにすると安全。
- **PowerShell に不慣れな運用者向けにはダブルクリック用 `.bat` ランチャを添える**と良い。中身は
  `chcp 65001`（日本語の文字化け防止）→ `powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_server.ps1"`
  （実行ポリシー回避で同フォルダの .ps1 を呼ぶ）→ 末尾 `pause`（ウィンドウを残す）の3点。`%~dp0` でバッチ
  自身のフォルダを基準にするのでどこへ置いても動く。Windows の「発行元不明」警告はファイル右クリック →
  プロパティ → 「ブロックの解除」で消える。

## 固定URL化（named tunnel）のコスト構造 — 追記 (2026-07-13)
「課金すれば固定URLにできる?」への正確な答えは **「Cloudflare への課金は基本不要。条件は自分のドメインを持つこと」**。
- **quick tunnel**（`cloudflared tunnel --url ...`）= `*.trycloudflare.com` のランダムURL・**再起動ごとに変わる**。当日から動くが本番不向き。
- **named tunnel**（名前付き）= 固定サブドメイン（例 `hitl.example.com`）を割当。**Cloudflare 無料プランで利用可能**でトンネル機能自体は無料。
- 課金が要るのは **ドメイン取得料のみ**（レジストラで年 ~1,000〜1,500円程度）。Cloudflare のアカウント・トンネル・DNS は無料枠。
- 手順（ドメイン前提）: `cloudflared tunnel login` → `tunnel create <name>` → `tunnel route dns <name> hitl.example.com` → 設定ファイルで `hitl.example.com → http://localhost:8000` を指定して起動（Windows サービス化で常駐可）。再起動しても URL 不変。
- **医用データ配布では named tunnel + Cloudflare Access（無料枠50ユーザー）を推奨**: 共有PWの代わりに作業者のメールアドレスへワンタイムコードでログインさせられ、共有PWより堅牢＆作業者の取り違えも防げる（現行 HTTP Basic と併用可）。
- ドメインを持ちたくない場合の代替: quick tunnel のまま毎回URL共有、または **Tailscale Funnel**（ドメイン不要で固定URL・無料枠あり）。

## 注意点・制約
- quick tunnel は本番長期運用には不向き（URL揮発）。短期パイロット〜小規模配布向け。
- HTTP Basic は共有PWのため作業者の取り違え防止はできない。厳密にするなら作業者別ID/PW（案B）か、上記 Cloudflare Access（メールPIN）へ移行。

## 関連
- Experimental_record/20260624.md（実装・実機検証）
- Experimental_record/20260620.md（配布方針の相談）
- Knowledge/hitl-annotation-webapp-konva.md（WebApp本体）
- Knowledge/hitl-blinding-and-confound-design.md（盲検設計）
