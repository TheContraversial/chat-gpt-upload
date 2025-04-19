# test-chat.ps1
# Runs a full chat test: creates chat, uploads multiple files, sends a message, and prints GPT response

# Configuration
$baseUrl = "http://127.0.0.1:8500"
$message = "Summarize the uploaded documents."

# Start a new chat session
Write-Host "Starting new chat..."
$chat = Invoke-RestMethod -Uri "$baseUrl/start-chat" -Method POST
$chatId = $chat.chat_id
Write-Host "Chat ID: $chatId"

# Upload multiple files
$filesToUpload = @(
    @{ filename = "test.docx"; contentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
    @{ filename = "test.pdf"; contentType = "application/pdf" },
    @{ filename = "test.txt"; contentType = "text/plain" },
    @{ filename = "test.png"; contentType = "image/png" }
)

foreach ($file in $filesToUpload) {
    $filename = $file.filename
    $contentType = $file.contentType
    $filePath = Join-Path $PSScriptRoot $filename

    if (Test-Path $filePath) {
        Write-Host "Uploading $filename..."

        $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        $contentDisposition = "form-data; name=\"file\"; filename=\"$filename\""
        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=\"chat_id\"$LF",
            $chatId,
            "--$boundary",
            "Content-Disposition: $contentDisposition",
            "Content-Type: $contentType$LF"
        )

        $bodyStream = New-Object System.IO.MemoryStream
        $writer = New-Object System.IO.StreamWriter($bodyStream)
        $bodyLines | ForEach-Object { $writer.Write($_ + $LF) }
        $writer.Flush()
        $bodyStream.Write($fileBytes, 0, $fileBytes.Length)
        $writer.Write($LF + "--$boundary--$LF")
        $writer.Flush()
        $bodyStream.Seek(0, 'Begin') | Out-Null

        try {
            Invoke-RestMethod -Uri "$baseUrl/upload-docx" -Method POST -Body $bodyStream -ContentType "multipart/form-data; boundary=$boundary"
            Write-Host "Uploaded $filename successfully."
        } catch {
            Write-Host "Failed to upload $filename: $_"
        }
    } else {
        Write-Host "Skipping $filename (not found)"
    }
}

# Send a message to the /ask endpoint
Write-Host "Sending message: $message"
$body = @{ chat_id = $chatId; message = $message } | ConvertTo-Json -Compress
$response = Invoke-WebRequest -Uri "$baseUrl/ask" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing

Write-Host "--- GPT Reply ---"
$response.Content
