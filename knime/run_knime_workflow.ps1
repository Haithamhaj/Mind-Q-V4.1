# DEPRECATED: retained for legacy KNIME workflows only. Stage 07 runs via Python now.

param(
    [Parameter(Mandatory = $true)]
    [string]$RunId,
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path

$knimeExe = $null
if ($env:KNIME_HOME) {
    $candidate = Join-Path $env:KNIME_HOME "knime.exe"
    if (Test-Path $candidate) {
        $knimeExe = $candidate
    }
}
if (-not $knimeExe) {
    $lookup = Get-Command -Name "knime.exe" -ErrorAction SilentlyContinue
    if (-not $lookup) {
        $lookup = Get-Command -Name "knime" -ErrorAction SilentlyContinue
    }
    if ($lookup) {
        $knimeExe = $lookup.Source
    }
}
if (-not $knimeExe) {
    throw "knime.exe not found. Set KNIME_HOME or ensure knime.exe is on PATH."
}

$workflowPath = Join-Path $repoRoot "knime\phase07_feature_app.knwf"
if (-not (Test-Path $workflowPath)) {
    throw "Workflow file not found: $workflowPath"
}
$workflowPath = (Resolve-Path $workflowPath).Path

$inputDir = Join-Path $repoRoot ("artifacts\{0}\phase_07_knime" -f $RunId)
if (-not (Test-Path $inputDir)) {
    throw "Input directory not found: $inputDir"
}

$outputDir = Join-Path $inputDir "outputs"
$logDir = Join-Path $repoRoot ("artifacts\{0}\knime_logs" -f $RunId)
New-Item -ItemType Directory -Force -Path $outputDir, $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir ("knime_batch_{0}.log" -f $timestamp)

$vmargs = $env:KNIME_VMARGS
if ([string]::IsNullOrWhiteSpace($vmargs)) {
    $vmargs = "-Xms4g -Xmx16g"
}

$knArgs = @(
    "-nosplash",
    "-application", "org.knime.product.KNIME_BATCH_APPLICATION",
    ("-workflowFile=""{0}""" -f $workflowPath),
    ("-workflow.variable=input_dir,""{0}"",String" -f $inputDir),
    ("-workflow.variable=output_dir,""{0}"",String" -f $outputDir),
    "-reset",
    "-vmargs", $vmargs
)

Write-Host ("KNIME_EXE={0}" -f $knimeExe)
Write-Host ("WORKFLOW_PATH={0}" -f $workflowPath)
Write-Host ("INPUT_DIR={0}" -f $inputDir)
Write-Host ("OUTPUT_DIR={0}" -f $outputDir)
Write-Host ("LOG_PATH={0}" -f $logPath)

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $knimeExe
$psi.Arguments = ($knArgs -join " ")
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $psi
[void]$process.Start()
$process.StandardOutput.ReadToEnd() | Tee-Object -FilePath $logPath | Out-Null
$process.StandardError.ReadToEnd() | Tee-Object -FilePath $logPath -Append | Out-Null
$process.WaitForExit()

exit $process.ExitCode
