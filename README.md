# Support Nexus

Base de conhecimento para equipes de suporte de ERP, com um **mapa vivo do sistema**: cada tela do sistema
aparece ligada às tabelas do banco que ela usa, às relações entre essas tabelas e aos manuais de suporte.

- **Mapa do sistema:** menus e telas na mesma ordem do sistema, com atalhos e códigos de janela.
- **Diagrama ER por tela:** as tabelas da tela e as vizinhas, ligadas coluna a coluna (N → 1), com destaque ao clicar.
- **Catálogo do banco sem tocar em produção:** um coletor lê só o `information_schema`, e as relações que não existem como FK são inferidas por regras e validadas pela equipe (confirmada · documentada · sugerida).
- **Manuais** com sumário automático, passos, observações e SQL, e **exportação para PDF** com cabeçalho e número de página.

O repositório vem com um **sistema de exemplo** (varejo fictício, 30 tabelas, 6 manuais) para rodar sem nenhum banco real.

```
coletor/    lê a estrutura de um MySQL (só information_schema) e infere as relações
            exemplo/ traz o banco fictício demo_pdv já no formato do coletor
backend/    API FastAPI + SQLite (catálogo, menus, vínculos, validações, manuais, PDF)
frontend/   React + TypeScript (Vite): mapa do sistema, diagrama e manuais
```

## Rodar

Requisitos: Windows com Microsoft Edge (para o PDF), Python 3.12+ e Node.js 20+.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.seed          # carrega o sistema de exemplo

cd ..\frontend
npm install

cd ..
.\iniciar.ps1                                  # API em :8010, interface em :5173
```

## Usar com um banco real

```powershell
cd coletor
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env                          # preencha host, usuário (só SELECT) e senha
.venv\Scripts\python.exe coletar.py meu_banco
.venv\Scripts\python.exe inferir.py meu_banco   # regras + dicionario.json
```

Depois aponte o módulo para `meu_banco` em `backend/app/seed.py` e rode o seed de novo. A coleta real fica em
`coletor/saida/`, que não é versionada.

A documentação técnica completa (arquitetura, decisões, validações e API) está em [readme.txt](readme.txt).
