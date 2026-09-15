# 実施前の設計・資料調整（2026-09-15）
- [x] annotator_guide.md: アノテータ選択を実名（kubota/maeda/kaisho）表記へ修正、予測の直し方（修正でも削除→描き直しでも可）を明記
- [x] 最終セッション「Scratch（2回目）」を追加（案A: セッション0と同じ10枚を専用RNGで再シャッフル・is_repeat=True・condition=scratch）
  - `scripts/prepare_experiment.py`: SCRATCH_REPEAT_KEY/LABEL 追加・生成・audit 拡張（最終セッション/非HITL/画像集合==セッション0/順序差/連番 index）
  - `scripts/webapp/config/experiment.json` 再生成（全 assertion PASS）。新旧 diff: blocks/practice/latin_square/models と各アノテータ sessions[0..9] は完全一致、末尾 1 セッションのみ追加
  - backend/frontend はデータ駆動のためコード変更なし。ローカル起動で /api/run（13セッション・盲検キー非露出）・/api/session（10枚=セッション0）・/api/predict（空プレフィル）・/api/submit（summary.csv に condition=scratch/is_repeat=True/session_index=10）を実 API 検証、検証記録削除・サーバ停止
  - `scripts/webapp/annotator_guide.md` を全13セッション構成へ更新
- [x] 事前解析計画書 `outputs/docs/analysis_plan.md`（主要=duration_sec、log(枚数)用量反応の混合効果モデル、scratch 基準=2回目、非劣性マージン Dice −0.01/HD95 +2px、attempt 1 採用、図表計画）を作成
- [x] アノテータ背景調査票 `outputs/docs/annotator_questionnaire.md`（職種・経験・アノテ経験・GT関与・操作環境・自己評価・実施予定・作業後質問）を作成
- [ ] 本番前に `run_server.bat` で再起動（experiment.json は起動時ロード）・`$Pass` を本番値へ
- [ ] 倫理審査の状況確認（患者画像二次利用＋アノテータの研究参加同意）

## レビュー（Scratch 2回目）
- 順序効果（scratch が常に習熟前）の補正用に、同一人物・同一画像の pre/post scratch ペア（30ペア）を得る設計。
- 解析では末尾 scratch を保守的な基準値として用い、初回との差を順序効果として報告する方針。

---

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

---

# 計測項目の追加（既報調査 2026-07-11 を受けて）

決定事項（ユーザ確認済み）:
- 境界指標は **全3クラス（eyelid/iris/pupil）**、許容幅 **2px**（≤2px を一致）
  ※当初は眼瞼のみとしたが、オフライン計算でアノテーター負担ゼロのため全クラスへ拡張。
    虹彩/瞳孔は楕円ゆえ HD95/ASSD が有用（Boundary-F1 は固定許容幅で小構造ほど甘め）。
- 主観負荷は **単一項目(Paas 9段階)を全画像**、submit後に取得（duration 非計上）
- クリック/編集の **タイムスタンプ** を記録（初動時間・アイドル時間・労力vs品質曲線の土台）
- 再現性用に **各アノテータ5枚を再掲**（同一条件で test-retest）

## タスク
- [x] 1. metrics.js: イベントのタイムスタンプ記録＋初動時間/アイドル時間の導出
- [x] 2. scoring.py: 眼瞼の境界指標 HD95 / ASSD / Boundary-F1@2px（cv2）
- [x] 3. session.py / main.py: effort・初動・アイドル・境界指標の列を追加・保存
- [x] 4. index.html / app.js: submit後に Paas 9段階の努力尺度モーダル
- [x] 5. prepare_experiment.py: 各アノテータに再掲5枚のセッションを追加（同一条件）
- [x] 6. 実サーバ + Playwright/実APIで end-to-end 検証

