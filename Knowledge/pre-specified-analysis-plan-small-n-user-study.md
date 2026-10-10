# 少人数・被験者内ユーザースタディの事前解析計画書は「主検定1つ+基準条件+データ処理規則」を先に固定する

- type: technique
- created: 2026-09-15
- tags: [statistical-analysis-plan, pre-registration, mixed-effects, user-study, HITL, paper-writing]

## 要点
被験者3名程度の被験者内・Latin 方格実験では、条件数(9)に対して人数が少なく、
「どの比較を主結果にするか」を後決めすると多重性と選択的報告の疑いを避けられない。
データ収集前に **(1) 主要評価項目と主検定を1つに絞る、(2) 基準条件をどの記録にするか、
(3) やり直し・外れ値・派生変数などのデータ処理規則** を文書として固定し、日付と版番号を付けて
コミットしておく。内容が会話で決まっていても、文書化されるまでは「未固定」と扱う。

## 適用場面 / 状況
- 再収集コストが高い(1人あたり数時間)人間実験の開始直前。
- 条件が順序尺度(学習枚数 100〜2500 など)で、総当たり比較より用量反応の方が問いに合うとき。
- 本プロジェクト: `outputs/docs/analysis_plan.md` v1.0(2026-09-15)を `e131aff` でコミット。

## 内容
1. **仮説を番号付き(H1〜H4)で列挙**し、各仮説に対応する解析節を1つずつ置く。
2. **主検定は1つ**: `log(duration) ~ log10(train_size) + 共変量 + (1|annotator) + (1|image)` の枚数係数(α=0.05)。
   条件間の総当たり検定はしない。飽和点は指数減衰モデルで別途推定(探索的)。
3. **基準条件の記録を明示**: scratch は「2回目(習熟後)」を主、「1回目」を感度解析。順序効果は 1回目−2回目 として報告。
4. **非劣性マージンを測定分解能と整合させる**: Boundary-F1 を @2px で計算しているなら HD95 の許容も +2 px、
   Dice は −0.01 のように、既存の指標設定から自然に導ける値にする。
5. **データ処理規則**を先に書く: 除外(練習・test アノテータ)、やり直しは `attempt==1` 完了記録を採用(記憶効果を避ける)、
   離席疑いは主解析に含めて感度解析で除外、派生変数(`log_n`、`redraw = shapes_deleted>0`)の定義、
   計測の既知バイアス(既定クラスに初期観察時間が乗る)の補正方法。
6. **ランダム効果の退化時の扱いを事前決定**(アノテータ3名では分散推定が 0 に落ちやすい → 固定効果へ)。
7. 多重性の方針(検証的1つ+事前指定対比のみ Holm、他は 95% CI 中心の探索的)、図表計画、
   事前に認識している限界、改訂履歴欄を含める。
8. 記録列名は**実装(`session.py` の `_flatten`)を読み直して一致させる**。計画書が実在しない列を参照すると解析時に崩れる。

## 注意点・落とし穴
- 被験者の**背景情報(職種・経験年数・アノテーション経験・GT 作成への関与)は webapp のログに乗らない**。
  計画書と同時に質問票を作り、作業前に回収して `annotator` 名と紐づけて保存する。
  作業後質問に「モデルの種類を推測できたか」を入れると、盲検の自己申告チェックが Methods に書ける。
- 「計画書は書けばよい」ではなく、**日付付きで VCS にコミットして時点を証明できる状態**にする。
- 収集開始後に変更した場合は改訂履歴に残し、Supplement に逸脱として列挙する(計画書に自ら書いておく)。

## 関連
- Experimental_record/20260915.md(追記10: 作成経緯、追記9: 「開始前必須」への仕分け)
- Knowledge/pre-launch-paper-risk-triage.md(この文書が必要と判定した棚卸しパターン)
- Knowledge/hitl-blinding-and-confound-design.md(基準条件・順序効果の設計背景)
- Knowledge/per-class-effort-attribution-by-active-class.md(クラス別時間の既知バイアスと補正)
- outputs/docs/analysis_plan.md, outputs/docs/annotator_questionnaire.md

