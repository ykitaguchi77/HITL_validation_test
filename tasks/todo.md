# 実験設計の置換: SAM decoder-LoRA n-shot 用量反応・ランダム化(2026-09-19)
計画ファイル: `~/.claude/plans/sharded-brewing-marshmallow.md`(承認済み 2026-09-19)

## 設計確定(完了)
- [x] 採用設計 = `Eyelid_few_shot_HITL/knowledge/study-design-crossover.md` 現行案(用量反応・ランダム化)、既存 SegFormer 設計は完全置換、推論は本 webapp 側
- [x] 参照 GT = 既存 CVAT GT / レシピ = n=0 から 1 枚ずつ各 1 epoch(lr 1e-3・AdamW 保持・flip aug)/ 学習順 3 seed
- [x] 統計レビュー: 品質ゲートを主要評価から外し H1 時間 + H2 非劣性(fixed-sequence)/ 画像変量効果 / 検出力シミュレーション / manipulation check
- [x] 被験者 **6 名**(A | S の組: 6 名 × 12 スロット(n×8 + 手動 4)× G=5 → 60 枚/人・5 セッション×12 枚、各画像 = 手動 2 名 + n 4 種、総観測 360)。3/5 名でも組めるようパラメータ化
- [x] Plan 承認(ExitPlanMode)

