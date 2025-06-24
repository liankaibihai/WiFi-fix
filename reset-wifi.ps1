#Requires -RunAsAdministrator
<#[
.SYNOPSIS
    Force reinstall of Wi-Fi adapter by uninstalling the device and its driver.
.DESCRIPTION
    This script automates the Device Manager steps for removing a Wi-Fi adapter and deleting its driver software. After removal, it scans for hardware changes and waits for the adapter to be re-detected.
#]

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Please run this script as Administrator."
    exit 1
}

# Identify Wi-Fi adapters
$wifiAdapters = Get-PnpDevice -Class 'Net' | Where-Object {
    $_.FriendlyName -match 'Wi-Fi|Wireless|802.11'
}

if (!$wifiAdapters) {
    Write-Error "No Wi-Fi adapter found."
    exit 1
}

foreach ($adapter in $wifiAdapters) {
    Write-Output "Removing driver for $($adapter.FriendlyName)"
    $inf = (Get-PnpDeviceProperty -InstanceId $adapter.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath').Data
    if ($inf) {
        pnputil /delete-driver $inf /uninstall /force | Out-Null
    }
    Write-Output "Removing device $($adapter.InstanceId)"
    pnputil /remove-device $adapter.InstanceId /subtree /force | Out-Null
}

Write-Output "Scanning for hardware changes..."
pnputil /scan-devices | Out-Null

$timeout = 60
Do {
    Start-Sleep -Seconds 2
    $timeout -= 2
    $current = Get-PnpDevice -Class 'Net' | Where-Object {
        $_.FriendlyName -match 'Wi-Fi|Wireless|802.11' -and $_.Status -eq 'OK'
    }
} While (-not $current -and $timeout -gt 0)

if ($current) {
    Write-Output "Wi-Fi adapter reinstalled: $($current[0].FriendlyName)"
} else {
    Write-Warning "Timed out waiting for Wi-Fi adapter reinstall."
}
