# プロジェクト指示

## Workflow

### Plan Mode Default
- 3ステップ以上または設計判断を伴うタスクはプランモードで開始
- 問題発生時は即停止して再計画(無理に進めない)
- 検証ステップをプランに含める

### Subagent Strategy
- 調査・探索・並列分析はサブエージェントに委譲
- 1サブエージェント = 1タスク
- メインコンテキストをクリーンに保つ

### Verification Before Done
- 動作証明なしにタスク完了としない
- テスト実行・ログ確認・差分確認
- 「シニアエンジニアが承認するか?」と自問

### Elegance (Balanced)
- 非trivialな変更は「より優雅な方法は?」と一旦立ち止まる
- 単純な修正には適用しない(過度な設計を避ける)

### Autonomous Bug Fixing
- バグ報告は質問せず直す
- ログ・エラー・失敗テストから根本原因を解決

---

## Core Principles
- Simplicity First: 最小限の変更、影響範囲を狭く
- No Laziness: 根本原因を特定。一時的な修正は禁止
- Minimal Impact: 必要な箇所のみ変更

---

## 成果物の置き場
- コード(スクリプト・ノートブック等): `scripts/`
- 生成物(図・表・レポート・派生ファイル等): `outputs/`
- 入力データ(原則 git 管理外): `data/`
- 一時ファイルや作業ファイルをプロジェクトルート直下に置かず、上記いずれかに分類する
- Experimental_record に記録する際は、生成・編集したファイルへの相対パスを必ず書く
  (例: `outputs/figures/dice_curve.png`、`scripts/preprocess.py`)
- プロジェクト固有のサブ構造(`scripts/preprocess/`, `outputs/figures/` 等)は
  必要に応じて自由に作ってよい

---

## Task Management
1. `tasks/todo.md` にチェック可能な計画を記述
2. 進捗に応じて項目をマーク
3. 完了後にレビューセクションを追加

---

## メモリ構造(2層・自動更新)
すべての更新は Stop hook が自動実行する。手動で書く必要はない。

### Layer 1: 詳細
- `Experimental_record/{yyyymmdd}.md` — 日次の作業内容
- `Knowledge/{title}.md` — 再利用可能な知見

### Layer 2: あらすじ
- `Research_overview.md` — 本プロジェクトの研究進捗まとめ(単一ファイル)
- 現在の到達点・マイルストーン・タイムライン・関連リンクを保持

### セッション開始時
1. `Research_overview.md` を Read して現状把握
2. 必要に応じて、そこからリンクされた直近の Experimental_record を参照