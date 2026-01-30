$Url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
$InstallerPath = "$env:TEMP\vc_redist.x64.exe"
Write-Host "Downloading Visual C++ Redistributable..."
Invoke-WebRequest -Uri $Url -OutFile $InstallerPath
Write-Host "Download Complete."
Write-Host "Installing..."
$Process = Start-Process -FilePath $InstallerPath -ArgumentList "/install /quiet /norestart" -PassThru -Wait
if ($Process.ExitCode -eq 0) { Write-Host "Success." } elseif ($Process.ExitCode -eq 3010) { Write-Host "Success (Restart Required)." } else { Write-Error "Failed with code $($Process.ExitCode)" }
if (Test-Path $InstallerPath) { Remove-Item $InstallerPath }
