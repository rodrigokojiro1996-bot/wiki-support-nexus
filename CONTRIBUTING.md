# Como contribuir

## Regra número um

**O repositório é público. Nunca commite** manuais reais, prints de telas com dados, catálogo de um banco real,
`backend/modulos.json`, `.env`, nomes de servidores, de clientes ou de pessoas. Use o sistema de exemplo
(`demo_pdv`, manuais `DEMO.*`) para testar e para os prints de PR. O `.gitignore` já barra os caminhos desse
conteúdo; o push protection do GitHub barra credenciais conhecidas.

## Rodar

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m app.seed

cd ..\frontend
npm ci

cd ..
.\iniciar.ps1          # API em :8010, interface em :5173
```

Com Docker: veja [docs/docker.md](docs/docker.md).

## Testar

```powershell
backend\.venv\Scripts\python.exe -m pytest -q     # na raiz do projeto
cd frontend; npm run build                        # inclui a checagem de tipos
```

O CI roda isso em todo PR, mais o `promtool` e o build da imagem Docker. A `main` só aceita merge com os quatro
jobs verdes.

## Branch, commit e PR

- **Uma branch por mudança**, com o tipo no nome: `feat/importar-manual`, `fix/modulo-importador`,
  `docs/...`, `ci/...`, `refactor/...`, `test/...`, `chore/...`.
- **Commits** no padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/): `feat: ...`,
  `fix: ...`, `docs: ...`. A mensagem diz o que mudou e por quê.
- **PR pequeno**, com título no mesmo padrão e o template preenchido (o que muda, por que, como testei).
  Se resolve uma issue, escreva `Fecha #N` na descrição.
- Atualize o [CHANGELOG](CHANGELOG.md) na seção **Não publicado**.
- **Squash and merge** para PR pequeno; **Rebase and merge** quando cada commit do PR fizer sentido sozinho.

## Versão

Ao publicar: a seção "Não publicado" do CHANGELOG vira `[0.X.0] - data`, commit `chore: versão 0.X.0`, tag
anotada `v0.X.0` e push da tag. A Release do GitHub é criada sozinha pelo workflow `release.yml`.

## Falha de segurança

Não abra issue: veja o [SECURITY.md](SECURITY.md).
