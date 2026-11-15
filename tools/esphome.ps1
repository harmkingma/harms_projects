param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('espcam-water', 'floorheating-temp-monitor')]
    [string]$Project,
    [Parameter(Mandatory = $true)]
    [ValidateSet('config', 'compile', 'run', 'upload', 'logs')]
    [string]$Action,
    [string]$Device
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$configs = @{
    'espcam-water' = 'espcam-water.yaml'
    'floorheating-temp-monitor' = 'feather-temp.yaml'
}
$config = Join-Path $root "projects\esphome\$Project\$($configs[$Project])"
$arguments = @($Action, $config)
if ($Device) { $arguments += @('--device', $Device) }
& (Join-Path $PSScriptRoot 'esphome.cmd') @arguments
if ($LASTEXITCODE -ne 0) { throw "ESPHome $Action failed for $Project." }