## 実装
- [x] Step A: `scripts/select_study_images.py`(+ `scripts/study_design.py` 割付則) → `outputs/study_pool/study_images.json`(研究 60 + 練習 5、患者 ≤5 枚、sha256)
- [x] Step B: MODEL `scripts/eval/make_nshot_checkpoints.py` → `Eyelid_few_shot_HITL/outputs/20260919_nshot_lora`(72 チェックポイント、患者分離 200 枚/49 患者で評価、学習プール 108 患者。n=128: eyelid Dice 0.977–0.979 / ASSD 2.2–2.3 px、iris 0.94–0.95、pupil 0.89–0.90。n=0 未学習参照点も記録)
- [x] Step C: MODEL `scripts/eval/export_study_proposals.py` → `outputs/proposals/proposals.json`(65 枚 × 8 n × 3 seed = 1560 エントリ、3.0 MB、sha256 90caf6af…)+ `outputs/model_eval/`(summary/per_image/per_step/manifest/orders/nshot_curve.png)
- [x] Step D: webapp backend を torch 無し JSON lookup 化(`geometry.masks_to_shapes` / `config` / `inference` / `main` / `session`)+ `app.js` 混合セッション + `metrics.js` per-class 編集列
- [x] Step E: `scripts/prepare_experiment.py` 書き直し(A パラメータ化・12 スロット回転・周辺画像の巡回配置・seed 2/2/1 回転・全 assert)→ `experiment.json` v2(sha256 f649066e…、患者 study 26 / train 108 / 評価 49 で分離)。A=3/5 もモック提案で audit PASS
- [x] Step F: `scripts/analysis/power_sim.py`(300 反復完了: H1 時間比 0.7・SD 0.5 で 0.99 / H2 真差 0.3px・δ=1px で 0.96 → `analysis_plan.md` v2.0 §6・OSF v2 に転記済み) / `scripts/analysis/fit_models.py`(合成データで H1/H3 の植込み効果を回復)
- [x] Step G: `analysis_plan.md` v2.0 / `osf_preregistration.md` v2 / `annotator_guide.md` / README / `.gitignore`
- [x] 検証: `scripts/verify_webapp_api.py` 全 PASS(torch 未 import・盲検 API 非露出・手動/提案の応答時間 2.0 vs 2.3 ms・summary.csv 新列・練習 GT / 本番 403)+ Playwright 実ブラウザで Session 1 の 12 枚(手動 4 = polygon ツール・提案 8 = select ツール)・DOM 非露出・描画確認(`outputs/figures/webapp_proposal_check.png`)。`index.html` の旧文言も更新
- [x] ユーザーテスト中のフィードバック(2026-09-19): 範囲選択した頂点の **一括削除**(Delete/🗑、`PolygonShape.deleteVertices`・`ToolController.deleteContext`、undo 1 段)、右サイドバーに **状態連動の操作パネル**(`app.updateOps`)、**7 ステップの操作チュートリアル**(`static/js/tutorial.js`、初回セッション自動表示・`?` ボタン・開いている間は計測を一時停止)。Playwright で 56→29 点の一括削除・per-class 計測・undo 復元・パネル切替を確認
- [x] ユーザーテストのフィードバック②(2026-09-19): 矢印キーは**選択中の頂点 1 点だけ**を動かす(ポリゴン全体は動かさずヒント表示、楕円は全体移動のまま)/ **セッションを 10 枚に**(`study_design.session_slots`: 12 スロット中 10、欠落 2 スロットを均等巡回・手動 3〜4/セッション、周辺は貪欲均衡)→ 6 セッション × 10 枚、`experiment.json` 再生成 sha256 bdf01c48…、`verify_webapp_api.py` 全 PASS、計画書・OSF ドラフト・ガイド・UI 文言を更新
- [x] test アカウントで Session 1 を通し実施(2026-09-19 深夜、10 枚 ≈17 分)。データは全列に流入。発見: ①`loadCurrent` で `metrics.reset()` がアクティブクラスを消し、最初にタブを押すまで eyelid のクラス別時間/クリック/頂点数が計上されない → reset 後に `setActiveClass` を再適用して修正 ②手動項目で空の initial に対して correction_dice=0 が記録 → 手動は `initial=None` にして修正
- [x] test Session 2(2026-09-20 04:11–04:32 JST、10 枚 ≈22 分)。手動の correction 列は NaN(修正②反映)。最終行(手動)で eyelid_time=0/eyelid_vertices_added=0 なのに vertices_added=59 → ブラウザが**古い app.js のまま**(ページ未リロード)で修正①が効いていない。対策: `/api/config` に `app_version`(static の最新 mtime)を載せ、セッション開始時に不一致なら自動リロード(`app.js startSession`)
- [x] 練習 2 の教示追記(セッション開始前モーダル `HITL.SESSION_INTRO`: 練習1/練習2/本番、「提案が合って見えても正解の精度まで確認して直す」)+ サイドバー・チュートリアル・ガイド
- [x] n=128 でも提案がギザギザ(ユーザー指摘)→ 表示時の平滑化は無し。`smoothing_check.py`(MODEL)で確率マップ Gaussian σ=2@512 が ASSD 不変で折れ角 12.0→9.7°、図 `outputs/figures/proposal_smoothing_check.png`。`export_study_proposals.py` に σ=2 を導入して再エクスポート(sha256 01bfdeaf…)、`experiment.json` 再生成(fc9fe1b8…)、verify PASS
- [x] 練習 1 の教示文言をユーザー指定の「模範解答」ニュアンスへ書き換え(2026-09-20)+ 被験者向け表記「正解(GT)」→「模範解答」を `tutorial.js`/`app.js`(サイドバー・提出後 status)/`annotator_guide.md` で全箇所統一。サーバ再起動(タスク `bie54deyv`)
- [x] 本番/練習 2 の教示を「提案が大体合っていてもピクセル単位で正解を目指す」へ、被験者向け文面から「速さは競いません」等の速度言及を全削除→「いつも通りのペースで」(`tutorial.js`/`app.js`/`annotator_guide.md`、grep 残り 0)。サーバ再起動(タスク `buczsg1ih`)(2026-09-20)
- [x] 教示の改訂(ユーザー指示): 練習 1 は「練習のみ、完成後に模範解答が出る。微妙な部分のニュアンスを確認し本番でも同じように」/ 本番・練習 2 は「提案が大体合っていてもピクセル単位で正解を目指す」/ 「速さは競いません」を全廃し「いつも通りのペースで」/ 「正解(GT)」→「模範解答」に統一
- [x] 本番被験者には経過タイマーとサイドバーの計測カウンタを非表示(`body.dev-metrics` は test アカウントのみ)。チュートリアル図・ガイドも更新
- [x] test Session 3(2026-09-20 19:43–20:03 JST、10 枚 ≈20 分、平滑化後の提案+新教示)を監査: 手動 4 枚で `eyelid_vertices_added` = `vertices_added`(50/45/40/46)・`eyelid_time` 全行あり = 修正①と version 照合の反映を確認、空提案(n=16 瞳孔)も正常。教示変更で n≥64 の眼瞼仕上げ工数 17〜25 → 38.5 点・40〜51 → 87 s(意図どおり)。30 枚合算: 手動 111 s / n=128 56 s / 低 n 135〜193 s
- [x] pilot 30 枚(test S1–S3)で残差 SD・効果量を実測し `power_sim.py` に代入して再計算(2026-09-20): log 残差 SD 0.35 / −12%/倍増 / ASSD 残差 SD 眼瞼 0.76・虹彩 3.11・瞳孔 1.79 px → H1 は 6 名で余裕、H2 は虹彩のみ余裕少(δ=2.3 px・真差 1 px で 0.65)
- [x] 登録用 `outputs/analysis/power_sim.csv` の復元確認(2026-09-20 20:24: 復元ジョブ `bhx4enlz5` 完了 → H1 比 0.7 × SD 0.5 = 0.987 / H2 真差 0.3 px = 0.957 = 登録値 0.99/0.96、探索行は消去)
- [ ] `power_sim.py` に `--out` を追加して再発防止(次の探索実行前に)
- [x] pilot 実測値を `analysis_plan.md` §5.11 に「パイロット実測」として追記(2026-09-20 20:24、§6 の固定パラメータ・版番号は据え置き。未コミット)
- [ ] ユーザー判断待ち: δ_iris を inter-rater × 0.5 のままにするか、inter-rater そのもの/探索的扱いにするか(事前登録前に確定)
- [x] 「既報の円・楕円近似は何を基準に精度を決めているか」に分野別で回答し、楕円パラメータ誤差(中心・長軸/短軸・回転角・楕円 IoU)+ MRD1/MRD2/PFH(HVID 換算 mm)の副次指標追加を提案(2026-09-20 20:46、説明のみ)
- [x] ユーザー承認済み(2026-09-20、実装は下記 [x] 参照): 上記副次指標を `geometry.py`/採点に追加するか。追加なら: 主指標 ASSD は不変 / 提案側 `*_prop_*` にも対称付与 / 回転角は離心率で条件付け / HVID 換算の仮定を明記 / test S1–S3 は records.jsonl から再採点 / δ_iris の定義指標と一括で決めて `analysis_plan.md` v2.1 に反映
- [ ] test Session 4〜6 の継続監査。S6 完了で開発者手動 22 枚 → 構造別 δ_k(ASSD × 0.5)を算出し `analysis_plan.md` v2.0 / OSF v2 に記入(`outputs/results/test_*` は δ_k 用に温存)
- [x] 検出力の実測更新: パイロット 30 枚から残差 SD 0.35(log)・効果 −12%/倍増・ASSD 残差 SD 眼瞼 0.76/虹彩 3.1/瞳孔 1.8 px → 6 名で H1 は十分、虹彩の非劣性は δ の決め方次第(計画書 §5.11 追記、`power_sim.csv` は登録用設定で復元)
- [x] 既報準拠の楕円指標(中心誤差・軸誤差・水平/垂直径誤差・回転誤差)と臨床指標(MRD1/MRD2/PFH、GT 虹彩 HVID=11.7 mm で mm 換算)を `scoring.py`/`session.py` に追加、提案側にも同梱して再エクスポート(sha256 b0268b2b…)、`experiment.json` 再生成(bcc841d9…)、verify PASS。`scripts/analysis/rescore_records.py` で既存記録を再採点(`summary_rescored.csv`、`fit_models.py` が優先読込)
- [ ] ユーザー側: 被験者 6 名の名前登録、δ_s 用の開発者手動 20 枚、OSF v2 提出、IRB 範囲確認・同意
- [ ] 旧設計向け残件(`$Pass` 本番値化・質問票配布・倫理確認)は新設計の実装後に再実施
- [~] ユーザー手動テスト: webapp を localhost:8000 でバックグラウンド起動中(現タスク `blc590ed3`、認証なし、2026-09-20 12:43 再起動=教示文言更新。app_version 照合で次回開始時に自動リロード)。新列の流入確認は完了(上記 Session 1 監査)。残り: UI フィードバック反映 → **サーバ停止**
- [ ] ユーザー回答待ち(2026-09-20): 練習 2 の教示に「提案が合って見えても正解と同じ精度になるまで確認して直す」を追加するか / 「ポリゴン選択中は通常ドラッグを範囲選択に」するか
- [ ] 本日のバグ修正 2 件(`app.js`・`main.py`)を含む全変更のコミット