## 追記 (2026-09-15)
- 出典: Experimental_record/20260915.md(追記11)
- **登録先の選び方**: アノテータ(reader)への条件割付は「健康関連アウトカム」を扱わないため、ICMJE 定義の臨床試験にも
  国内指針の「介入研究」にも通常は該当せず、**UMIN-CTR/jRCT 登録は不要**(委員会が求めた場合は UMIN「その他」区分が受け皿)。
  ただし該当性は倫理委員会の判断なので、申請書に「介入研究ではない」旨を一文入れて確認しておく。
- 査読で効くのは「データ収集前に固定した第三者証明」。VCS コミットは自己管理下で証明力が弱いので、
  **OSF Registries(無料・タイムスタンプ・エンバーゴ最長4年)に `analysis_plan.md` を添付して事前登録**し、論文に登録 URL を書く。
  代替は AsPredicted。コミットハッシュは補助証拠と位置づける。
- **研究種別の表現**: 行動データはこれから収集するので「前向き」だが、画像はレトロスペクティブ収集なので
  "prospective clinical study" は誤解を招く。
  "a prospective, within-subject, blinded reader study using retrospectively collected images" か、
  **multi-reader multi-case (MRMC) design** と書くと設計が査読者に即座に伝わる(全 reader が全 case を読む設計に限る)。

## 追記 (2026-09-15)
- 出典: Experimental_record/20260915.md(追記12)
- **OSF 登録ドラフトはテンプレートの節見出しをそのまま Markdown に写して書く**(Title/Hypotheses/Study type/Blinding/
  Study design/Randomization/Existing data/Sample size (+rationale)/Stopping rule/Variables/Indices/Statistical models/
  Inference criteria/Data exclusion/Missing data/Exploratory/Other)。フォームへ節ごとに貼るだけで済み、
  `analysis_plan.md` との対応も節単位で追える。記入待ち箇所は `[ ]` で明示(著者・IRB 番号・エンバーゴ)。
- **非公開の割付ファイルは「ハッシュだけ」を登録文書に埋め込む**: 患者IDを含む `experiment.json` は公開できないが、
  `sha256sum` の値と日付を Randomization 節に書けば、ファイルを出さずに「割付が登録時点で固定されていた」ことを
  第三者検証可能にできる(後日ファイルを監査者へ見せればハッシュ照合で証明)。seed とスクリプト名も併記する。
- Study type は "experiment / not a clinical trial" と明記し、Existing data 節で「画像・GT・モデルは既存、
  行動データは未収集」を切り分けて書くと、レトロ画像+前向き reader study の性格が誤解されない。
- 本プロジェクト: `outputs/docs/osf_preregistration.md`(英文・191行、コミット `b7ded06`)。
- 作業メモ: 長い英文を `cat > f <<'EOF'` で書くと bash が `unexpected EOF while looking for matching '` で落ちることがある
  (Bash ツール経由の長文 heredoc は不安定)→ ファイル生成は Write ツールに切り替えるのが早い。

## 追記 (2026-09-15, OSF 登録手順)
- 参照: Experimental_record/20260915.md(追記15)
- ドラフトの `[ ]` を全部埋めてから登録する(本プロジェクトは著者/ORCID・IRB 19492-7・承認日 2022-09-20・エンバーゴ1週間で `47cbd7d`)。
- 具体的な登録手順(プロジェクト作成→OSF Preregistration テンプレート→添付→Register→Embargo)と注意点は
  [[osf-preregistration-for-non-clinical-reader-study]] に集約した。

## 追記 (2026-09-19, 解析コードと検出力をデータ収集前に検証)
- 出典: Experimental_record/20260919.md(Step F)
- 解析計画 v2 と同時に **解析スクリプト本体(`fit_models.py`)と検出力シミュレーション(`power_sim.py`)を書き、合成データで植込み効果を回復できるか**を先に確認した
  (H1 傾き −0.05 を植えて −0.047、automation bias 0.2 を植えて 0.19)。これで「計画に書いたモデルが実データの列でそのまま走る」ことと
  「主検定が計画どおりの向き・スケールで効く」ことがデータ前に保証され、計画書の検出力欄も実数(H1 0.99 / H2 0.96)で埋まる。
- 検出力は設計パラメータ(被験者数・スロット・グループ)を入力にして、比 0.6/0.7/0.8 × SD 0.4/0.5/0.6 のグリッドで出しておくと、
  被験者が減った場合の再計算が 1 コマンドで済む。
- statsmodels の MixedLM は小 n で `ConvergenceWarning` を多発する。スモーク実行では `2>/dev/null | grep -v Warn` で本体出力だけ見る。
