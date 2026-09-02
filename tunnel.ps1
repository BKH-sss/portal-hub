$process = New-Object System.Diagnostics.Process
$process.StartInfo.FileName = "ssh"
$process.StartInfo.Arguments = "-o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run"
$process.StartInfo.UseShellExecute = $false
$process.StartInfo.RedirectStandardOutput = $true
$process.StartInfo.RedirectStandardError = $true
$process.Start()

Write-Host "터널 개방 중... (잠시만 기다려주세요)"

$stdoutReader = $process.StandardOutput
$stderrReader = $process.StandardError

while (!$process.HasExited) {
    if (!$stdoutReader.EndOfStream) {
        $line = $stdoutReader.ReadLine()
        Write-Host $line
        if ($line -match "(https://[a-zA-Z0-9.-]+\.lhr\.life)") {
            $url = $matches[1] + "/chatbot.html"
            Write-Host "`n=======================================================" -ForegroundColor Green
            Write-Host "✅ 외부 접속 링크 발급 완료!" -ForegroundColor Green
            Write-Host "링크: $url" -ForegroundColor Yellow
            $url | Set-Clipboard
            Write-Host "✅ 클립보드에 자동 복사되었습니다! (Ctrl+V 로 붙여넣기)" -ForegroundColor Cyan
            Write-Host "=======================================================`n" -ForegroundColor Green
        }
    }
    if (!$stderrReader.EndOfStream) {
        $errLine = $stderrReader.ReadLine()
        Write-Host $errLine
    }
    Start-Sleep -Milliseconds 100
}
