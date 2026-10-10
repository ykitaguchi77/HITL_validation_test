# 被験者実験の AI 提案は「全 (画像, 条件) を事前計算 → 消費側の後処理コードを import して形状化」する
- type: technique
- created: 2026-09-19
- tags: [hitl, user-study, blinding, precompute, cross-repo, sam2, lora]

## 状況
モデル開発リポジトリ(MODEL: SAM2 + decoder-LoRA、専用 .venv)と被験者実験リポジトリ(STUDY: FastAPI webapp、system python、transformers のバージョンも別)が分かれており、
実験アプリで n∈{1,…,128} × 3 seed = 72 チェックポイントの提案を盲検で出したい。実験は 60 枚 × 6 名で、提案の対 GT 指標(修正量)も解析に使う。

## 問題
- runtime 推論にすると、①アプリが MODEL 側の環境(torch/transformers/SAM2 重み)に依存し 2 リポの環境差で壊れる、②条件ごとに推論時間が違い**応答時間が盲検のサイドチャネル**になる、
  ③手動条件(提案なし)は即応答なので手動/提案の区別がつく、④チェックポイントの読み替え・キャッシュが複雑になる。
- 提案マスクを MODEL 側で「独自に」ポリゴン化・採点すると、webapp が最終アノテーションを採点するコードと**微妙に違う後処理**になり、提案指標と最終指標が比較不能になる。

## 解決策・手順
1. STUDY 側で研究画像リストを先に凍結(`study_images.json` + sha256)。
2. MODEL 側に export スクリプトを置き、画像ごとに特徴を 1 回だけ抽出してキャッシュ、72 チェックポイントを順に読んで prob を出す。
3. その export スクリプトから **STUDY 側の `geometry.masks_to_shapes` / `scoring` を `sys.path` 経由で直接 import** し、形状化(polygon/楕円)と対 GT 指標を webapp と同一コードで計算する。
4. 出力は `proposals.json`(キー = (image, n, seed) → shapes + 指標)+ sha256。STUDY の `inference.py` は lookup のみ(torch 非 import)、起動時に「割付が要求する全キーが存在するか」と sha を検証する。
5. 手動条件も同じ lookup 経路(空の提案)を通し、応答時間が条件で変わらないようにする。
6. 事前計算した指標は解析にも使う(本件 H5: 提案の修正量が実測の手間を予測するか)。

## 注意点・落とし穴
- モジュール名衝突: STUDY の `config.py`/`geometry.py` は一般的な名前なので、MODEL 側で同名モジュールが無いか `ls` で確認してから `sys.path.insert(0, ...)` する。
- STUDY 側 `INFER_SIZE`(推論解像度)を import して使い、MODEL 側で数値を複製しない。
- 生成物(`proposals.json`, `study_images.json`)は患者 ID を含むので `.gitignore` に入れ、sha256 だけを文書に記す。
- 学習は長い(72 個 ≈1.5 h)ので、まず `--levels 1,2,4 --seeds 0 --n-eval 10` のようなスモーク用オーバーライドを用意し、本番はバックグラウンドで回して並行作業する。

## 関連
- Experimental_record/20260919.md(Step C/D の実装)
- Knowledge/design-pivot-inventory-frozen-artifacts-and-seams.md(2 リポの契約を「画像リスト+提案 JSON」に閉じる方針)
- Knowledge/hitl-blinding-and-confound-design.md(盲検設計)

## 追記 (2026-09-20) — 後処理を変えたら「提案 JSON → 割付 JSON → 文書」のハッシュ連鎖を全部更新する
- 出典: Experimental_record/20260920.md(提案平滑化 σ=2 の導入)
- 事前計算の後処理(本件: 確率マップの Gaussian σ=2 → 二値化)を変えると `proposals.json` の sha256 が変わり、それを provenance に含む `experiment.json` の sha256 も変わる
  (SEED 固定なので割付そのものは不変)。解析計画書・事前登録ドラフト・todo に転記した sha256 をすべて差し替え、`verify_webapp_api.py` を再実行し、サーバを再起動してユーザーにリロードを依頼する。
- 後処理の変更は export スクリプトの定数(`BLUR_SIGMA`)+ `provenance.postprocess` 文字列の両方に書き、根拠(日付・検証数値)をコメントに残す。
- 変更前に取った試用記録は「旧提案」として区別する。詳細は [[proposal-jaggedness-smooth-probability-map-before-threshold]]。

