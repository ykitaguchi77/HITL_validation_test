# Eyelid HITL Annotation webapp

CVAT 風のアノテーション UI で、提案なし（手動）/ n-shot decoder-LoRA チェックポイントの提案を初期値とする
HITL のアノテーション効率（active 時間・クリック数・頂点編集・マウス移動距離・クラス別修正量）と品質
（対 GT Dice / HD95 / ASSD / BF@2px）を盲検で計測する。

## クラス
- Eyelid（涙丘を含む一体）… ポリゴン
- Iris / Pupil … 楕円 (OBB, 回転対応)

## 提案は事前計算（runtime に GPU / torch 不要）
全 (画像, n, seed) の提案と対 GT 指標は `outputs/proposals/proposals.json` に事前計算されている
（`Eyelid_few_shot_HITL/scripts/eval/export_study_proposals.py`）。アプリは lookup だけを行うので、手動と提案の
応答時間が同じ（タイミングで条件を推測できない）。

## セットアップ
```bash
pip install fastapi uvicorn opencv-python numpy
python scripts/select_study_images.py        # 研究画像プールを凍結（outputs/study_pool/study_images.json）
# → Eyelid_few_shot_HITL 側で make_nshot_checkpoints.py → export_study_proposals.py
python scripts/prepare_experiment.py         # 割付を生成（experiment.json、全 assert）
```

## 起動
```bash
cd scripts/webapp/backend
uvicorn main:app --port 8000     # 起動時に全 item の提案が存在することを検証
# ブラウザで http://localhost:8000
```
本番配布は `run_server.ps1`（Basic 認証 + Cloudflare tunnel）を使う。

## 使い方
1. アノテータ名を選び、セッションを上から順に開く（練習 2 → Session 1〜6）。
2. 各セッション 10 枚（提案あり 6〜7 + 手動 3〜4 がランダム順、条件は非表示）。提案があれば修正、無ければゼロから描く。
3. 各画像で「提出して次へ」→ 確認 → 負担度 (1–9) → 保存。

### 操作
- ツール: V=選択/編集, P=ポリゴン, E=楕円, space/✋=移動, ホイール=拡大縮小, F=全体表示
- ポリゴン: クリックで頂点追加、最初の点付近 or ダブルクリックで閉じる。Shift+クリックで点追加。
- 楕円: ドラッグで作成、選択ツールで回転・リサイズ。
- Ctrl+Z / Ctrl+Y = undo/redo、Del = 選択図形削除。

## 出力
`outputs/results/<annotator>_<session>_a<attempt>_<stamp>/`
- `records.jsonl` … 1 行 = 1 画像（図形・全計測値・GT 比較・隠し条件 n/seed/model/group・提案の事前計算指標）
- `summary.csv`   … 1 行 = 1 画像のフラットな集計（`scripts/analysis/fit_models.py` の入力）

## 構成
- `backend/config.py` … パス・クラス
- `backend/geometry.py` … XML パース, vector⇔mask, `masks_to_shapes`（提案形状フォーマットの唯一の定義）, Dice/IoU
- `backend/inference.py` … proposals.json の lookup + 起動時検証
- `backend/scoring.py` … GT 比較・HITL 補正量
- `backend/session.py` … 結果保存 (JSONL/CSV)
- `backend/main.py` … FastAPI（盲検 API）
- `static/` … フロント (Konva.js, ビルド不要)
