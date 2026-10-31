# Changelog

Mudanças de cada versão do Support Nexus. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

### Adicionado
- Ligar colunas no diagrama: clique numa coluna e na coluna de outra tabela; o diagrama pergunta se estão
  relacionadas, com o sentido sugerido (a chave primária fica no lado 1, dá para inverter) e uma observação
  opcional. **Validar** grava a relação como documentada pela equipe, com quem ligou e quando, e o diagrama se
  redesenha com ela; **Descartar** (ou Esc) volta a navegar sem gravar nada. Se o catálogo já sugeria essa ligação,
  validar só confirma a sugestão; colunas já ligadas (pelo banco ou pela equipe) são recusadas. As relações ligadas
  pela equipe ficam numa tabela própria (migração 007, `relacoes_equipe`) e sobrevivem a uma nova importação do
  catálogo; desfazer pela ficha apaga a ligação. Entram na cobertura e nas contribuições do Grafana.
- Rodapé "+ N colunas" dos cartões do diagrama clicável: seleciona a tabela e mostra todas as colunas só dela (para
  ligar uma coluna que não é chave), centralizando o diagrama nela; "− recolher colunas" volta ao resumo.

## [0.4.0] - 2026-10-31

### Adicionado
- Painel "Support Nexus · Branches do Git" no Grafana: toda branch enviada ao GitHub (existentes e apagadas), situação
  do PR mais recente, autor, destino, última atualização, pushes recentes e histórico de pull requests. Lê a API
  pública do GitHub pelo plugin Infinity; token opcional (`GITHUB_TOKEN`) para sair do limite de 60 consultas por
  hora. No servidor da Oracle, `deploy/oracle/docker-compose.grafana.yml` sobe um Grafana só com esse painel em
  `/grafana/`, atrás da senha da entrada.
- Ícone do SPA ADM com a cruz do logo da rede (quatro braços em H e o redemoinho no centro), em branco sobre o
  turquesa da marca.

### Alterado
- Dependências: Python 3.15 e Node 26 nas imagens, TypeScript 7, FastAPI 0.161, react-router-dom 7.18, elkjs 0.12 e
  correções do pip.

### Adicionado
- Ícones dos módulos SPA PDV, SPA ADM e SPA FIN redesenhados em SVG nas cores da marca: nítidos em qualquer tamanho
  e nos dois temas (eram PNGs de 64 px, um deles com fundo branco). No tema escuro, o logo da rede fica sobre uma
  placa branca (o logo completo só funciona sobre branco) e some o contorno claro das bordas. Barra do editor e da
  página do manual com as ações numa linha própria abaixo de 1100 px, o Salvar à direita.
- Layout para qualquer tamanho de janela, de 360 px (celular) a 2560 px, e com zoom de 200%, sem rolagem
  horizontal. Topo em duas linhas abaixo de 1100 px; no celular, módulos lado a lado, tema só com o ícone e alvos de
  toque de 44 px (também em telas de toque); manual em A4 com margens menores no celular (a impressão não muda).
  Em telas grandes o conteúdo cresce junto (topo, ficha, manual e editor; o diagrama não, para não atrapalhar o
  arrastar), as colunas acompanham a largura e o manual da tela e os chamados ficam lado a lado.
- Dois tipos de manual por tela: o **manual da tela** (passo a passo dos processos e funcionalidades, um por tela)
  e os **chamados frequentes** (problemas recorrentes da tela e como resolver, quantos forem preciso). A ficha da
  tela mostra os dois; o chamado novo já vem com Sintoma, Causa e Solução; a página do manual da tela lista os
  chamados frequentes dela. Migração 006 (`manuais.tipo`); os manuais existentes viram manual da tela.
- Botão de tema no topo: claro (padrão) ou escuro, guardado no navegador. No escuro, as cores da marca seguem as
  mesmas (botões laranja com letra branca, turquesa em links e foco); o manual continua papel branco e o PDF sai
  claro. Diagrama com as cores escuras do React Flow.

### Corrigido
- Módulos que usam o mesmo banco (o financeiro usa o do administrativo): o catálogo é importado uma vez só.
- Manual e tabelas só em tela final (item do menu sem opções depois dele). Menus principais e submenus só abrem e
  fecham a árvore; submenu ainda não detalhado não abre ficha; link direto para um menu mostra as opções dele; a
  API recusa manual ligado a um menu; a tela inicial conta telas, não itens de menu.

### Adicionado
- Vários módulos no mapa: os módulos com banco mapeado viram links no topo e o mapa mostra o módulo escolhido
  (menus, catálogo, diagrama e manuais); o da tela aberta fica destacado. Menus reais de cada módulo em
  `menus_reais/menus_<módulo>.json` (no servidor, `~/nexus-real/menus/`).
- Nomes dos módulos no topo e no mapa vêm do `modulos.json` do servidor (ex.: "SPA PDV"), em vez de fixos no código;
  módulo com banco mapeado fica ativo, os outros aparecem como "em breve".
