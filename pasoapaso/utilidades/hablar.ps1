Add-Type -AssemblyName System.Speech
$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $voz.SelectVoice('Microsoft Sabina Desktop') } catch { }
$voz.Rate = 0
$voz.Volume = 100
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
while ($true) {
    $linea = [Console]::In.ReadLine()
    if ($linea -eq $null -or $linea -eq '__SALIR__') { break }
    $linea = $linea.Trim()
    if ($linea.Length -gt 0) {
        try { $voz.Speak($linea) } catch { }
    }
}
$voz.Dispose()
