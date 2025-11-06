<#
.SYNOPSIS
  Centralized approval gate for KNIME executions.

.DESCRIPTION
  Provides an interactive (or pre-configured) approval step before launching KNIME GUI
  or running KNIME batch workflows. Supports:
    - Persistent allowance for N runs (decremented automatically)
    - Environment variables KNIME_REQUIRE_APPROVAL, KNIME_APPROVAL_COUNT
    - CI auto-approval
    - Non-interactive safety (fails closed unless explicitly auto-approved)

.USAGE
  . "$PSScriptRoot\knime_approval.ps1"
  Ensure-KnimeApproval -Context "KNIME GUI" -RequireApproval

  # Approve next 3 runs automatically
  Ensure-KnimeApproval -Context "Batch" -ApprovalCount 3

  # Bypass prompt
  Ensure-KnimeApproval -Context "GUI" -AutoApprove
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RepoRootPath {
    try {
        # scripts/ -> repo root
        return (Split-Path -Parent $PSScriptRoot)
    } catch {
        return (Resolve-Path '.').Path
    }
}

function Get-KnimeApprovalStatePath {
    $root = Get-RepoRootPath
    $dir = Join-Path $root 'tools/knime'
    try {
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        return (Join-Path $dir '.approval_state.json')
    } catch {
        # Fallback to temp
        return (Join-Path $env:TEMP 'knime_approval_state.json')
    }
}

function Get-KnimeApprovalState {
    $path = Get-KnimeApprovalStatePath
    if (Test-Path $path) {
        try {
            return (Get-Content $path -Raw | ConvertFrom-Json)
        } catch {
            return ([pscustomobject]@{ remaining = 0; updated_at = (Get-Date).ToString('o') })
        }
    }
    return ([pscustomobject]@{ remaining = 0; updated_at = (Get-Date).ToString('o') })
}

function Save-KnimeApprovalState($state) {
    $path = Get-KnimeApprovalStatePath
    $json = $state | ConvertTo-Json -Depth 5
    Set-Content -Path $path -Value $json -Encoding UTF8
}

function Confirm-KnimeApproval {
    [CmdletBinding()]
    param(
        [string]$Context = 'KNIME',
        [switch]$AutoApprove,
        [int]$ApprovalCount = -1,
        [switch]$RequireApproval
    )

    # CI or explicit auto-approve bypasses prompts
    if ($AutoApprove -or ($env:CI -eq 'true')) { return $true }

    # Determine whether approval is required
    $require = $false
    if ($RequireApproval) { $require = $true }
    elseif ($env:KNIME_REQUIRE_APPROVAL) { $require = ($env:KNIME_REQUIRE_APPROVAL -in @('1','true','yes','on')) }
    else { $require = $true } # default to safe behavior

    if (-not $require) { return $true }

    # External allowance via env var wins for this invocation only
    if ($ApprovalCount -lt 0 -and $env:KNIME_APPROVAL_COUNT) {
        $tmp = 0
        if ([int]::TryParse($env:KNIME_APPROVAL_COUNT, [ref]$tmp)) { $ApprovalCount = $tmp }
    }

    # External allowance via parameter or env var
    if ($ApprovalCount -ge 0) {
        $remaining = [int]$ApprovalCount
        if ($remaining -gt 0) {
            # Consume one now
            $remaining = $remaining - 1
            $state = [pscustomobject]@{ remaining = $remaining; updated_at = (Get-Date).ToString('o') }
            Save-KnimeApprovalState -state $state
            return $true
        } else {
            Write-Host "❌ $Context cancelled (ApprovalCount=0)" -ForegroundColor Yellow
            exit 0
        }
    }

    # Check persisted allowance
    $state = Get-KnimeApprovalState
    if (($state | Get-Member -Name remaining -MemberType NoteProperty) -and [int]$state.remaining -gt 0) {
        $state.remaining = [int]$state.remaining - 1
        $state.updated_at = (Get-Date).ToString('o')
        Save-KnimeApprovalState -state $state
        Write-Host "🟢 $Context auto-approved. Remaining allowances: $($state.remaining)" -ForegroundColor Green
        return $true
    }

    # Non-interactive safe-guard
    if (-not $Host.UI -or -not $Host.UI.RawUI) {
        Write-Host "⚠️ $Context requires approval but session is non-interactive. Set KNIME_REQUIRE_APPROVAL=0 or use -AutoApprove/-ApprovalCount." -ForegroundColor Yellow
        exit 0
    }

    # Interactive prompt
    Write-Host ""; Write-Host "════════ KNIME Approval ─ $Context ════════" -ForegroundColor Cyan
    Write-Host "هل تريد تشغيل KNIME الآن؟" -ForegroundColor White
    Write-Host "  [Y] تشغيل مرة واحدة" -ForegroundColor Gray
    Write-Host "  [N] إلغاء" -ForegroundColor Gray
    Write-Host "  [رقم] الموافقة على عدد مرات (يتم خصم هذه المرة)" -ForegroundColor Gray
    $resp = Read-Host "أدخل اختيارك (Y/N/رقم)"

    if ([string]::IsNullOrWhiteSpace($resp) -or $resp.Trim().ToLower() -eq 'y') {
        return $true
    }
    if ($resp.Trim().ToLower() -in @('n','q','no')) {
        Write-Host "❌ تم الإلغاء" -ForegroundColor Yellow
        exit 0
    }
    $n = 0
    if ([int]::TryParse($resp.Trim(), [ref]$n)) {
        if ($n -le 0) {
            Write-Host "❌ تم الإلغاء (0 محاولات)" -ForegroundColor Yellow
            exit 0
        }
        $state = [pscustomobject]@{ remaining = ($n - 1); updated_at = (Get-Date).ToString('o') }
        Save-KnimeApprovalState -state $state
        Write-Host "🟢 موافقة على $n تشغيل (سيتبقى $($n-1) بعد هذه المرة)" -ForegroundColor Green
        return $true
    }

    Write-Host "❌ اختيار غير معروف. تم الإلغاء." -ForegroundColor Yellow
    exit 0
}

# Dot-sourced script: functions are available to caller
