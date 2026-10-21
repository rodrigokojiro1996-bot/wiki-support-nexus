# Changelog

Mudanças de cada versão do Support Nexus. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

### Adicionado
- Editor de manuais na interface: "Criar manual para esta tela" na Visão geral, "+ Novo manual" e "Editar".
  Blocos iguais aos dos manuais existentes, prévia ao vivo e prints com Ctrl+V ou arrastando.
- `POST /api/manuais`, `PUT /api/manuais/{código}` e `POST /api/imagens`.
- Blocos de texto e nota com várias linhas saem formatados como foram colados: parágrafos, listas com subitens
  (Tab), títulos de trecho (linha com emoji, "1." ou terminada em ":"), `[ Botão ]` como botão e `->` como seta.
  Passos e OBS mantêm as quebras de linha. Manuais de uma linha por bloco não mudam.
- Código automático por módulo (`PDV.001`…) e versão +0.1 a cada edição; quem salvou fica registrado
  (migração 004).

### Alterado
- Mascaramento de senhas e detecção de tabelas citadas em `app/servicos/limpeza.py`, usados pelo editor e pelo
  importador.
- O seed lê os manuais de `seed/manuais` e de `dados/manuais` juntos (antes, uma pasta ou a outra).
- `/api/imagens` procura em `dados/imagens` e depois em `seed/imagens`.

## [0.2.0] - 2026-10-21

Estrutura e boas práticas a partir do plano em [docs/ideias-melhorias.txt](docs/ideias-melhorias.txt).

### Segurança
- O importador grava manuais e prints reais em `backend/dados/` (fora do git), não mais em `backend/seed/`.
  O `.gitignore` só aceita arquivos `DEMO.*` em `backend/seed/`.
- Os módulos e bancos reais ficam em `backend/modulos.json` (fora do git); o exemplo é `modulos.exemplo.json`.

### Adicionado
- Testes com pytest (71): diagrama, relações, vínculos, seed, migrações, autoria, manuais e PDF, modo de produção,
  mascaramento de senhas, regras de inferência do coletor e desempenho com 500 tabelas.
- Migrações numeradas (`backend/app/migrations/`, tabela `schema_version`), aplicadas pelo seed e na subida da API.
  Bancos da 0.1.0 são reconhecidos e atualizados sem perder dados.
- Autoria: quem validou ou descartou cada relação e quem vinculou cada tabela a uma tela, com data. Campo
  "Seu nome" no topo da interface, até ter login.
- Modo de produção num só processo: a API serve o build do frontend e o PDF funciona sem o Vite
  (`iniciar-producao.ps1`).
- `GET /api/saude` para monitoramento.
- `CHANGELOG.md` e tag por versão.

### Alterado
- `backend/app/main.py` dividido em `rotas/` (um router por assunto), `servicos/` e `config.py`.
- Diagrama ~15× mais rápido com catálogo grande (516 ms → ~35 ms com 500 tabelas / 2000 relações).
- No corte em 40 tabelas, o empate é decidido pelo nome: o diagrama sai igual a cada execução.
- Dependências separadas (`requirements.txt` só a API, `requirements-ferramentas.txt`, `requirements-dev.txt`)
  e travadas com `==`; no frontend, `@xyflow/react` e `elkjs` com versão exata.
- `readme.txt` virou [docs/arquitetura.md](docs/arquitetura.md), atualizado.
- O topo da interface cabe em tela de celular.

### Removido
- `backend/app/schema.sql` (substituído pelas migrações) e o `try/except` do `ALTER TABLE` no seed.

## [0.1.0] - 2026-10-21

Primeira versão: mapa do sistema, diagrama ER por tela, catálogo do banco com relações inferidas, manuais com
exportação para PDF, importador de documentos e sistema de exemplo (demo_pdv).

[0.2.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/releases/tag/v0.1.0
