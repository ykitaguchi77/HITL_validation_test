# 比較する2つの操作パスは計測を対称に仕込む(片側の計上漏れは条件間比較を壊す)

- type: lesson
- created: 2026-07-12
- tags: [instrumentation, experiment-design, metrics, hitl, frontend]

## 概要
効率比較実験で、同じ指標(例: 頂点編集数)が **複数のコードパス**から発生する場合、
どれか一つのパスに計測呼び出しを入れ忘れると、**その条件だけ指標がゼロ寄りに偏り、
条件間比較そのものが成立しなくなる**。指標の追加・レビューは「発生源ごと」ではなく
「指標ごとに全発生源を洗う」視点で行う。

## 背景・発見経緯
HITL アノテーション webapp で、ゼロから点を打つ scratch 描画(`tools.js` の `_polyClick`)は
点を置いても `metrics.vertexAdded()` を呼ばず、`shapeCreated` を1回計上するだけだった。
一方、既存ポリゴンへの点追加(`_extendClick`)は元から `vertexAdded()` を呼んでいた。
結果、**scratch は何点打っても `vertices_added=0`**、HITL は正しく計上される非対称が生じ、
「scratch vs HITL の修正労力」を頂点編集数で比較できない状態になっていた
(ローカル起動での動作確認中にユーザーが「頂点の追加がカウントされていない」と気づいて発覚)。

## 詳細
- 修正: `_polyClick` の初点と2点目以降の追加点の2箇所で `this.metrics.vertexAdded()` を呼ぶ(2行追加)。
- 検証: 実サーバ + Playwright でゼロから4点 → `vertices_added=4`・クラス別 `eyelid.vertices_edited=4`・
  `events[]` に `v+` 4件を確認(修正前は 0)。フロントのみの変更で no-cache ヘッダにより即反映。
- 一般化した予防策:
  1. 指標を実装/レビューするとき「この指標を生む操作は他に何があるか」を列挙し、**全発生源で同じ
     計測を呼ぶ**ことを確認する(片方の入口だけに入れない)。
  2. 特に **比較のアーム(scratch vs HITL、手動 vs AI支援 等)がコードパスで分岐**するときは、
     アームごとに指標の計上を対称化できているかを明示的にチェックする。
  3. 実データ収集前に、各アームで指標が期待どおり増えることを end-to-end で1度は目視/自動確認する
     (ゼロのままの列は「操作しなかった」なのか「計上漏れ」なのか事後に区別できない)。

## 適用場面
- 効率・労力の比較実験でクリック数・編集数・時間などを自前計測するとき。
- UI に「新規作成」と「既存編集」のように似た結果を生む別々の入口があるとき。
- HITL(初期予測を修正)と scratch(ゼロ描画)のように、比較の両アームが別ワークフローのとき。

## 関連
- Experimental_record/20260712.md
- [HITL/インタラクティブセグメンテーションの効率評価で使われる計測項目(既報サーベイ)](Knowledge/hitl-annotation-efficiency-metrics-from-literature.md)
- [CVAT風HITLアノーテーションwebappの実装知見](Knowledge/hitl-annotation-webapp-konva.md)
