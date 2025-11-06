param(
    [Parameter(Mandatory=$true)]
    [string]$RunId,
    [string]$Workflow = "phase07_feature_app",
    [string]$ArtifactsRoot,
    [string]$OutputSubdir,
    [switch]$DisableGitSuffix,
    [switch]$RequireApproval,
    [int]$ApprovalCount = -1,
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

# Resolve important roots (this file lives in backend\knime, so repo root is one level above backend)
$backendRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $backendRoot

# Load approval gate (module resides in repo-level scripts/)
. "$(Join-Path $repoRoot 'scripts/knime_approval.ps1')"

# Require approval before batch execution
Confirm-KnimeApproval -Context "KNIME Batch Workflow ($RunId)" -RequireApproval:$RequireApproval -ApprovalCount $ApprovalCount -AutoApprove:$AutoApprove | Out-Null

# Resolve KNIME executable path (KNIME_HOME > PATH > default locations)
$KnimeExe = $null
if ($env:KNIME_HOME) {
    $k1 = Join-Path $env:KNIME_HOME 'knime.exe'
    if (Test-Path $k1) { $KnimeExe = $k1 }
}
if (-not $KnimeExe) {
    $cmd = Get-Command -Name knime -ErrorAction SilentlyContinue
    if ($cmd) { $KnimeExe = $cmd.Source }
}
if (-not $KnimeExe) {
    $k2 = 'C:\\Program Files\\KNIME\\knime.exe'
    if (Test-Path $k2) { $KnimeExe = $k2 }
}
if (-not $KnimeExe) {
    $k3 = 'C:\\Program Files (x86)\\KNIME\\knime.exe'
    if (Test-Path $k3) { $KnimeExe = $k3 }
}
if (-not $KnimeExe) {
    Write-Error "KNIME executable not found. Set KNIME_HOME or ensure knime.exe is on PATH."
    exit 1
}

# Determine workflow file (accept relative names without extension)
$workflowName = $Workflow
if ([string]::IsNullOrWhiteSpace([System.IO.Path]::GetExtension($workflowName))) {
    $workflowName = "$workflowName.knwf"
}
$workflowCandidates = @()
if ([System.IO.Path]::IsPathRooted($workflowName)) {
    $workflowCandidates += $workflowName
} else {
    $workflowCandidates += Join-Path $repoRoot (Join-Path 'knime' $workflowName)
    $workflowCandidates += Join-Path $repoRoot (Join-Path 'knime/workflows' $workflowName)
}
$WorkflowPath = $null
foreach ($candidate in $workflowCandidates) {
    if (Test-Path $candidate) {
        $WorkflowPath = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}
if (-not $WorkflowPath) {
    Write-Error "Workflow file not found. Checked: $($workflowCandidates -join ', ')"
    exit 1
}

# Resolve artifacts root (default to repoRoot/artifacts)
if ([string]::IsNullOrWhiteSpace($ArtifactsRoot)) {
    $ArtifactsRoot = Join-Path $repoRoot 'artifacts'
} elseif (-not [System.IO.Path]::IsPathRooted($ArtifactsRoot)) {
    $ArtifactsRoot = Join-Path $repoRoot $ArtifactsRoot
}
if (-not (Test-Path $ArtifactsRoot)) {
    New-Item -ItemType Directory -Path $ArtifactsRoot -Force | Out-Null
}
$ArtifactsRoot = (Resolve-Path -LiteralPath $ArtifactsRoot).Path

$InputDir = Join-Path $ArtifactsRoot (Join-Path $RunId 'phase_07_knime')
if (-not (Test-Path $InputDir)) {
    Write-Error "Input directory not found: $InputDir"
    exit 1
}

# Read git_sha from run_meta.json if available to build a unique output subfolder
$RunMetaPath = Join-Path $InputDir 'run_meta.json'
$GitSha = $null
if (-not $DisableGitSuffix -and (Test-Path $RunMetaPath)) {
    try {
        $meta = Get-Content $RunMetaPath -Raw | ConvertFrom-Json
        $GitSha = $meta.git_sha
    } catch {
        Write-Warning "Could not parse run_meta.json; proceeding without git_sha subfolder."
    }
}

$BaseOutputDir = $InputDir
if (-not $DisableGitSuffix -and -not [string]::IsNullOrWhiteSpace($GitSha)) {
    $BaseOutputDir = Join-Path $InputDir ("git_" + $GitSha)
}
if (-not (Test-Path $BaseOutputDir)) {
    New-Item -ItemType Directory -Path $BaseOutputDir -Force | Out-Null
}

$OutputDir = $BaseOutputDir
if (-not [string]::IsNullOrWhiteSpace($OutputSubdir)) {
    $OutputDir = Join-Path $BaseOutputDir $OutputSubdir
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
}

Write-Host "?? Running KNIME for run: $RunId" -ForegroundColor Green
Write-Host "?? Workflow:  $WorkflowPath" -ForegroundColor Cyan
Write-Host "?? InputDir:  $InputDir" -ForegroundColor Cyan
Write-Host "?? OutputDir: $OutputDir" -ForegroundColor Cyan

$knimeArgs = @(
    '-nosplash',
    '-application', 'org.knime.product.KNIME_BATCH_APPLICATION',
    "-workflowFile=$WorkflowPath",
    '-workflow.variable', "input_dir,$InputDir,String",
    '-workflow.variable', "output_dir,$OutputDir,String",
    '-reset'
)

$process = Start-Process -FilePath $KnimeExe -ArgumentList $knimeArgs -NoNewWindow -Wait -PassThru
$exitCode = $process.ExitCode

if ($exitCode -ne 0) {
    Write-Error "KNIME batch run failed with exit code $exitCode"
    exit $exitCode
}

Write-Host "? KNIME workflow completed successfully" -ForegroundColor Green
Get-ChildItem $OutputDir -File -Recurse | ForEach-Object { Write-Host ("    -> " + $_.FullName) }
