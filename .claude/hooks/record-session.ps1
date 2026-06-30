# Stop hook (Windows / PowerShell 5.1) — session recorder  v1.1
# 直前セッションを headless `claude -p` で非同期に記録する。排他制御なし・個人運用前提。
# 重要: 発火と全 early-exit を record.log に必ず記録し、黙って失敗しない。
$ErrorActionPreference = 'SilentlyContinue'

# パスは $PSScriptRoot から導出（JSON の cwd に依存しない）
$HookDir    = $PSScriptRoot
$ProjectDir = (Get-Item $HookDir).Parent.Parent.FullName
$LogFile    = Join-Path $HookDir 'record.log'
function Log([string]$m){ Add-Content -LiteralPath $LogFile -Encoding UTF8 -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'), $m) }

# 発火の足跡（どんな場合も必ず記録 → ログが空なら「フック未起動」と断定できる）
Log "stop-hook fired (proj=$ProjectDir)"

# 再帰防止: 記録用 claude 呼び出しが自身の Stop hook を発火させるため。
if ($env:CLAUDE_HOOK_RECORDING -eq '1') { Log 'skip: recursion guard'; exit 0 }

# stdin から hook JSON を読む（必ず UTF-8 として読む）
# 既定の [Console]::In.ReadToEnd() はコンソールのコードページ（日本語環境では
# CP932）でデコードするため、JSON 内の日本語（last_assistant_message 等）が壊れ、
# バイト境界のズレで構造文字を飲み込み ConvertFrom-Json が失敗する。
# OpenStandardInput を UTF-8 の StreamReader で読むことで確実に復号する。
$raw = ''
try {
  $stdin  = [Console]::OpenStandardInput()
  $reader = New-Object System.IO.StreamReader($stdin, (New-Object System.Text.UTF8Encoding($false)), $true)
  $raw    = $reader.ReadToEnd()
  $reader.Dispose()
} catch { Log ('warn: stdin read failed: ' + $_.Exception.Message) }
$data = $null
if ($raw) {
  $clean = ([string]$raw).TrimStart([char]0xFEFF).Trim()   # 念のため先頭 BOM を除去
  try { $data = $clean | ConvertFrom-Json }
  catch {
    Log ('warn: JSON parse failed: ' + $_.Exception.Message)
    Log ('raw head: ' + $clean.Substring(0, [Math]::Min(200, $clean.Length)))
  }
}
if ($data -and $data.stop_hook_active -eq $true) { Log 'skip: stop_hook_active=true'; exit 0 }

$TranscriptPath = if ($data) { [string]$data.transcript_path } else { '' }
if (-not $TranscriptPath) { Log 'skip: transcript_path 不明（記録不可）'; exit 0 }

$PromptFile = Join-Path $HookDir 'prompts\record-prompt.md'
if (-not (Test-Path -LiteralPath $PromptFile)) { Log 'skip: record-prompt.md なし'; exit 0 }

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Log 'skip: claude CLI が PATH にない'; exit 0 }

$Today        = Get-Date -Format 'yyyyMMdd'
$TodayHuman   = Get-Date -Format 'yyyy-MM-dd'
$NowIso       = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
$OverviewFile = Join-Path $ProjectDir 'Research_overview.md'

$KnowledgeDir  = Join-Path $ProjectDir 'Knowledge'
$KnowledgeList = ''
if (Test-Path -LiteralPath $KnowledgeDir) {
  $KnowledgeList = (Get-ChildItem -LiteralPath $KnowledgeDir -Filter '*.md' -ErrorAction SilentlyContinue |
    ForEach-Object { $_.FullName }) -join "`r`n"
}
if (-not $KnowledgeList) { $KnowledgeList = '(まだKnowledgeファイルなし)' }
$OverviewStatus = if (Test-Path -LiteralPath $OverviewFile) { '存在(更新する)' } else { '不在(新規作成する)' }

$Prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8
$ctx = @"

---
## このセッションのコンテキスト
- Transcript path: $TranscriptPath
- 今日の日付: $TodayHuman (ファイル名用: $Today)
- 現在時刻 (ISO): $NowIso
- Project root: $ProjectDir
- Research_overview path: Research_overview.md ($OverviewStatus)

## 既存Knowledgeファイル一覧
$KnowledgeList

Step 1 から順に実行してください。
"@
$FullPrompt = $Prompt + $ctx

# 大きなプロンプトは temp に書き、detached プロセスから読む
$TmpPrompt = Join-Path $env:TEMP ("claude-record-" + $PID + ".txt")
$TmpWorker = Join-Path $env:TEMP ("claude-record-" + $PID + ".ps1")
[System.IO.File]::WriteAllText($TmpPrompt, $FullPrompt, (New-Object System.Text.UTF8Encoding($false)))

$worker = @"
`$env:CLAUDE_HOOK_RECORDING = '1'
Set-Location -LiteralPath '$ProjectDir'
Add-Content -LiteralPath '$LogFile' -Encoding UTF8 -Value ('==== ' + (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss') + ' RECORDER START ====')
`$p = Get-Content -LiteralPath '$TmpPrompt' -Raw -Encoding UTF8
`$p | claude -p --output-format text --permission-mode bypassPermissions 2>&1 | Add-Content -LiteralPath '$LogFile' -Encoding UTF8
Add-Content -LiteralPath '$LogFile' -Encoding UTF8 -Value ('==== ' + (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss') + ' RECORDER END ====')
Remove-Item -LiteralPath '$TmpPrompt','$TmpWorker' -Force -ErrorAction SilentlyContinue
"@
[System.IO.File]::WriteAllText($TmpWorker, $worker, (New-Object System.Text.UTF8Encoding($true)))

Log 'launching detached recorder'
Start-Process -WindowStyle Hidden -FilePath 'powershell.exe' `
  -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $TmpWorker) | Out-Null

exit 0