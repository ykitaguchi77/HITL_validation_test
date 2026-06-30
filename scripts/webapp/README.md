# Eyelid HITL Annotation webapp

CVAT風のアノテーションUIで、ゼロから / 各SegFormerモデルをベースにしたHITLの
アノテーション効率（Dice・所要時間・クリック数・マウス移動距離・クラス別修正量）を計測する。

## クラス
- Eyelid / Caruncle … ポリゴン
- Iris / Pupil … 楕円(OBB, 回転対応)

HITLではモデルが Eyelid/Iris/Pupil を初期表示（Caruncleはモデル非対応のため手動）。

## セットアップ
```bash
pip install -r ../../requirements.txt        # プロジェクトルートの requirements.txt
python ../../scripts/prepare_experiment.py    # 60枚の割当を生成（experiment.json）
```

## 起動
```bash
cd scripts/webapp/backend
uvicorn main:app --port 8000
# ブラウザで http://localhost:8000
```

## 使い方
1. アノテータ名と phase を選んで「セッション開始」。
2. 10枚を通しでアノテーション（途中で休まない）。
3. 各画像で「提出して次へ」。10枚完了で自動保存。

### 操作
- ツール: V=選択/編集, P=ポリゴン, E=楕円, space/✋=移動, ホイール=拡大縮小, F=全体表示
- ポリゴン: クリックで頂点追加、最初の点付近 or ダブルクリックで閉じる。
  辺の中点クリックで頂点追加、Alt+クリックで頂点削除。
- 楕円: ドラッグで作成、選択ツールで回転・リサイズ。
- Ctrl+Z / Ctrl+Y = undo/redo、Del = 選択図形削除。

## 出力
`outputs/results/<session_id>/`
- `records.jsonl` … 1行=1画像（図形ジオメトリ・全計測値・GT比較スコア）
- `summary.csv`   … 1行=1画像のフラットな集計（解析用）

## モデルの差し替え
`scripts/webapp/config/experiment.json` の `models.<key>.path` を学習済みサブセット
モデルのチェックポイントに変更する（現状は全て full 3000枚モデルのプレースホルダ）。

## 構成
- `backend/config.py` … パス・クラス・モデルレジストリ
- `backend/geometry.py` … XMLパース, vector⇔mask, Dice/IoU
- `backend/inference.py` … SegFormer推論→初期ベクタ
- `backend/scoring.py` … GT比較・HITL補正量
- `backend/session.py` … 結果保存(JSONL/CSV)
- `backend/main.py` … FastAPI
- `static/` … フロント(Konva.js, ビルド不要)
