[CmdletBinding()]
param(
    [switch]$SkipAppInstall
)

$ErrorActionPreference = 'Stop'

$VenvName = 'parse-1c-build'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$MainSpec = Join-Path $ProjectRoot '.dev'
$DependencyRoots = @(
    'C:\Dev\Python\commons',
    'C:\Dev\Python\commons-1c'
)

if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
    throw 'pipx is not available on PATH.'
}

if (-not (Test-Path -LiteralPath (Join-Path $MainSpec 'pyproject.toml'))) {
    throw "Main dev pyproject.toml was not found: $MainSpec"
}

if (-not $SkipAppInstall) {
    & pipx install --editable --force $MainSpec
}

foreach ($dependencyRoot in $DependencyRoots) {
    if (-not (Test-Path -LiteralPath (Join-Path $dependencyRoot 'pyproject.toml'))) {
        throw "Dependency pyproject.toml was not found: $dependencyRoot"
    }
}

$installArgs = @('runpip', $VenvName, 'install', '--no-deps', '--no-cache-dir', '--force-reinstall')
foreach ($dependencyRoot in $DependencyRoots) {
    $installArgs += '-e'
    $installArgs += $dependencyRoot
}

& pipx @installArgs
& pipx runpip $VenvName list --editable