- Estrutura real do sistema no lugar do exemplo, sem nada no git: menus reais em `dados/menus_<módulo>.json`
  (preferidos ao exemplo de `seed/`), catálogo do coletor e `modulos.json`. Na troca, os menus que saíram do
  arquivo são removidos, os manuais de exemplo saem e os da equipe ficam (sem tela, se a tela não existir mais).
  Tela inicial: selo "Sistema de exemplo" só com o exemplo, "Começar por" a primeira tela com tabelas e a
  lista "Manuais sem tela". No servidor da Oracle, `deploy/oracle/docker-compose.dados-reais.yml`.
- Rodapé "Manual alterado em DD/MM/AAAA às HH:MM" na tela e no PDF sempre que alguém salva o manual pelo editor,
  na hora de Brasília (`America/Sao_Paulo`, qualquer que seja o fuso do servidor). Manuais nunca alterados pela
  interface mantêm "Documento gerado pelo Support Nexus". Migração 005 (`manuais.alterado_em`) e `tzdata`.

### Alterado
- Identidade visual da rede Farmácias Associadas: turquesa `#00B2A9` e laranja `#F36F21` (a cor do logo),
  botões principais em laranja com letra branca, links e foco em turquesa escuro, fonte Inter, logo da rede no
  topo e no cabeçalho do manual e do PDF, favicon com a cruz da rede e ícones dos módulos. As funcionalidades
  não mudam.

### Adicionado
- Homologação: `NEXUS_AMBIENTE=homologacao` mostra a faixa "Ambiente de homologação" em todas as telas, e
  `/api/saude` informa o ambiente. Guia de `docker run` sem o compose em `docs/docker.md` (seção 10).
- Fora dos buscadores: `robots.txt` e o cabeçalho `X-Robots-Tag: noindex, nofollow` em toda resposta.
- Servidor de testes na Oracle Cloud (`deploy/oracle/`, guia em `docs/oracle-cloud.md`): Caddy na frente com HTTPS
  automático, senha única na entrada (bcrypt), `/metrics` e `/docs` bloqueados, cabeçalhos de segurança e limite de
  10 MB por envio; API sem porta própria para fora; scripts para preparar o servidor (Docker, fuso, atualizações
  automáticas, firewall da imagem da Oracle, swap), configurar o `.env` e fazer backup com rotação. Liga a faixa de homologação.
  Imagem testada em ARM (processador do plano gratuito).

### Corrigido
- O contêiner gravava as datas em UTC (3 h adiantado em relação a Brasília): o compose agora define o fuso
  (`NEXUS_FUSO`, padrão `America/Sao_Paulo`).

### Alterado
- A imagem tem o `tini` como PID 1 e o Chromium do PDF roda com `--disable-dev-shm-usage`: funciona num
  `docker run` simples, sem o `init: true` e o `shm_size` do compose.

## [0.3.0] - 2026-10-22

### Adicionado
- "Importar documento" na interface: no mapa (ao lado de "+ Novo manual" e de "Criar manual para esta tela") e
  no editor de um manual novo. Escolher ou arrastar o arquivo abre o editor preenchido, com a prévia e os avisos da
  conversão no topo. Nada é salvo até clicar em Salvar manual; erros (tamanho, tipo, `.doc`, `.docm`) aparecem
  como texto claro.
- Exemplos de formatação compartilhados (`backend/tests/dados/importacao/formatacao.json`) testados nos dois lados:
  o importador gera os blocos esperados (pytest) e esses blocos aparecem na tela igual ao mesmo texto colado no
  editor (Vitest, `npm test`, novo no CI).
- Importação de Word pelos estilos: Título 1 abre seção, Título 2 em diante vira subtítulo, lista numerada vira
  passo com a numeração do documento, lista com marcador vira lista (com subitens) e parágrafo em fonte
  monoespaçada vira bloco SQL.
- `POST /api/manuais/importar?modulo=<id>`: um documento (PDF, Word `.docx`, `.txt` ou `.md`) vira um rascunho de
  manual (título, seções, prints, tabelas citadas e avisos) para revisar no editor. Não salva nada; quem salva é o
  `POST /api/manuais`, que agora aceita `fontes` (os documentos de origem).
- Segurança da importação: tipo conferido pelos bytes, limite de 20 MB, recusa explicada de `.doc` e `.docm`,
  proteção contra zip bomb, limites de 200 páginas e 300 imagens, PDF com senha recusado.
- Avisos no rascunho: PDF escaneado, documento sem títulos, imagens repetidas ignoradas, senhas mascaradas, tabela
  do Word em texto e `.txt` em cp1252.
- Métricas `nexus_importacoes_total{formato,resultado}` e `nexus_importacao_duration_seconds{formato}`.
- CI no GitHub Actions (`.github/workflows/ci.yml`) em todo PR e push na main: pytest, build do frontend
  (com checagem de tipos), `promtool` (configuração e testes das regras de alerta) e build da imagem Docker.
  Actions travadas por SHA, permissão só de leitura e execução antiga cancelada a cada push novo.
- Template de pull request (o que muda, por que, como testei, checklist) e templates de issue "Bug" e
  "Melhoria" (`.github/`). Falha de segurança vai para o aviso privado, não para issue pública.
