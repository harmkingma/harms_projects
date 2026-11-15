param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('esphome', 'watermeter', 'home-assistant', 'cad-tools')]
    [string]$Profile
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'setup.cmd') $Profile
if ($LASTEXITCODE -ne 0) { throw "Setting up the $Profile environment failed." }
