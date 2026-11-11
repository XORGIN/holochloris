# Lance les trois services dans trois PowerShell distincts.
# 1. Démarrer Raspberry Pi + ComfyUI Desktop auparavant.
$web = 'C:\holochloris_web_p5'
$c2 = 'C:\Users\alize\Desktop\automatisation-microscope\holochloris_declencheur_flux.py'
$mstPython = 'C:\holochloris\MST-plus-plus\.venv\Scripts\python.exe'
$mstScript = 'C:\holochloris\holochloris_mst_flux_auto.py'
foreach ($p in @("$web\server.py", $c2, $mstPython, $mstScript)) {
    if (-not (Test-Path $p)) { Write-Error "Fichier absent : $p"; exit 1 }
}
Start-Process powershell.exe -ArgumentList @('-NoExit', '-Command', "Set-Location '$web'; py server.py")
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList @('-NoExit', '-Command', "& '$mstPython' '$mstScript'")
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList @('-NoExit', '-Command', "py '$c2'")
Write-Host 'Holochloris démarré. Interface : http://127.0.0.1:8765'
Write-Host 'Arrêt : Ctrl+C dans chaque fenêtre lancée.'