---

# 実施前の設計・資料調整（2026-09-15）
- [x] annotator_guide.md: アノテータ選択を実名（kubota/maeda/kaisho）表記へ修正、予測の直し方（修正でも削除→描き直しでも可）を明記
- [x] 最終セッション「Scratch（2回目）」を追加（案A: セッション0と同じ10枚を専用RNGで再シャッフル・is_repeat=True・condition=scratch）
  - `scripts/prepare_experiment.py`: SCRATCH_REPEAT_KEY/LABEL 追加・生成・audit 拡張（最終セッション/非HITL/画像集合==セッション0/順序差/連番 index）
  - `scripts/webapp/config/experiment.json` 再生成（全 assertion PASS）。新旧 diff: blocks/practice/latin_square/models と各アノテータ sessions[0..9] は完全一致、末尾 1 セッションのみ追加
  - backend/frontend はデータ駆動のためコード変更なし。ローカル起動で /api/run（13セッション・盲検キー非露出）・/api/session（10枚=セッション0）・/api/predict（空プレフィル）・/api/submit（summary.csv に condition=scratch/is_repeat=True/session_index=10）を実 API 検証、検証記録削除・サーバ停止
  - `scripts/webapp/annotator_guide.md` を全13セッション構成へ更新
- [x] 事前解析計画書 `outputs/docs/analysis_plan.md`（主要=duration_sec、log(枚数)用量反応の混合効果モデル、scratch 基準=2回目、非劣性マージン Dice −0.01/HD95 +2px、attempt 1 採用、図表計画）を作成
- [x] アノテータ背景調査票 `outputs/docs/annotator_questionnaire.md`（職種・経験・アノテ経験・GT関与・操作環境・自己評価・実施予定・作業後質問）を作成
- [x] OSF 事前登録用ドラフト `outputs/docs/osf_preregistration.md`（OSF Prereg テンプレート構成・英文、experiment.json の sha256 記載）を作成
- [x] OSF に登録（ドラフトは空欄なし `47cbd7d`・エンバーゴ 3 日へ変更済み（未コミット）・登録手順は案内済み。`analysis_plan.md` 添付で提出、最初のアノテータ開始前。2026-09-15 の代行試行は OSF 障害で 2 回未完了（18:20 障害中、22:31 復旧表示だが API 20〜60s）→ 2026-09-16 09:08 着手判定合格・セッション失効でログイン依頼 → 15:42 ORCID 初回連携のメール確認待ちで未確立 → 17:11 ログイン確立を確認し、現行 8 ステップ版テンプレートへ全転記・`analysis_plan.md` 添付・Embargo 2026-09-19 設定まで完了。ユーザー承認後 Submit → **登録完了 https://osf.io/d7e2g**（2026-09-16 19:30、Pending Embargo Approval、エンバーゴ 2026-09-19 まで、関連プロジェクト https://osf.io/awgqf）。承認メールのリンクをクリック（未承認でも 48h で自動承認）。DOI はエンバーゴ明けに付与→ Methods に記載）
- [ ] `.playwright-mcp/`（Playwright MCP の作業ファイル、ルート直下・git 未追跡）を `.gitignore` に追加または削除
- [ ] 本番前に `run_server.bat` で再起動（experiment.json は起動時ロード）・`$Pass` を本番値へ
- [ ] 倫理審査の状況確認（患者画像二次利用＋アノテータの研究参加同意）
- [ ] 背景調査票を3名へ配布・作業前に回収し、`annotator` 名と紐づけて `outputs/` に保存

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
- [x] 事前解析計画に「描き直し画像（HITL で `shapes_deleted > 0`）の扱い＋描き直し率 vs 学習枚数を副次指標」を明記（`outputs/docs/analysis_plan.md` §3/§5.5）（2026-09-15）
- [x] 事前解析計画に「同一 `session_key` に複数試行がある場合の扱い」を明記（attempt 1 の完了記録を採用、`outputs/docs/analysis_plan.md` §3）（2026-09-15）
- [x] webapp 一式 + `annotator_guide.md` の未コミット分を実施前にコミット（`a5951a0`・31ファイル、患者データ/`.pth`/資格情報の非混入を機械確認）（2026-09-15）
- [x] GitHub へ push（`git push origin main` は自動モード分類器にブロック → ユーザーが `! git push origin main` を実行し `4716de3..a5951a0 main -> main` で成功）（2026-09-15）
- [ ] `scripts/webapp/run_server.ps1` の `$Pass` を本番値へ変更（変更はコミットしない）→ `run_server.bat` で再起動
- [x] 論文化リスクの対応状況を棚卸し（10件: ✅1 / ⚠️3 / ❌5 / ❓1）し「開始前必須 / 後から補える」に仕分けして提示（2026-09-15）
- [x] **開始前必須**: 事前解析計画書 `outputs/docs/analysis_plan.md` v1.0 を作成・コミット `e131aff`（2026-09-15）
- [x] `e131aff` を GitHub へ push（ユーザー実行 `! git push origin main` → `a5951a0..e131aff`）（2026-09-15）
- [x] 解析計画の登録先を判断: UMIN/jRCT は不要（健康アウトカム無し=非介入。倫理申請で一文確認）→ OSF Registries で事前登録を推奨、研究種別は「prospective blinded reader study using retrospectively collected images / MRMC」と表現（2026-09-15）
- [x] OSF 登録用の英文要約（問い・仮説・デザイン・主要評価項目・サンプルサイズ根拠・解析）を `outputs/docs/` に作成 → OSF に `analysis_plan.md` 添付で登録 — ユーザー判断待ち（`outputs/docs/osf_preregistration.md` 作成・`b7ded06` としてコミット・push `e131aff..b7ded06` 済み）（2026-09-15）
- [x] OSF ドラフトの空欄を記入（著者・ORCID／倫理承認 阪大病院倫理審査委員会 19492-7／エンバーゴ 1週間）→ コミット `3b9db4a`（2026-09-15）
- [x] `3b9db4a` を GitHub へ push（ユーザー実行 `! git push origin main`）（2026-09-15）
- [x] OSF ドラフトに倫理承認日（2022-09-20）を記入 → コミット `47cbd7d` → push（ユーザー実行。1回目は先頭スペースで未実行、再入力で成功。origin/main = `47cbd7d`）（2026-09-15）
- [x] 「OSF への登録はどのようにすればよい？」に回答（osf.io プロジェクト作成 → Registrations → OSF Preregistration テンプレート → 各節貼付 → `analysis_plan.md` 添付 → Embargo 1週間で提出 → DOI を Methods/Research_overview に記録）（2026-09-15）
- [x] 「subjective load を測定する実験は入っているか」に回答（Paas 9段階単一項目を全画像で必須回答・`effort` 列・`duration_sec` 非計上、質問票の作業後疲労感 1〜9 が補助。実装済み・変更不要）（2026-09-15）
- [x] OSF に登録（空欄なし・そのまま転記可）: `analysis_plan.md` 添付で提出 → https://osf.io/d7e2g（2026-09-16）
  - [x] エンバーゴを 3 日に変更（`outputs/docs/osf_preregistration.md`、未コミット）（2026-09-15）
  - [x] 2026-09-15 18:20 頃に Claude in Chrome で登録を試行 → OSF 障害（status.cos.io「Degraded performance」、api.osf.io 無応答）で中断。半日〜1日後に再試行（プロジェクト作成 → Registration → Prereg テンプレート転記 → `analysis_plan.md` 添付 → Embargo 3 days → 最終確認後 Register）→ **2026-09-16 19:30 登録完了 https://osf.io/d7e2g**（プロジェクト無しで直接 Registration 作成、関連プロジェクト https://osf.io/awgqf が自動生成）
  - [ ] 2026-09-15 22:31 に再試行 → status.cos.io は「All Systems Operational」だが `api.osf.io/v2/` が 60s タイムアウト ×2 / 200 (21.5s)、`myprojects` は 40s 以上スピナーのため再度見送り。**着手判定**: `curl api.osf.io/v2/` が 3 回連続 200 かつ 3 秒以内になったら Chrome 拡張（Browser 2 = この PC）で再開
  - [ ] 2026-09-16 09:08 に再試行 → 着手判定に**合格**（`api.osf.io/v2/` 0.38s / 1.29s / 0.24s、status は「Under Maintenance」表示のまま）→ Chrome 拡張（Browser 1 = この PC）で `osf.io/myprojects/` → `/dashboard` を開くと **`accounts.osf.io/login`（セッション失効）**。ユーザーに Chrome 上でログイン → 「ログインした」の合図を依頼（タブ 1046916182 は開いたまま）。合図後: プロジェクト作成 → Registrations → Prereg テンプレート転記 → `analysis_plan.md` 添付 → Embargo 3 days → 最終確認後 Register
  - [ ] 2026-09-16 15:42「ログインした」→ 確認すると **ORCID 初回連携のメール確認待ち**（`osf.io/external-login/email`、`/dashboard` は「Sign In With ORCID」フォームに戻る）= OSF セッション未確立。ユーザーへ (1) 確認メール（`kitaguchi@ophthal.med.osaka-u.ac.jp`）のリンクをクリック (2) フォームで氏名・メール入力 → Send (3) 既存アカウントならメール+パスワードで直接ログイン、を提示。ダッシュボード表示後に再度「ログインした」の合図 → 上記手順で再開
  - [x] 2026-09-16 17:11「verifyされたようです」→ `osf.io/dashboard` 描画でログイン確立を確認 → `registries/osf/new`（既存プロジェクト無し → OSF Preregistration）でドラフト `registries/drafts/6aaa4f9ade4622247cd26961` 作成 → 現行 8 ステップ（Metadata / Overview / Research Design / Sampling / Variables / Analysis Plan / Other / Review）に `osf_preregistration.md` を振り分け転記・`analysis_plan.md` を Analysis Plan 設問内で添付・Review → Register → Embargo 終了日 2026-09-19（最短 3 日）を設定（2026-09-16）
  - [ ] **Submit 直前でユーザー確認待ち**（取消不可。License は CC0 既定のまま=変更するなら Back で Metadata へ）。Yes → Submit → 登録 URL/DOI を取得
  - [ ] Submit 後: DOI を `outputs/docs/osf_preregistration.md`・`Research_overview.md`・論文 Methods 用メモに記載し、`Embargo: 3 days.` と併せてコミット
