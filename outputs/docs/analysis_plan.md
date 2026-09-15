# 事前解析計画書（Statistical Analysis Plan）
HITL アノテーション効率 vs 支援モデルの学習データ量 — 盲検・被験者内・Latin 方格実験

- 版: v1.0（データ収集開始前に確定）
- 作成日: 2026-09-15
- 関連: `scripts/prepare_experiment.py`（割付）、`scripts/webapp/backend/session.py`（記録列）、
  `Knowledge/hitl-blinding-and-confound-design.md`、`Knowledge/hitl-annotation-efficiency-metrics-from-literature.md`
- 本書はデータ収集前に固定し、変更はすべて日付付きで末尾「改訂履歴」に記す。

---

## 1. 研究の問い・仮説

**主問**: セグメンテーションモデルの学習枚数（＝モデル習熟度）が増えるにつれ、
そのモデル予測を初期値とする HITL アノテーションの労力はどう減り、どこで頭打ちになるか。

- **H1（効率）**: 画像1枚あたり作業時間は学習枚数の増加に伴い減少し、逓減する（log 枚数に対して概ね線形、
  または飽和曲線）。
- **H2（品質非劣性）**: いずれの HITL 条件でも最終アノテーションの GT 一致度は scratch に対して非劣性
  （§6 のマージン）。
- **H3（オートメーションバイアス）**: 低学習枚数条件では初期予測の質が低いほど最終品質が低い
  （初期予測への引きずり）。高枚数条件ではこの相関が消える。
- **H4（主観負荷）**: 主観的努力度（Paas）は学習枚数の増加に伴い低下する。

## 2. デザイン（固定済み・要約）

- アノテータ 3 名（GT 作成者は除外）、被験者内。
- 条件 9 = scratch + HITL 8（seg100/200/300/500/1000/1500/2000/2500、SegFormer-B1、患者リーク無し nested サブセット）。
- 画像 90 枚（test プール、患者単位で学習と分離）を 9 ブロック（正面 7 + 周辺 3）に分割、
  3×9 巡回 Latin 方格でアノテータ×ブロック→条件を割付（各画像は 3 名が異なる条件で作業）。
- 提示順: 練習 2（解析除外）→ Scratch（セッション0、非盲検）→ Session 1〜8（HITL 8 条件を盲検混合、
  各 10 枚）→ Session 9（既出 HITL 画像 10 枚を同一条件で盲検再掲）→ Scratch（2 回目、セッション0 と同一 10 枚）。
- 1 名あたり本解析対象: 90（主）+ 10（HITL 再掲）+ 10（scratch 再掲）= 110 画像。

## 3. データソースと前処理

- 入力: `outputs/results/*/summary.csv` を全連結（必要に応じ `records.jsonl` の `events[]`/`heartbeats[]`）。
- 除外:
  1. `is_practice == True`、`annotator == "test"`
  2. 中断セッション（フォルダ自体が削除されるため自動的に不在）
  3. **やり直し（`attempt ≥ 2`）の扱い: 同一 `annotator × session_key` に複数試行がある場合、
     `attempt == 1` の完了記録を採用する**（やり直しは記憶効果で汚染されるため）。ただし attempt 1 が
     10 枚未完（記録が途中で止まっている）場合は最新の完了試行を採用し、その旨を報告する。
  4. 1 画像の `duration_sec` が該当アノテータ×条件群の中央値の 5 倍を超える、または `heartbeats[]` に
     60 秒超の欠落がある記録は「離席疑い」として感度解析で除外（主解析には含める）。
- 派生変数:
  - `log_n = log10(train_size)`（HITL のみ）。scratch は `train_size = NA`。
  - `redraw = shapes_deleted > 0`（HITL で予測を捨てて描き直したか）。
  - クラス別時間 `{k}_time_sec` は既定選択クラス（eyelid）に初期の全体観察時間が乗る。
    クラス別解析では `events[]` から「最初の操作までの時間」を eyelid から差し引いた補正版も併記する。
  - 境界指標（`{k}_hd95`, `{k}_assd`, `{k}_boundary_f1`）は px 単位。画像解像度は記録の `native_size` を使う。

