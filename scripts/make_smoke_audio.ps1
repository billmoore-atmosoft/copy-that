<# Generate fixed synthetic speech for inference smoke tests, never a microphone recording. #>
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$projectFolder = Split-Path -Parent $PSScriptRoot
$audioFolder = Join-Path $projectFolder '.runtime\synthetic\short'
New-Item -ItemType Directory -Path $audioFolder -Force | Out-Null
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$text = 'Please check the current build and tell me why it failed. Do not deploy it to production until I approve it.'
try {
    $speech.SetOutputToWaveFile((Join-Path $audioFolder 'audio.wav'), $format)
    $speech.Speak($text)
} finally { $speech.Dispose() }
Set-Content -LiteralPath (Join-Path $audioFolder 'reference.txt') -Value $text -Encoding utf8
Set-Content -LiteralPath (Join-Path $audioFolder 'expected.txt') -Value $text -Encoding utf8
Write-Host 'Synthetic audio saved under .runtime\synthetic.'