## 次フェーズ候補（2026-09-15 論文戦略相談・ユーザー判断待ち）
- [ ] 事前解析計画書（主要=作業時間 / 副次指標・混合効果モデル式・非劣性マージン・クラス別効率曲線）を `outputs/` に作成
- [x] 末尾 scratch セッション（10枚）追加の設計変更 — 案A で実装完了（2026-09-15、詳細は冒頭セクション）
  - [x] `scripts/prepare_experiment.py` に「Scratch(2回目)」を Session 9 の後へ専用RNGで追加（既存90枚・練習・S9 割当不変を audit + 新旧 JSON diff で再検証）
  - [x] 記録は `is_repeat=true` + `condition=scratch`（backend/front は Session 9 の再掲機構を流用・コード変更なし）
  - [x] `scripts/webapp/annotator_guide.md` を全12→13セッションへ更新
  - [x] ローカル実サーバ + 実APIで end-to-end 検証（検証記録削除・サーバ停止済み）
- [ ] アノテータ3名の倫理審査・同意手続きの確認
- [x] `scripts/webapp/annotator_guide.md` の実施前修正 ①アノテータ選択を「番号 1/2/3」→ 実名（kubota/maeda/kaisho）へ ②「予測の直し方は自由（修正 / 削除→描き直し）」を明記（2026-09-15）
- [ ] `scripts/webapp/annotator_guide.md` の残り: ③周辺視の楕円回転を練習「もう一度やる」で慣れる案内 ④目標精度の伝え方の決定 ⑤休憩・分割実施の目安
- [ ] 事前解析計画に「描き直し画像（HITL で `shapes_deleted > 0`）の扱い＋描き直し率 vs 学習枚数を副次指標」を明記
- [ ] 事前解析計画に「同一 `session_key` に複数試行（`a2`, `a3`…＝中断→やり直し）がある場合の扱い（最新のみ採用等）」を明記
- [x] webapp 一式 + `annotator_guide.md` の未コミット分を実施前にコミット（`a5951a0`・31ファイル、患者データ/`.pth`/資格情報の非混入を機械確認）（2026-09-15）
- [x] GitHub へ push（`git push origin main` は自動モード分類器にブロック → ユーザーが `! git push origin main` を実行し `4716de3..a5951a0 main -> main` で成功）（2026-09-15）
- [ ] `scripts/webapp/run_server.ps1` の `$Pass` を本番値へ変更（変更はコミットしない）→ `run_server.bat` で再起動
- [x] 論文化リスクの対応状況を棚卸し（10件: ✅1 / ⚠️3 / ❌5 / ❓1）し「開始前必須 / 後から補える」に仕分けして提示（2026-09-15）
- [ ] **開始前必須**: 事前解析計画書 `outputs/analysis_plan.md`（上記の描き直し・複数試行の扱いも統合）— ユーザー判断待ち
- [ ] **開始前必須**: アノテータ3名の背景情報（経験年数・専門・アノテーション経験）を短い質問票で収集し `outputs/` に保存（`annotator` 名と紐づけ）
- [ ] 後から補える: 学習曲線の seed 反復（100〜500 で 2〜3 run・誤差棒）／U-Net ablation は削除推奨／タイミング副チャネルは Limitations

## レビュー（計測項目追加）
- 全5項目を実装し、実サーバ + Playwright + 実APIで end-to-end 検証済み。
- 追加した記録列（summary.csv）: is_repeat, time_to_first_action_sec, idle_time_sec,
  effort, eyelid_hd95, eyelid_assd, eyelid_boundary_f1。JSONL には events[]（{t,type,cls}）も保存。
- 境界指標（cv2 distanceTransform）検証: 同一→HD95=0/ASSD=0/F1=1.0、1px→F1=1.0、5px→F1=0.5、空→None。
- 全3クラス（eyelid/iris/pupil）で算出。楕円もマスクにラスタライズしてマスク境界のずれを測る方式
  （楕円パラメータ直接比較ではない）。列は per-class 共通（{k}_hd95/{k}_assd/{k}_boundary_f1）へ整理。
- 主観負荷: submit で metrics スナップショット（duration 確定）→タイマー停止→Paas 9段階モーダル→
  評価後に POST。回答時間は duration に非計上。Playwright で overlay 表示→クリック7→記録=7 を確認。
- 再掲セッション: 各アノテータに hitl_repeat（Session 9・5枚・同一条件）を追加。experiment.json 再生成、
  全 assertion PASS。専用RNGで既存90枚割当・練習は不変。クライアントには is_repeat/condition 非露出（盲検維持）。
- 検証で作成した test 記録は削除済み（既存の 2026-06-30 分 test_p_* 2件は棚卸し保留のまま温存）。

---

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
