# 記録テンプレート集
> このファイルは `.claude/hooks/prompts/record-prompt.md` から参照されます。

## Experimental_record(作業・コード変更)
# {yyyy-mm-dd} 実験記録
## {タイトル}
### 概要
- 何を行ったか
### 変更ファイル
- `scripts/path/to/file.py` (新規 / 編集 / 削除)
- `outputs/figures/xxx.png` (生成)
### Before / After
| 項目 | Before | After |
|------|--------|-------|
| 機能A | 旧 | 新 |
### 変更理由
-
### ハマった点と解決策
- 問題:
- 解決策:
### 関連リンク
-

## Experimental_record(解析)
## {タイトル}
### 解析目的
### 解析手法
- 対象データ: `data/xxx.csv`
- 統計手法:
- 使用ツール:
### 主要な結果
- 生成物: `outputs/xxx.png`, `outputs/xxx.csv`
### 解釈・考察
### 次のステップ

## Knowledge(新規)
# {タイトル}
- type: lesson | technique | pattern
- created: {yyyy-mm-dd}
- tags: [tag1, tag2]
## 概要
## 背景・発見経緯
## 詳細
## 適用場面
## 関連
- Experimental_record/{yyyymmdd}.md

## Knowledge(追記)
## 追記 ({yyyy-mm-dd})
- 関連: Experimental_record/{yyyymmdd}.md
{差分のみ}

## Research_overview(参考)
# 研究進捗 Overview
- last_updated: {yyyy-mm-dd}
## 研究概要
{1-2段落}
## 現在の到達点
{1段落・スナップショット}
## マイルストーン
- [x] 完了したもの ({yyyy-mm-dd})
- [ ] 次のステップ
## タイムライン
- {yyyy-mm-dd}: {1行サマリ} -> [詳細](Experimental_record/{yyyymmdd}.md)
## 関連 Knowledge
- [タイトル](Knowledge/xxx.md)
## 関連リソース
- 論文・データ場所等