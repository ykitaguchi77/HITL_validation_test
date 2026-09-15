# シード固定の実験割付へ後から要素を足すときは専用RNGを使う(既存割付を不変に保つ)

- type: pattern
- created: 2026-07-11
- tags: [experiment-design, reproducibility, rng, random-seed, python]

## 教訓
シード固定(`random.Random(SEED)`)で生成した実験割付(画像→セッション割当など)に、
**後から追加のランダム抽出(例: 再掲画像のサンプリング)を足すとき、共有 RNG から引いてはいけない**。
共有 RNG のストリームを1回でも余分に消費すると、それ以降の全乱数がずれて
**既存の割付が丸ごと変わってしまう**(=すでに検証・合意済みの設計が無言で崩れる)。

## やり方
- 追加分には **専用のRNGインスタンス**を立てる: `rng_repeat = random.Random(SEED + 定数)` など、
  既存ストリームから独立させる。
- 変更後に**割付の不変性を assertion で機械確認**する(既存部分のハッシュ/件数/内容一致を audit スクリプトで)。
  本プロジェクトでは `prepare_experiment.py` の audit が全 assertion PASS で既存90枚・練習セッション不変を保証した。

## 適用場面
- 生成済み・配布済みの実験計画(experiment.json 等)に、セッション・条件・サンプルを追加するとき。
- テストデータのシード固定フィクスチャに項目を足すときも同じ(既存ケースのスナップショットを壊さない)。

## 出典
- `scripts/prepare_experiment.py`(Session 9 の再掲5枚サンプリングに専用RNG)
- Experimental_record/20260711.md

## 更新 (2026-09-15)
- 出典: Experimental_record/20260915.md
- 2回目の適用: 末尾に「Scratch（2回目）」(セッション0と同じ10枚の再シャッフル)を追加する際も
  `random.Random(SEED + 2000 + ai)` の専用 RNG を立て、メイン `rng` の消費順を変えずに済ませた
  (Session 9 用は `SEED + 1000 + ai` 系。**追加要素ごとにオフセット帯を分ける**と後から更に足せる)。
- 不変性の確認は audit の assertion だけでなく、**再生成前に旧 JSON をバックアップし、新旧を構造比較**
  (`blocks`/`practice`/`latin_square`/`models`、各アノテータの `sessions[0..N]` の完全一致、末尾のみ追加)
  するのが確実。audit は「設計上の性質」を、diff は「既存割付が1ビットも動いていないこと」をそれぞれ保証する。
- 追加セッションの性質(最終位置・非HITL・画像集合==元セッション・順序が異なる・index 連番)を
  audit に**新しい assertion として足す**ことで、以後の再生成でも設計意図が機械的に守られる。
- 消費者側(backend/frontend)が完全に config 駆動なら、生成スクリプト+配布資料の変更だけで済み、
  実 API(一覧・セッション取得・predict・submit→CSV)で end-to-end 確認できる。
