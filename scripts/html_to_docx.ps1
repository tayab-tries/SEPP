$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open("d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report_Condensed.html")
    $doc.SaveAs([ref]"d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report_Condensed.docx", [ref]16)
    $doc.Close()
    Write-Host "DOCX file created successfully."
} catch {
    Write-Error $_.Exception.Message
} finally {
    $word.Quit()
}