- Dependabot (`.github/dependabot.yml`): PRs semanais de atualização para pip (backend e coletor), npm, imagens do
  Dockerfile e do docker-compose e GitHub Actions, com os patches agrupados. Alertas de dependência, secret scanning
  e push protection ligados no repositório.
- Licença MIT (`LICENSE`), `SECURITY.md` (como avisar uma falha pelo aviso privado do GitHub), `CONTRIBUTING.md`
  (como rodar, testar, padrão de branch, commit e PR, e a regra de nunca commitar conteúdo real) e `CODEOWNERS`.
- Release automática (`.github/workflows/release.yml`): o push de uma tag `v*` cria a Release do GitHub com a seção
  daquela versão do CHANGELOG, e falha se a versão não tiver seção. Releases das tags v0.1.0 e v0.2.0 publicadas.
- Editor de manuais na interface: "Criar manual para esta tela" na Visão geral, "+ Novo manual" e "Editar".
  Blocos iguais aos dos manuais existentes, prévia ao vivo e prints com Ctrl+V ou arrastando.
- `POST /api/manuais`, `PUT /api/manuais/{código}` e `POST /api/imagens`.
- Blocos de texto e nota com várias linhas saem formatados como foram colados: parágrafos, listas com subitens
  (Tab), títulos de trecho (linha com emoji, "1." ou terminada em ":"), `[ Botão ]` como botão e `->` como seta.
  Passos e OBS mantêm as quebras de linha. Manuais de uma linha por bloco não mudam.
- Código automático por módulo (`PDV.001`…) e versão +0.1 a cada edição; quem salvou fica registrado
  (migração 004).
- Docker: `Dockerfile` em duas etapas (imagens base travadas por versão e digest, usuário sem privilégios,
  `HEALTHCHECK` em `/api/saude`, Chromium para o PDF), `docker-compose.yml` (porta só local, volume `nexus-dados`,
  `init`, `shm_size`, limite de memória) e guia em `docs/docker.md`. Imagem de 1,5 GB (Chromium sem o
  "headless shell").

- Monitoramento: a API publica métricas em `/metrics` (requisições, tempo de resposta por rota, tempo e falhas do
  PDF, memória e CPU); Prometheus coleta a cada 15 s e avalia 4 regras de alerta (com testes do `promtool`);
  Grafana com o painel "Support Nexus · API" provisionado por arquivo. Senha do Grafana no `.env`. Guia em
  `docs/monitoramento.md`.

- Painel "Support Nexus · Cobertura da wiki" no Grafana: telas com e sem manual (total e por menu), vínculos
  confirmados, relações por estado, evolução no tempo e contribuições dos últimos 7 dias por pessoa e tipo. Os
  números vêm de métricas `nexus_wiki_*`, calculadas no banco a cada coleta do Prometheus.

### Corrigido
- O importador apagava o `*` de comandos SQL (`SELECT * FROM` virava `SELECT  FROM`): a linha de SQL agora é
  reconhecida antes da limpeza de asteriscos soltos.
- O importador em lote (`ferramentas/importar_processos.py`) gravava todo manual no módulo PDV. Agora o módulo vem
  do item da curadoria (campo `modulo` ou o prefixo do id do menu) e as tabelas citadas são procuradas no banco desse
  módulo; o campo solto `banco` do `curadoria.json` deixou de ser usado. Módulo inexistente é avisado e o manual não
  é importado.
- O seed regravava a data `atualizado_em` de todos os manuais a cada execução (e o contêiner roda o seed a cada
  subida): um manual parado há meses aparecia como "atualizado hoje". Agora a data só muda quando o conteúdo muda,
  e o editor grava a data real no JSON.
- Fontes da interface (Manrope, JetBrains Mono) empacotadas no build em vez de baixadas do Google Fonts a cada
  acesso: funcionam sem internet e atrás de antivírus/proxy.
- PDF no Linux/Docker: alternativas abertas Liberation Sans/Mono para Segoe UI/Consolas (o SQL saía numa fonte
  chinesa monoespaçada), e o gerador espera as fontes carregarem antes de imprimir.

### Alterado
- Itens de lista importados (e a linha terminada em ":" que os apresenta) ficam num bloco de texto só, com Tab
  nos subitens, como o editor guarda uma lista colada: aparecem como lista, não como parágrafos soltos com "•".
- pypdf, python-docx e pillow passaram para `requirements.txt` e para a imagem Docker (a API usa);
  `requirements-ferramentas.txt` deixou de existir.
- Importação em lote: `.txt` com BOM não deixa mais o caractere invisível na primeira linha, logos repetidos em
  documentos Word são descartados (contando as referências, não os arquivos), e documento recusado vira um
  problema na lista em vez de interromper o lote. A curadoria real de teste gerou o mesmo resultado de antes.
- A conversão de documentos em manuais saiu do script de lote para `app/servicos/importacao.py` (`converter()`),
  base da importação pela interface. O lote ficou só com a curadoria e gera o mesmo JSON e os mesmos prints de
  antes. Documentos fictícios de teste em `backend/tests/dados/importacao/`.
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

[Não publicado]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/releases/tag/v0.1.0