## 4. 評価項目

| 区分 | 変数（summary.csv 列） | 備考 |
|---|---|---|
| **主要** | `duration_sec` | 画像あたり作業時間。推論待ち・一時停止・確認画面・負荷回答は非計上 |
| 副次（労力） | `total_clicks`, `vertices_added/moved/deleted`, `mouse_distance_px`, `undo_count`, `time_to_first_action_sec`, `idle_time_sec`, `redraw` | |
| 副次（主観） | `effort`（Paas 1–9） | |
| 副次（品質） | `mean_dice`, `{k}_dice`, `{k}_hd95`, `{k}_assd`, `{k}_boundary_f1` | k ∈ eyelid/iris/pupil |
| 副次（修正量） | `{k}_correction_dice`（初期予測 vs 最終、1.0=無修正）, `{k}_area_change` | HITL のみ |
| 補助 | `gaze`, `ecc`, `order_in_session`, `session_index`, `timestamp`, `paused_time_sec` | 共変量・感度解析 |

## 5. 統計解析

### 5.1 記述統計
条件別（scratch, 100, …, 2500）に主要・副次指標の中央値 [IQR] と平均 (SD)、アノテータ別・視線別の層別表。
モデルの held-out Dice（`outputs/models/heldout_dice.csv`）を並記し、横軸を「学習枚数」と「モデル Dice」の両方で図示。

### 5.2 主解析（H1）: 用量反応の混合効果モデル
HITL 8 条件（scratch を除く）を対象に

```
log(duration_sec) ~ log_n + gaze + order_in_session + session_index
                    + (1 | annotator) + (1 | image_id)
```

- 推定: REML、Satterthwaite 自由度（R: lme4 + lmerTest、または Python statsmodels MixedLM）。
- アノテータは水準 3 のため、**ランダム効果が退化（分散 0）する場合は固定効果に切り替える**ことを事前に決めておく。
  結論は「この 3 名について」と限定して記述する。
- `log_n` の係数（1 log10 単位あたりの時間変化率）と 95% CI を主結果とする。
- 飽和点の推定: 上記に加え、非線形（指数減衰 `a + b·exp(−n/τ)`、または区分線形）を当てはめ、
  AIC で比較。減衰モデルが優れる場合は τ（飽和スケール）と、時間が漸近値の 10% 以内に入る枚数を報告。
- 条件間の個別対比は用量反応の補助として、隣接条件ではなく **scratch 対各 HITL 条件**および
  **seg100 対 seg2500** のみを事前指定（Holm 補正）。

### 5.3 scratch 基準との比較
- scratch の基準値は**2 回目（習熟後）**を主とし、1 回目との差を「順序（習熟）効果」として別途報告する
  （同一画像ペア 30 組の対応あり混合モデル: `log(duration) ~ repeat + (1|annotator) + (1|image_id)`）。
- HITL 各条件 vs scratch（2 回目）の時間比（幾何平均比）と 95% CI。
- 感度解析として scratch 1 回目を基準にした結果も併記（HITL 効果が保守的か過大かの範囲を示す）。

### 5.4 品質非劣性（H2）
- 主: `mean_dice`、副: クラス別 Dice・境界指標。
- 5.2 と同じ固定・ランダム効果で `mean_dice ~ condition + ...` を当てはめ、各 HITL 条件 − scratch（2 回目）の
  差の 95% CI 下限が **−0.01（Dice）** を上回れば非劣性とする。境界指標は HD95 差の上限 **+2 px** を非劣性マージンとする
  （2 px は本実験の許容幅 Boundary-F1@2px と整合）。

### 5.5 オートメーションバイアス（H3）
- HITL のみ: `mean_dice ~ initial_quality × log_n + gaze + (1|annotator) + (1|image_id)`、
  `initial_quality` は初期予測の GT Dice（`records.jsonl` の `initial` から再計算、または `correction_dice` の逆数関係で代替）。
