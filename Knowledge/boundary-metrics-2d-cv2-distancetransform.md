# 2Dマスクの境界指標(HD95/ASSD/Boundary-F1@tol)を cv2.distanceTransform だけで実装する

- type: technique
- created: 2026-07-11
- tags: [segmentation, metrics, HD95, ASSD, boundary-f1, surface-dice, opencv, no-scipy]

## 背景
Dice/IoU は重なりを見るが境界の正確さを見落とすため、既報([[hitl-annotation-efficiency-metrics-from-literature]])では
HD95・ASSD・Surface Dice at tolerance の併記が標準。定番実装は scipy(`distance_transform_edt`)や
MedPy・surface-distance ライブラリだが、**依存を増やしたくない webapp バックエンドでは cv2 だけで足りる**。

## 実装の要点
1. **境界画素の抽出**: バイナリマスクとその erosion の XOR(または輪郭描画)で境界画素集合を得る。
2. **距離場**: 相手側マスクの境界を 0、それ以外を 1 にした画像へ `cv2.distanceTransform(src, cv2.DIST_L2, ...)`
   をかけると「各画素から相手境界までの最近距離」の場が得られる。
3. **片方向距離のサンプリング**: 自分の境界画素位置で距離場を引くと d(A→B) の距離配列。逆向きも同様に。
4. 指標の合成:
   - **HD95** = 双方向の距離配列を結合して 95 パーセンタイル
   - **ASSD** = 双方向の距離配列の平均
   - **Boundary-F1(=Surface Dice)@τ** = precision(A境界のうち ≤τ の割合)と recall(B境界のうち ≤τ)の調和平均
5. **エッジケース**: どちらかのマスクが空なら距離が定義できない → `None` を返して解析側で除外(0 や inf で埋めない)。

## 検証方法(判別性のスモークテスト)
合成マスクをずらして期待値と突き合わせる:
- 同一マスク → HD95=0 / ASSD=0 / F1=1.0
- 1px 平行移動 → F1@2px=1.0(許容幅内は一致)
- 5px 平行移動 → HD95=5、F1@2px=0.5
- 空マスク → すべて None
この4点が出れば tolerance の向き・境界抽出のバグはほぼ排除できる。

## 注意
- 既報の HD95/ASSD は 3D ボクセルの物理間隔(mm)前提のものが多く、2D 画像では**ピクセル許容幅への読替**が必要
  (本プロジェクトは臨床判断で「≤2px を一致」= Boundary-F1@2px、HD95/ASSD は生の px 値で併記)。
- 保存済みのポリゴン/マスクからオフライン計算できるので UI 変更は不要。提出時のオンライン計算に足すのも軽い。

## 適用場面
- scipy を入れたくない環境(推論用の最小 FastAPI バックエンド等)で境界品質指標が要るとき。
- Dice だけの評価に対して査読者から Hausdorff 系の追加を求められたとき(保存データから後付け可能)。

## 出典
- 実装: `scripts/webapp/backend/scoring.py`(全3クラス HD95/ASSD/Boundary-F1@2px)
- Experimental_record/20260711.md

## 更新 (2026-07-11)
- 記録: Experimental_record/20260711.md
- **対象クラスを絞る必要は無い**: 当初はアノテーター負荷を理由に眼瞼のみで計算していたが、
  境界指標は**保存済みマスクからのオフライン計算でアノテーター負担はゼロ**。負荷を理由に対象を
  絞るのは誤りで、全クラス(eyelid/iris/pupil)で算出する形へ拡張した。オフライン指標一般に言える教訓。
- **楕円もマスク境界で測る**: 虹彩/瞳孔は楕円(5パラメータ)だが、パラメータを直接比較せず
  `cv2.ellipse` で塗りつぶし→マスク境界のずれを測れば、眼瞼(ポリゴン)と**同じ土俵**で扱える。
- **実装は per-class 共通カラムに**: 特定クラス名をハードコード(`eyelid_hd95` 等)せず、
  クラスをループして `{k}_hd95`/`{k}_assd`/`{k}_boundary_f1` を生成する方が素直で拡張に強い。
- **注意(固定許容幅の副作用)**: Boundary-F1@τ は固定 px 許容幅ゆえ**小さい構造(瞳孔)ほど甘めに出る**。
  構造サイズでスケールしない方針なら、瞳孔では HD95/ASSD の絶対 px 値の方が解釈しやすい。
