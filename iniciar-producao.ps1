# Modo de produção: compila o frontend e sobe UM processo (API + interface) na porta 8010, sem --reload.
# O PDF passa a abrir a página de impressão na própria API, então o Vite não precisa estar rodando.
# Uso: .\iniciar-producao.ps1            (só nesta máquina)
#      .\iniciar-producao.ps1 -Rede      (aceita acesso de outras máquinas da rede)
param([switch]$Rede)
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$porta = 8010

Push-Location "$raiz\frontend"
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Falha no build do frontend" }
} finally { Pop-Location }

Push-Location "$raiz\backend"
try {
    .\.venv\Scripts\python.exe -m app.seed
    if ($LASTEXITCODE -ne 0) { throw "Falha no seed" }
    $env:NEXUS_FRONTEND = "http://127.0.0.1:$porta"
    $hostApi = if ($Rede) { '0.0.0.0' } else { '127.0.0.1' }
    Start-Process "http://localhost:$porta"
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host $hostApi --port $porta
} finally { Pop-Location }
