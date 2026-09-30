param(
    [Parameter(Mandatory = $true)]
    [string]$TestData
)

$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$executable = Join-Path $releaseRoot 'STEMCropTool.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "STEMCropTool.exe was not found beside this script."
}
if (-not (Test-Path -LiteralPath $TestData -PathType Container)) {
    throw "Test-data directory does not exist: $TestData"
}

$workspace = Join-Path ([System.IO.Path]::GetTempPath()) (
    'stem-crop-clean-machine-' + [guid]::NewGuid().ToString('N')
)
[System.IO.Directory]::CreateDirectory($workspace) | Out-Null
$environmentNames = @(
    'PATH',
    'PYTHONHOME',
    'PYTHONPATH',
    'CONDA_PREFIX',
    'QT_QPA_PLATFORM',
    'STEM_CROP_TOOL_SELF_TEST_DIR',
    'STEM_CROP_TOOL_TEST_DATA'
)
$originalEnvironment = @{}
foreach ($name in $environmentNames) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        [EnvironmentVariableTarget]::Process
    )
}
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    Remove-Item Env:CONDA_PREFIX -ErrorAction SilentlyContinue
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:STEM_CROP_TOOL_SELF_TEST_DIR = $workspace
    $env:STEM_CROP_TOOL_TEST_DATA = (Resolve-Path -LiteralPath $TestData).Path
    $process = Start-Process `
        -FilePath $executable `
        -WorkingDirectory $releaseRoot `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Packaged self-test failed with exit code $($process.ExitCode)."
    }
    $reportPath = Join-Path $workspace 'packaged_self_test.json'
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw 'Packaged self-test did not create its report.'
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.status -ne 'passed' -or -not $report.external_dm_tested) {
        throw 'Packaged self-test did not validate the full real-data matrix.'
    }
    Write-Host 'Packaged self-test passed.'
    $report | ConvertTo-Json -Depth 5
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $originalEnvironment[$name],
            [EnvironmentVariableTarget]::Process
        )
    }
    $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $resolvedWorkspace = [System.IO.Path]::GetFullPath($workspace)
    $tempPrefix = $resolvedTemp.TrimEnd('\') + '\'
    $isInsideTemp = $resolvedWorkspace.StartsWith(
        $tempPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )
    if ($isInsideTemp -and (Test-Path -LiteralPath $resolvedWorkspace)) {
        Remove-Item -LiteralPath $resolvedWorkspace -Recurse -Force
    }
}
