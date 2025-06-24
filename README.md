# WiFi-fix

This repository provides a PowerShell script, `reset-wifi.ps1`, that automates reinstalling a Wi-Fi adapter.

Running the script removes the adapter and its driver, triggers a hardware rescan and waits for Windows to reinstall the adapter.

## Usage

1. Open PowerShell as **Administrator**.
2. Run the script:

```powershell
./reset-wifi.ps1
```

Windows will remove the Wi-Fi device and its driver, scan for hardware changes and automatically reinstall the adapter.
