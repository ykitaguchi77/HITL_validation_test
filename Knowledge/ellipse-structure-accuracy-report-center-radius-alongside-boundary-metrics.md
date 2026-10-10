# 円・楕円で表す構造(虹彩・瞳孔)の精度は、マスク流儀の境界距離だけでなく既報が使う「中心誤差・径誤差(・楕円 IoU)」と臨床量(MRD1/MRD2/PFH の mm)を副次に併記する

- type: pattern
- created: 2026-09-20
- tags: [metrics, ellipse, iris, pupil, eyelid, MRD, literature, non-inferiority, user-study, HITL]

## 要点
セグメンテーション研究の標準指標(Dice / ASSD / HD95)は「マスク流儀」で、虹彩・瞳孔のような**円・楕円で表す構造**では
既報の多くが別の基準で精度を語っている。既報と比較可能にし、かつ「ばらつきの正体」を分解できるように、
**主指標は境界距離のまま動かさず、構造の種類に合った既報流儀の指標を副次に加える**。

## 既報の流儀(分野別)
| 分野 | 主に使う基準 |
|---|---|
| 虹彩認識(バイオメトリクス) | NICE.I/II の E1(画素分類誤り率)・E2(FP/FN 均衡)= マスク流儀。円近似時代(Daugman・Hough 円)は **中心座標誤差(px)+ 半径誤差(px)** を limbus・瞳孔縁それぞれで報告 |
| 瞳孔検出(視線計測・pupillometry) | **中心のユークリッド誤差(px)** と **「誤差 ≤ 5 px の割合(検出率)」**(ExCuSe / ElSe / PuRe / PupilNet、LPW・Świrski)。楕円まで評価する TEyeD 等は **楕円 IoU + 中心誤差 + 軸長・回転角誤差**。径は直径絶対誤差(px/mm)+ Bland–Altman |
| 眼科臨床(前眼部・外眼部写真の計測) | 中心ずれ(mm)・直径誤差(mm)・方法間の **Bland–Altman(バイアス・一致限界)・ICC**。眼瞼は **MRD1 / MRD2 / PFH** を mm で比較し「±0.5 mm 以内の割合」で精度を述べる。px→mm は **HVID(角膜横径 ≈ 11.7 mm)** で換算 |
| 楕円近似そのもの(一般 CV) | 楕円 IoU(Dice)・中心誤差・長軸/短軸誤差・回転角誤差・境界距離(Hausdorff)。円に近いほど回転角は不定 → 離心率で重み付けするか IoU に任せる |

## 適用パターン
1. **主指標は変えない**: 非劣性の主検定(ASSD)を差し替えると事前登録・検出力計算が全部動く。副次に追加する。
2. **構造ごとに分解する**: 「隠れた部分を含む楕円」(虹彩)は境界距離の残差の大半が**隠れ側(上下方向)の半径の解釈差**で説明できる可能性が高い。
   中心誤差 / 水平径誤差(見えている側)/ 垂直径誤差(隠れ側)に分けると、被験者間ばらつきが「見えていない部分の推定」由来か「縁の置き方」由来か判別できる。
3. **臨床量に翻訳する**: 眼瞼ポリゴン + 瞳孔中心 → MRD1 / MRD2 / PFH(px)→ HVID で mm 換算。「臨床的に意味のある誤差(±0.5 mm)」で語れると眼科医の査読者に最も伝わる。換算の仮定(HVID 固定値)は明記する。
4. **比較アーム間で対称に付与する**: 事前計算した AI 提案側にも同じ指標を付け、最終アノテーションと同じコードで採点する([[symmetric-instrumentation-across-comparison-arms]])。
5. **遡及算出できる形で記録する**: 図形そのもの(records.jsonl のポリゴン・楕円パラメータ)が保存されていれば、後から指標を足しても既存セッションを再採点できる。summary.csv の集計値だけでは足りない。
6. **非劣性マージンの決め方と連動させる**: 構造別 δ_k をどの指標で定義するか(境界距離か中心+径か)は、指標追加と同時に事前登録前に一括で決める([[pilot-variance-recheck-of-preregistered-power]])。

## 背景(本プロジェクトでの出所)
pilot 30 枚で虹彩の ASSD 残差 SD が 3.1 px(眼瞼 0.76・瞳孔 1.79)と突出し、非劣性の検出力が虹彩だけ余裕が少なかった。
「中心や半径など別の metric では既報は何を基準にしているか」という問いから、上表を整理し、
`scripts/webapp/backend/geometry.py`(楕円は `cv2.fitEllipse`)の採点に中心誤差・長軸/短軸誤差・回転角誤差・楕円 IoU、画像単位に MRD1/MRD2/PFH を副次指標として追加する案を提示した。

## 関連
- [[boundary-metrics-2d-cv2-distancetransform]](現行のマスク流儀の実装)
- [[hitl-annotation-efficiency-metrics-from-literature]](効率側の既報サーベイ)
- [[symmetric-instrumentation-across-comparison-arms]]
- [[pilot-variance-recheck-of-preregistered-power]]

## 出典
- Experimental_record/20260920.md

## 追記 (2026-09-20) — 実装と pilot 再採点で分かったこと
- 出典: Experimental_record/20260920.md
- ユーザー承認で `scripts/webapp/backend/scoring.py` に実装した。列: `{iris,pupil}_center_err/_center_dx/_dy/_major_err/_minor_err/_hdiam_err/_vdiam_err/_rot_err`、
  提案側 `{k}_prop_center_err/_prop_major_err`、画像単位 `hvid_px_gt`・`mrd1/mrd2/pfh_mm`・`*_gt_mm`・`*_err_mm`。楕円 IoU は Dice と重複するので入れなかった。
- **水平/垂直径は回転楕円の軸投影**で出す(`hdiam = 2·hypot(rx·cosθ, ry·sinθ)`, `vdiam = 2·hypot(rx·sinθ, ry·cosθ)`)。長軸/短軸誤差だけだと「どちら向きに大きいか」が消える。
- **mm 換算のスケールは GT 側の虹彩水平径(HVID 11.7 mm)を提出側・GT 側で共通に使う**。提出側の虹彩径から換算すると、虹彩の描き方の誤差が MRD 誤差に混入して眼瞼の評価にならない。
- MRD1/MRD2/PFH は眼瞼マスクの「瞳孔中心を通る列」の上縁・下縁で定義(瞳孔中心が列外・眼瞼なしなら None)。
- 回転誤差は円に近い構造では意味を持たない(手動でも 28°)。参考列として残し、解析では使わない。
- pilot 再採点(開発者手動 10 枚)の分解結果: 虹彩中心誤差 4.6 px、**水平径 +3.7 px / 垂直径 −0.2 px** → 当初の仮説「虹彩 ASSD 残差は隠れ側(垂直)の解釈差」ではなく、
  **見えている側の径を GT より大きく描く系統差**が主因だった。分解してみないと原因の向きは当てられない。|MRD1 誤差| 0.14 mm・|PFH 誤差| 0.07 mm で臨床許容 ±0.5 mm を大きく下回る。
- 既存セッションは [[retroactive-rescoring-from-stored-geometry-when-metrics-added]] で遡及算出した。
