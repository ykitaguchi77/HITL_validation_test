# Windows の Claude Code フックで stdin JSON を UTF-8 として読む

- type: lesson
- created: 2026-06-15
- tags: [claude-code, hooks, windows, powershell, encoding, utf-8]

## 概要
Claude Code の Stop hook（Windows / PowerShell 5.1）で、stdin の hook JSON を
`[Console]::In.ReadToEnd()` で読むと、**コンソール既定コードページ（日本語環境では CP932）で
誤デコード**され、JSON 内の日本語が壊れて `ConvertFrom-Json` が失敗する。
`[Console]::OpenStandardInput()` を UTF-8 の `StreamReader` で読めば確実に復号できる。

## 背景・発見経緯
本プロジェクトの Stop hook が「毎ターン発火するのに記録が書かれない」状態だった。
`record.log` には `stop-hook fired` → `JSON parse failed` →
`transcript_path 不明（記録不可）` が並んでいた。フック機構自体は正常で、
失敗は **stdin の解析段** にあった。診断ログ（生 stdin 保存＋例外メッセージ）を仕込むと:
- 生 stdin に BOM は無い（当初の BOM 仮説は否定）。
- `last_assistant_message`（前応答の日本語）が文字化けしていた。
- エラーは `':' または '}' ではなく無効なオブジェクトが渡されました。(1993)` という
  **構造破壊エラー**。UTF-8 の日本語バイト列を CP932 として読むとバイト境界がずれ、
  途中の構造文字（`","`, `:` 等）を多バイト文字の後続バイトとして飲み込むため。

## 詳細

### 誤り（CP932 で誤デコードされうる）
```powershell
$raw = [Console]::In.ReadToEnd()
$data = $raw | ConvertFrom-Json    # 日本語を含むと失敗しうる
```

### 正しい（UTF-8 固定で読む）
```powershell
$raw = ''
try {
  $stdin  = [Console]::OpenStandardInput()
  $reader = New-Object System.IO.StreamReader($stdin, (New-Object System.Text.UTF8Encoding($false)), $true)
  $raw    = $reader.ReadToEnd()
  $reader.Dispose()
} catch { }
$raw  = ([string]$raw).TrimStart([char]0xFEFF).Trim()   # 念のため BOM 除去
$data = $raw | ConvertFrom-Json
```
- `StreamReader` 第3引数 `detectEncodingFromByteOrderMarks=$true` で BOM も処理。
- ASCII のみの payload では差は出ないため、**日本語応答を含むと初めて顕在化**する（再現条件に注意）。

### 切り分け・検証のコツ
- フックは「発火しているか」と「発火後どこで落ちたか」を必ずログに残す
  （`stop-hook fired` を無条件 Log、各 early-exit でも Log）。沈黙させない。
- 失敗時は **生 stdin をファイル保存＋例外メッセージ＋先頭数百字**をログへ。
  BOM/エンコーディング/別形式かを後から確定できる。
- PowerShell 5.1 単体で再現可能: UTF-8 の日本語 JSON をファイルにし、
  `powershell -File reader.ps1 < payload.json` で両方式を比較する。
  `[Console]::In` 方式は実フックと同一エラーで失敗、`OpenStandardInput`+UTF8 は成功する。
- 既定エンコーディング確認: `[Console]::InputEncoding`（日本語 Windows では CP932）。

## 適用場面
- Windows + PowerShell で Claude Code の hook（Stop/PreToolUse 等）の stdin JSON を読むとき。
- 日本語など非 ASCII を含む payload を PowerShell で `ConvertFrom-Json` する一般ケース。
- 自己展開型 bootstrap（`CLAUDE_experiment._windows.md`）が配る hook テンプレートにも同修正が必要。

## 関連
- Experimental_record/20260615.md
- フック: `.claude/hooks/record-session.ps1`、テンプレート: `C:\Users\CorneAI\Downloads\CLAUDE_experiment._windows.md`
