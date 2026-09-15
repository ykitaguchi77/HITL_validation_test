# クラス別の労力計測は「選択中クラス」で帰属させ、既定クラスへの初期時間の混入を解析で補正する
- type: pattern
- created: 2026-09-15
- tags: [hitl, instrumentation, per-class, metrics, annotation-effort, analysis]

## 概要
複数クラスを1画像で編集するアノテーションツールで「クラス別にどれだけ手間がかかったか」を後から
計算できるようにするには、**時間・クリック・頂点編集を「UI 上で選択中のクラス」に帰属して蓄積**し、
かつ**全操作を `{t, type, cls}` のイベントログとして残す**。集計列はクラス名をハードコードせず
`{k}_time_sec` / `{k}_clicks` / `{k}_vertices_edited` / `{k}_correction_dice` のように
per-class 共通カラムで生成する。

## 背景・発見経緯
実験再開の相談時に「クラス別の手間はログから計算できるか」と問われ、コードを読み直したところ
既に `summary.csv` に per-class 列として保存済みだった(追加実装不要)。ただし帰属ルールに起因する
**系統的な偏り**(下記)があり、解析時に把握しておく必要があると整理した。

## 詳細
- 帰属の単位: `setActiveClass(key)` 時に前クラスの経過時間を flush → 新クラスに切替(`_flushClassTime`)。
  クリック・頂点編集も `activeClass` にカウント。クラス切替はサイドバーのみ(canvas クリックでは変わらない)
  ので帰属が曖昧にならない。
- 一時停止(フォーカス喪失・モーダル)中の時間はクラス別にも計上しない([[timed-task-timing-hygiene-focus-pause-heartbeat]])。
- **既定クラスへの混入**: 画像表示直後に既定で eyelid が選択されるため、全体を眺める・ズームする等の
  クラス非依存の時間が eyelid に乗る。3クラス合計は `duration_sec` に一致するが、eyelid は過大評価側。
  → 解析では `events[]` から「最初の操作までの時間(初動時間)」を差し引く、または初動時間を別列として扱う。
- **図形種別で指標の意味が違う**: 楕円(移動/リサイズ/回転)は頂点編集ではないため `{k}_vertices_edited` に乗らない。
  ポリゴンクラスと楕円クラスを同じ「編集数」で比べない。時間・クリック・correction_dice(修正量)で比較する。
- クラス別に取っていない指標(例: マウス移動距離)は、events の `cls` を使えば後から帰属できる設計にしておく
  (mouseMove イベントに cls を持たせる)。

## 適用場面
- 複数クラス/複数図形種別を1画面で編集する HITL・アノテーション効率実験全般。
- 「モデル成熟に伴う手間の減り方がクラス(図形種別)で異なるか」をクラス別効率曲線で示したいとき。

## 関連
- [[symmetric-instrumentation-across-comparison-arms]](条件間で計測を対称に)
- [[boundary-metrics-2d-cv2-distancetransform]](per-class 共通カラムの設計)
- [[hitl-annotation-efficiency-metrics-from-literature]]

## 参照
- Experimental_record/20260915.md
- `scripts/webapp/static/js/metrics.js`(`setActiveClass`/`_flushClassTime`)
- `scripts/webapp/backend/session.py`(`_per_class_cols()`)
- `scripts/webapp/static/js/app.js`(画像表示直後 `setActiveClass("eyelid")`)
