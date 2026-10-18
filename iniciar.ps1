# Sobe a API (porta 8010) e o frontend (porta 5173) em duas janelas e abre o navegador.
# Uso: clique com o botão direito > Executar com PowerShell, ou rode .\iniciar.ps1
$raiz = $PSScriptRoot
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$raiz\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8010 --reload"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$raiz\frontend'; npm run dev"
Start-Sleep 4
Start-Process 'http://localhost:5173'