- [x] **開始前必須**: 背景質問票 `outputs/docs/annotator_questionnaire.md` を作成（2026-09-15）→ [ ] 3名へ配布・回答を `outputs/` に `annotator` 名と紐づけて保存
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

---

## アノテータID取り違え防止（2026-10-10）
- [x] 個人専用リンク（`?t=<token>`）: サーバがトークン→アノテータを解決。プルダウンは `test` のみ
- [x] 全API（run/session/predict/practice_gt/submit/abort）で ident を検証、他人名義の session_id 書込/削除を拒否
- [x] 完了状況・attempt をサーバの保存記録から判定（localStorage 廃止、全画像提出済み=完了）
- [x] リンク生成 `scripts/make_annotator_links.py`（トークンは `scripts/webapp/config/annotator_tokens.json`、git管理外）
- [x] 配布手順更新（`scripts/webapp/README_deploy.md`, `annotator_guide.md`, `run_server.ps1`）

### レビュー
- API 18項目 PASS（生ID/無効トークン 403、他人 session_id への submit/abort 403、途中セッションは未完了、
  記録の annotator は解決後の名前、test は従来通り）。Playwright: 個人リンクで名前表示・他人名非表示、
  無効リンクでエラー停止、コード入力で遷移、空 localStorage でもサーバ記録から進捗復元。検証記録は削除済み。
- 完了済セッションのやり直し（確認アラート・attempt 加算）は 06-19/20 の方針どおり本人リンク内でのみ温存。

## 練習の模範解答が負荷アンケートに覆われる問題(2026-10-10)
- [x] 練習時のみ画像下に「OK(模範解答を確認した)」ボタン(GT 読み込み完了まで無効・その間「確認OK」非表示)→ OK 後に負荷アンケート
- [x] 修正→再提出で再度ゲート、GT 取得失敗時はフェイルオープン、本番セッションは不変
- [x] 検証: ポート 8011 + Playwright(練習2・本番 S1)、新規記録なし
### レビュー
- 変更は `app.js`/`index.html`/`style.css` のみ。サーバ再起動不要(タブ再読み込みで反映)。未コミット
