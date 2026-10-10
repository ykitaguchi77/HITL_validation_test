# API レベルの機械検証は静的 UI 文言の取り残しを検出できない — 設計変更後は初期画面を 1 回スナップショットして grep する
- type: lesson
- created: 2026-09-19
- tags: [webapp, verification, playwright, testclient, design-pivot, ui-copy, blinding]

## 概要
実験設計を大きく変えたあと、FastAPI `TestClient` で API(セッション数・隠しフィールド非露出・応答時間・CSV 列)を機械検証して「全 PASS」になっても、
`index.html` にハードコードされた案内文(「練習 → Scratch → Session 1〜8」「各セッション10枚」「推論中…」)は旧設計のまま残っていた。
被験者が最初に見る画面の文言はデータ駆動ではないことが多く、API テストの守備範囲外。設計変更のたびに **初期画面を実ブラウザで 1 回スナップショットし、
旧設計の固有語(旧セッション名・旧枚数・旧モデル名・「推論」など)を grep する**ことを検証手順に含める。

## 背景・きっかけ
SegFormer 8 モデル(Scratch + Session 1〜8 × 10 枚)から SAM2 decoder-LoRA n-shot(練習 2 + Session 1〜5 × 12 枚、手動/提案混在)へ置換した際、
backend・`app.js`・`metrics.js` は書き換えたが `index.html` の説明段落と loading overlay の文言を見落とした。`verify_webapp_api.py` は全 PASS。
Playwright で `http://localhost:8017/` を開いたスナップショットの段落テキストで気づいた。被験者向け案内の不整合は盲検の手がかりにもなり得る(「推論中…」は
提案あり画像でだけ出るなら条件が漏れる)。

## 手順
1. 設計変更で使わなくなった固有語のリストを作る(旧セッションキー・枚数・モデル名・「推論」「Scratch」等)。
2. `grep -n` を `static/index.html` / `static/js/*.js` / ガイド md / README に対して実行し、残存箇所を潰す。
3. サーバを立て Playwright で初期画面 → 1 セッション目の 1 枚目まで進め、`browser_snapshot` のテキストを目視。
   ロックされたセッションは `localStorage` の完了キー(例 `hitl_done_<annotator>`)にダミーを入れて開錠すると本番手順を踏まずに確認できる。
4. 盲検アプリなら、同じ流れで `document.body.innerHTML` を条件語の正規表現(n128|seed|lora|condition|.jpg 等)で検査し、手動/提案の両方の画像で
   ツール既定・初期形状数・オーバーレイ文言が条件を示唆しないことを確認する。
5. 確認後はブラウザを閉じ、バックグラウンドサーバを停止する(ポート解放)。

## 注意点
- 案内文を `experiment.json` などのデータ側から描画するようにしておけば、この種の取り残しは構造的に減る(枚数・セッション数は既にデータ駆動だった)。
- loading overlay のような「条件によって表示頻度が変わる UI」は、文言そのものよりも**出現条件が対称か**を見る。

## 関連
- Experimental_record/20260919.md
- Knowledge/precomputed-proposals-import-consumer-postprocessing.md(runtime を lookup 化したため「推論中…」が実態と合わなくなった経緯)
- Knowledge/hitl-blinding-and-confound-design.md
- Knowledge/stop-background-verification-server-to-free-port.md
