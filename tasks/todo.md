# HITL アノテーション webapp 実装計画

## 決定事項（ユーザ確認済み）
- 技術スタック: **FastAPI（バックエンド, PyTorch推論）+ Konva.js（CDN, 素のJS, ビルド不要）**
- アノテーションクラス: **4クラス** Eyelid/Caruncle(polygon), Iris/Pupil(楕円OBB)
  - HITL時、モデルは Eyelid/Iris/Pupil を事前提示、Caruncle は毎回手動追加（モデルは3ch=Eyelid+Caruncle統合のため）
- スコープ: **webapp優先**。モデルは設定で差し替え可能（現状フル3000枚チェックポイントのみ）
- 画像割当: **60枚すべて異なる画像**（testセット2500-2999から、症例リークなし、phaseへランダム均等割当）
- 結果: JSON + CSV で `outputs/results/` に保存

## phase 構成
scratch / HITL@500 / HITL@1000 / HITL@1500 / HITL@2000 / HITL@2500 の6 phase × 10枚 = 60枚

## 計測項目（HITL既報準拠・論文用フルセット）
- 品質: per-class Dice, IoU（vs GT）, mean Dice
- 時間: 画像ごと総所要時間, クラスごと作業時間, phase通し時間
- インタラクション: クリック数(総/クラス別), 頂点 追加/移動/削除 数, マウス移動距離(画像座標px), 編集操作数, undo数, ズーム/パン操作数
- HITL補正量: モデル初期予測 vs 最終 の per-class Dice（低いほど大補正）, 頂点移動量, 面積変化, Caruncle新規作成有無
- 派生: scratch比の時間削減・クリック削減

## ファイル構成
```
scripts/
  webapp/
    backend/
      config.py        # パス・phase・モデルレジストリ（差替え可能）
      geometry.py      # XMLパース, mask<->vector(contour/fitEllipse), ラスタライズ
      inference.py     # SegFormer ロード + predict_amodal + 初期ベクタ生成
      scoring.py       # GTマスク生成, Dice/IoU 計算
      session.py       # セッション/画像割当ロード, 結果保存
      main.py          # FastAPI エンドポイント
    static/
      index.html, css/style.css
      js/ app.js, canvas.js, tools.js, metrics.js
    config/
      experiment.json  # phase→モデル, 画像割当ファイル参照
  prepare_experiment.py  # 症例リーク無しで60枚割当生成 + GTキャッシュ
requirements.txt, README.md
outputs/results/         # セッション結果 json/csv
```

## 実装ステップ
- [x] 1. backend/config.py — パス・phase・モデルレジストリ
- [x] 2. backend/geometry.py — XMLパース, vector<->mask, ラスタライズ
- [x] 3. scripts/prepare_experiment.py — 症例安全な60枚割当生成
- [x] 4. backend/inference.py — モデルロード, predict_amodal, 初期ベクタ
- [x] 5. backend/scoring.py — GT Dice/IoU
- [x] 6. backend/session.py + main.py — API
- [x] 7. frontend: index.html / canvas.js（ズーム/パン）
- [x] 8. frontend: tools.js（polygon/楕円OBB編集）
- [x] 9. frontend: metrics.js（クリック/距離/時間/編集）+ app.js（phase制御/提出）
- [x] 10. requirements.txt, README.md
- [x] 11. 検証: サーバ起動, 推論動作, 1枚提出→結果JSON/CSV確認, Dice計算確認

## 検証（Done条件）
- uvicorn 起動成功
- /api/predict が初期ポリゴン/楕円を返す（HITL phase）
- scratch phase は空で開始
- 1枚アノテーション→提出→outputs/results/ に json/csv 出力, per-class Dice 算出を確認
- Playwright もしくは手動で UI のズーム/パン/頂点編集が動作

## レビュー
- webapp一式を実装し、バックエンド・フロント両方を検証済み（Playwright + API テスト）。
- 検証結果:
  - GT round-trip Dice = 1.000（geometry/scoring 正当性）
  - SegFormer推論 vs GT: eyelid 0.986 / iris 0.986 / pupil 0.978（実モデル動作）
  - Caruncle はモデル非対応のため初期空（HITLで手動追加）→ 仕様通り
  - scratch phase は initial=null、描画図形が記録に正確に保存
  - UI: 画像描画・ズーム/パン・ポリゴン/楕円描画・undo/redo・提出すべて動作
  - 出力: records.jsonl（無損失）+ summary.csv（全クラス計測値）
- 既知の前提 / 次フェーズ:
  - 現状モデルは全phaseが full 3000枚チェックポイントのプレースホルダ。
    サブセット5モデル（500/1000/1500/2000/2500, 症例リーク無し）の学習が別途必要。
    学習後 experiment.json の models.*.path を差し替えるだけで反映。
  - test pool は症例リーク安全な 2500-2999 の 463枚から 60枚を割当済み。