- 交互作用が有意（初期予測の質と最終品質の相関が低枚数で強い）なら引きずりありと解釈。
- 補助: `redraw` 率 vs `log_n` のロジスティック混合モデル。

### 5.6 主観負荷（H4）
- `effort ~ log_n + gaze + (1|annotator) + (1|image_id)`（順序尺度だが 9 段階のため線形混合モデルを主、
  累積リンク混合モデル（ordinal::clmm）を感度解析）。

### 5.7 再現性
- HITL 再掲（Session 9）と初回の同一画像・同一条件ペア（30 組）: 作業時間の ICC(2,1)、最終マスクの
  ペアワイズ Dice（個人内一致）。
- scratch 再掲（Scratch 2 回目）: 同様に ICC とペアワイズ Dice。両者を並べて報告。

### 5.8 クラス別解析
- 主要・副次のクラス別版（`{k}_time_sec`（補正版併記）, `{k}_clicks`, `{k}_vertices_edited`, `{k}_dice`, `{k}_hd95`）で
  5.2 を繰り返し、眼瞼（ポリゴン）と虹彩・瞳孔（楕円）で用量反応の形が異なるかを記述する。探索的。

### 5.9 多重性
- 検証的検定は主要評価項目に対する `log_n` の係数（5.2）1 つ。
- 副次評価項目は 95% CI を中心に記述し、p 値は名目値として報告する（探索的）。事前指定対比のみ Holm 補正。

### 5.10 欠測・逸脱
- 提出時の 3 クラス必須ガードにより欠測クラスは生じない。`effort` 未回答は生じない（モーダル必須）。
- 一時停止（`paused_time_sec`）が `duration_sec` を超える画像は注意フラグとして報告。
- 計画からの逸脱はすべて論文の Supplement に列挙する。

## 6. 事前固定パラメータ

| 項目 | 値 |
|---|---|
| 主要評価項目 | `duration_sec`（log 変換） |
| 主要検定 | 5.2 の `log_n` 係数、両側 α = 0.05 |
| 非劣性マージン | Dice −0.01、HD95 +2 px |
| アノテータ効果 | ランダム→退化時は固定（事前決定） |
| scratch 基準 | 2 回目（主）、1 回目（感度） |
| attempt の扱い | attempt 1 完了記録を採用 |
| 外れ値 | 主解析は含める、感度解析で除外（§3 基準） |
| 解析ソフト | R ≥ 4.3（lme4/lmerTest/ordinal）または Python（statsmodels）。スクリプトは `scripts/analysis/` に置き、乱数シードは 42 |

## 7. 図表計画

1. 研究デザイン図（Latin 方格・セッション列）
2. モデル held-out Dice vs 学習枚数（8 点）
3. 作業時間 vs 学習枚数（個人別点 + 混合モデル推定曲線、scratch 1 回目/2 回目を水平線で併記）
4. 副次労力（クリック・頂点編集・主観負荷）vs 学習枚数（パネル）
5. 品質（mean Dice・HD95・Boundary-F1）vs 学習枚数、非劣性マージン線
6. 初期予測の質 vs 最終品質（条件別散布、H3）
7. 再現性（初回 vs 再掲の Bland–Altman または散布）
- 表 1: アノテータ背景、表 2: 条件別記述統計、表 3: 混合モデル推定値、Supp: クラス別・感度解析

## 8. 限界として記載する事項（事前認識）
- アノテータ 3 名（一般化の限界）。
- GT 作成者は 1 名で、モデルはその GT で学習しているため HITL 条件は GT のスタイルに寄りやすい（境界指標併記で緩和、
  人間間ばらつきの基準は本実験では未取得）。
- 学習曲線は各枚数 1 run。
- scratch は非盲検。順序効果は 2 回目 scratch で推定するが、末尾の疲労効果は分離できない（保守的方向）。
- 推論待ち時間は計測から除外しているが、待ち時間の長短から条件を推測できる理論的可能性は残る（実測 0.07–0.17 s、実害小）。

## 改訂履歴
- v1.0 2026-09-15: 初版（データ収集前）。
