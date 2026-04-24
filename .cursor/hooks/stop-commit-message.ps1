$ErrorActionPreference = "Stop"

# Do not read stdin here: stop hooks may be invoked without piped input.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$hooksJsonPath = Join-Path $repoRoot ".cursor/hooks.json"

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Output "{}"
        exit 0
    }

    $status = git -C $repoRoot status --porcelain 2>$null
} catch {
    # Fail-open: return empty object if git is unavailable.
    Write-Output "{}"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Output "{}"
    exit 0
}

$followupMessage = $null

try {
    if (Test-Path $hooksJsonPath) {
        $hooksConfig = Get-Content -Path $hooksJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($hooksConfig.stop_commit_message_prompt -and -not [string]::IsNullOrWhiteSpace([string]$hooksConfig.stop_commit_message_prompt)) {
            $followupMessage = [string]$hooksConfig.stop_commit_message_prompt
        }
    }
} catch {
    # Fail-open: return empty object if hooks.json cannot be parsed.
}

if ([string]::IsNullOrWhiteSpace([string]$followupMessage)) {
    Write-Output "{}"
    exit 0
}

$result = @{
    followup_message = $followupMessage
}

$json = $result | ConvertTo-Json -Compress
$escapedJson = ($json.ToCharArray() | ForEach-Object {
    if ([int][char]$_ -gt 127) {
        '\u{0:x4}' -f [int][char]$_
    } else {
        $_
    }
}) -join ''

Write-Output $escapedJson
