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
.\iniciar.ps1                                  # desenvolvimento: API em :8010, interface em :5173
.\iniciar-producao.ps1                         # produção: build + um só processo em :8010
```

## Rodar com Docker

```powershell
copy .env.example .env                          # defina GRAFANA_SENHA
docker compose up -d --build                    # sobe a aplicação, o Prometheus e o Grafana
docker compose ps                               # espere os três "(healthy)"
```

| Endereço | Serviço |
|---|---|
| http://localhost:8010 | Support Nexus |
| http://localhost:3000 | Grafana: painel "Support Nexus · API" (usuário `admin`, senha do `.env`) |
| http://localhost:9090 | Prometheus: métricas, alvos e alertas |

Tudo só nesta máquina. Instalação do Docker no Windows, backup dos dados e o porquê de cada escolha:
[docs/docker.md](docs/docker.md). Métricas, painel e alertas: [docs/monitoramento.md](docs/monitoramento.md).

## Testes

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m pytest -q     # na raiz do projeto
```

`pytest -q`, `npm test` e `npm run build` (em `frontend/`) verdes antes de cada commit.

## Usar com um banco real

```powershell
cd coletor
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env                          # preencha host, usuário (só SELECT) e senha
.venv\Scripts\python.exe coletar.py meu_banco
.venv\Scripts\python.exe inferir.py meu_banco   # regras + dicionario.json
```

Depois copie `backend/modulos.exemplo.json` para `backend/modulos.json`, aponte o módulo para `meu_banco` e rode o
seed de novo. A coleta real (`coletor/saida/`), os manuais importados (`backend/dados/`) e o `modulos.json` não são
versionados.

> **O repositório é público.** Nunca commite manuais reais, prints, catálogo de banco real, `.env`, nomes de
> servidores ou de clientes.

A documentação técnica completa (arquitetura, decisões, validações e API) está em
[docs/arquitetura.md](docs/arquitetura.md). As mudanças de cada versão estão no [CHANGELOG](CHANGELOG.md).

Para contribuir: [CONTRIBUTING.md](CONTRIBUTING.md). Falhas de segurança: [SECURITY.md](SECURITY.md).

## Licença

[MIT](LICENSE).
