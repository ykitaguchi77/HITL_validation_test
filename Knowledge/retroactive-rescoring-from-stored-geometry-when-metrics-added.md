# 採点指標を後から足したら、保存済みの図形(records.jsonl)から現行コードで再採点し `summary_rescored.csv` を並置する

- type: technique
- created: 2026-09-20
- tags: [metrics, rescoring, records, reproducibility, user-study, HITL, analysis-pipeline]

## 状況
ユーザースタディの記録 webapp は、セッションごとに **図形そのもの(ポリゴン・楕円パラメータ)を `records.jsonl`** に、
**採点済み集計を `summary.csv`** に書く。パイロットや初期セッションを記録した後で、採点コード(`scoring.py`)に
新しい品質指標(楕円中心誤差・径誤差・MRD1/MRD2/PFH など)を追加する必要が出た。

## 問題
- `summary.csv` は採点「結果」しか持たないので、新指標の列は既存セッションでは空になる。
- 記録済みセッションをやり直すことはできない(被験者の時間・順序効果・学習効果が壊れる)。
- 既存 `summary.csv` を上書きすると「記録時の採点」と「後付け採点」の区別が消える。

## 解決策・手順
1. **図形を必ず保存しておく**(前提): `records.jsonl` に提出アノテーション(`annotation`)と初期提案(`initial`)・`native_size`・`n` を残す。
   集計値だけ保存していたら遡及は不可能。
2. **再採点スクリプトを別に置く**(`scripts/analysis/rescore_records.py`):
   `records.jsonl` を読み、`score_annotation(filename, annotation, w, h, initial=initial if n else None)` を現行コードで呼び直し、
   行動指標(時間・クリック・頂点数)はレコードからそのまま流用、GT 比較だけ再計算。webapp の `session.CSV_COLS` と `_flatten` を
   そのまま import して**同じ列定義で** `summary_rescored.csv` を各セッションフォルダに書く(`summary.csv` は触らない)。
3. **解析側が優先読込する**: `fit_models.py` の読み込みで `summary_rescored.csv` があればそれを、無ければ `summary.csv` を使う(2 行)。
   これで指標追加前後のセッションを一つの表で扱える。
4. **提案側にも同じ指標を同梱してハッシュを更新**: 事前計算した提案 JSON に同じ指標を付け直し、提案 JSON → 割付 JSON → 計画書/OSF の
   ハッシュ連鎖を更新する([[precomputed-proposals-import-consumer-postprocessing]])。割付項目が不変であることは先頭項目などで確認する。
5. **スモークテスト**: GT を既知量だけずらした提出(中心 +3 px・回転 +10°)で期待値が返ることと、楕円が無い提出(手動画像)で None になり落ちないことを確認してからサーバを再起動する。

## 注意点・落とし穴
- `--glob` でパイロット(`test_s0*`)だけ対象にするなど、範囲を絞れるようにしておく。
- `extrasaction="ignore"` で `CSV_COLS` に無いキーを捨てるので、列を追加したら `CSV_COLS` 側も必ず更新する(記録時の列と再採点の列が同じになる)。
- 記録時とコードが変わっているので、旧指標(Dice/ASSD)が再採点で一致することも一度は確認する(今回は同じ関数なので一致)。
- 本番中に指標を足す場合は、事前登録文書に「副次指標は記録済み図形から遡及算出」と書いておくと後出しに見えない。

## 関連
- [[ellipse-structure-accuracy-report-center-radius-alongside-boundary-metrics]](追加した指標の中身)
- [[precomputed-proposals-import-consumer-postprocessing]](ハッシュ連鎖の更新)
- [[symmetric-instrumentation-across-comparison-arms]](提案側にも対称付与)
- [[first-real-session-column-audit-zero-vs-missing]](列の 0 と欠損の区別)

## 出典
- Experimental_record/20260920.md
