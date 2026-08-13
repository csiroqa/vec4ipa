# install_msix.ps1 - register the packaged GUI (MSIX) for the current user.
#
# The package is signed with the dev certificate "CN=vec4ipa contributors"
# (vec4ipa_wap_*.cer sits next to the msix).  Deployment validates the
# chain against the MACHINE stores, so this script self-elevates and a
# UAC prompt appears - click Yes once.
#
# Run:  powershell -ExecutionPolicy Bypass -File .\install_msix.ps1

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit 0
}

$appxDir = Join-Path $PSScriptRoot "AppPackages"
$msix = Get-ChildItem $appxDir -Recurse -Filter *.msix |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $msix) { Write-Host "no .msix found under $appxDir"; exit 1 }

$cer = $msix.FullName -replace '\.msix$', '.cer'
if (-not (Test-Path $cer)) {
    Write-Host "no .cer next to the package - exporting the dev cert from the store..."
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object { $_.Subject -eq "CN=vec4ipa contributors" } |
        Select-Object -First 1
    if (-not $cert) {
        Write-Host "dev cert 'CN=vec4ipa contributors' not found in Cert:\CurrentUser\My"
        exit 1
    }
    Export-Certificate -Cert $cert -FilePath $cer -Force | Out-Null
}
if (-not (Test-Path $cer)) { Write-Host "cannot obtain the dev certificate: $cer"; exit 1 }

Write-Host "installing dev certificate (machine stores)..."
certutil -addstore TrustedPeople $cer | Out-Null
certutil -addstore Root $cer | Out-Null

Write-Host "registering $($msix.Name)..."
Add-AppxPackage -Path $msix.FullName

Get-AppxPackage vec4ipaWorkbench |
    Select-Object Name, Version, InstallLocation | Format-List
Write-Host "done - start 'vec4ipa Workbench' from the Start menu."
