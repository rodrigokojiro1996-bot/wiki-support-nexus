# Support Nexus — documentação técnica

Mapa vivo do sistema para equipes de suporte de ERP.

1. [Objetivo](#1-objetivo)
2. [Funcionalidades](#2-funcionalidades)
3. [Arquitetura](#3-arquitetura)
4. [Estrutura de pastas](#4-estrutura-de-pastas)
5. [Linguagens, frameworks e o porquê de cada escolha](#5-linguagens-frameworks-e-o-porquê-de-cada-escolha)
6. [Modelo de dados](#6-modelo-de-dados)
7. [Fluxos principais](#7-fluxos-principais)
8. [Validações e regras de negócio](#8-validações-e-regras-de-negócio)
9. [API](#9-api)
10. [Como instalar e rodar](#10-como-instalar-e-rodar)
11. [Testes](#11-testes)
12. [Segurança e dados sensíveis](#12-segurança-e-dados-sensíveis)
13. [Versões e commits](#13-versões-e-commits)
14. [Limitações conhecidas e próximos passos](#14-limitações-conhecidas-e-próximos-passos)


## 1. Objetivo

O Support Nexus é uma base de conhecimento para equipes de suporte de ERP. Uma wiki comum guarda só texto.
O Support Nexus liga três coisas que costumam ficar separadas:

- o **mapa do sistema**: os menus e telas do ERP, na mesma ordem em que aparecem para o usuário;
- o **catálogo do banco**: as tabelas, colunas e relações do banco de dados;
- os **manuais**: procedimentos, erros conhecidos e comandos de suporte.

Na prática, o atendente escolhe a tela que o cliente está usando e vê, no mesmo lugar: o caminho no menu, os
manuais daquela tela, as tabelas que a tela usa e um diagrama mostrando como essas tabelas se ligam.

O repositório traz um **sistema de exemplo**: um PDV de varejo fictício com 30 tabelas, menus e 6 manuais. Ele
serve para rodar o projeto sem nenhum banco real. Os módulos Retaguarda e Financeiro aparecem na interface como
"em breve".


## 2. Funcionalidades

**Mapa do sistema**
- Árvore de menus e telas, com atalho de teclado, código da janela e quantidade de manuais de cada item.
- Só um menu principal fica aberto por vez.
- Submenus que ainda não foram mapeados aparecem com a marca "a detalhar".
- Filtro por nome de menu ou tela.

**Ficha da tela, aba "Visão geral"**
- Caminho completo (ex.: PDV › Caixa › Fechamento de Caixa (F10)).
- Manuais vinculados.
- Tabelas que a tela usa. O vínculo pode ser "sugerido" (borda tracejada) ou "confirmado pela equipe" (borda
  contínua, com quem confirmou e quando), e a equipe pode vincular e remover tabelas.
- Ligações entre as tabelas da tela, com os botões Validar, Descartar e Desfazer, e quem validou ou descartou.

**Ficha da tela, aba "Tabelas" (diagrama ER)**
- Cada tabela é um cartão com colunas e tipos. As ligações saem da coluna exata e mostram a cardinalidade N → 1.
- As tabelas da tela ficam destacadas e as ligações delas aparecem tracejadas e animadas.
- Clicar numa tabela deixa acesas só ela e as vizinhas. Duplo clique abre a ficha da tabela.
- Opções: só chaves ou todas as colunas; 0, 1 ou 2 níveis de ligação; tabelas de apoio; busca por tabela ou
  coluna; zoom.

**Ficha da tabela**
- Engine, quantidade estimada de linhas, colunas e PK.
- Relações, cada uma com o seu estado.
- Telas que usam a tabela e manuais que a citam.

**Manuais**
- Modelo visual próprio: faixa lateral, traço de destaque, sumário automático, seções numeradas, OBS, notas,
  blocos SQL e prints.
- Exibem o caminho da tela no sistema.
- Botão "Exportar PDF": gera um A4 com cabeçalho, rodapé e número de página.

**Importação de documentos**
- Converte PDFs, documentos Word e anotações .txt em manuais. O destino de cada documento é definido por uma
  curadoria em JSON. Na importação, os autores são removidos, as senhas são mascaradas e os prints são extraídos
  na ordem do documento. O resultado vai para `backend/dados/`, fora do git.

**Coleta e inferência do banco**
- Lê somente a estrutura do MySQL (`information_schema`).
- Infere as relações que não existem como chave estrangeira.


## 3. Arquitetura

```
   MySQL (somente leitura)            Documentos de suporte
   information_schema                 (PDF / Word / .txt)
          |                                    |
          v                                    v
   coletor/coletar.py --> CSVs        backend/ferramentas/
   coletor/inferir.py --> catalogo     importar_processos.py
   (ou coletor/exemplo/demo_pdv)               |
          |                                    v
          |                        backend/dados/manuais/*.json  (real, fora do git)
          |                        backend/seed/manuais/DEMO.*   (exemplo)
          +-----------------+------------------+
                            v
                  backend/app/seed.py  (aplica as migrações e carrega)
                            |
                            v
              SQLite: backend/dados/nexus.db
                            |
                            v
             FastAPI (backend/app) :8010
                 |                       |
                 | JSON (/api)           | PDF: Playwright abre a
                 v                       v página de impressão no Edge
   desenvolvimento: React + Vite :5173 <--+
   produção: o próprio FastAPI serve frontend/dist na :8010
```

Decisões de arquitetura:

**a) Catálogo importado, não consulta ao vivo.** A wiki nunca se conecta ao banco do ERP. Um coletor tira uma
"foto" da estrutura e a wiki trabalha sobre essa cópia. Assim não há risco de carga ou de acesso indevido à
produção, a wiki funciona com o ERP fora do ar e comparar duas coletas mostra o que mudou na estrutura.

**b) Conhecimento da equipe separado do catálogo.** As validações de relação e os vínculos tela ↔ tabela ficam
em tabelas próprias. Por isso, reimportar o catálogo não apaga o trabalho da equipe.

**c) Conteúdo versionado em JSON.** Menus (`seed/menus_pdv.json`) e os manuais de exemplo
(`seed/manuais/DEMO.*.json`) ficam no git. O SQLite é um banco derivado, reconstruído com o seed. Isso permite
revisar alterações por diff e recriar o ambiente do zero. O conteúdo real (manuais e prints importados) fica em
`backend/dados/`, que não é versionado.

**d) Frontend e backend separados.** O backend expõe uma API JSON e o frontend consome essa API. Em
desenvolvimento, o Vite encaminha `/api` para a porta 8010. Em produção, um só processo: o FastAPI serve o build
do frontend e a API na mesma porta.

**e) Rotas finas, regras em serviços.** As rotas (`app/rotas/`) só leem a requisição e montam a resposta. As
regras ficam em `app/servicos/`; o algoritmo do diagrama não usa SQL, o que permite testá-lo isolado.


## 4. Estrutura de pastas

```
coletor/
  coletar.py               conecta no MySQL e exporta tabelas, colunas, FKs e índices (CSV)
  inferir.py               aplica as regras de inferência e gera catalogo.json
  dicionario.json          sinônimos de colunas (conhecimento da equipe)
  extrair_metadados.sql    mesmas consultas, para rodar manualmente no DBeaver
  exemplo/gerar_exemplo.py gera o banco fictício demo_pdv no formato do coletor
  exemplo/demo_pdv/        CSVs e catalogo.json do banco de exemplo
  tests/                   testes das regras de inferência

backend/
  app/main.py              cria o app: CORS, routers, prints, build do frontend
  app/config.py            caminhos, portas, CORS, PDF, limites do diagrama, módulos
  app/db.py                conexão SQLite, migrações e caminho do menu
  app/migrations/          NNN_nome.sql, aplicadas em ordem (tabela schema_version)
  app/rotas/               modulos, menus, catalogo, manuais, saude, frontend
  app/servicos/            diagrama (algoritmo puro), relacoes, manuais
  app/seed.py              carrega catálogo, menus e manuais no SQLite
  app/pdf.py               geração do PDF dos manuais (Playwright + Edge)
  modulos.exemplo.json     módulos e o banco de cada um (o real fica em modulos.json, fora do git)
  seed/menus_pdv.json      menus e telas do sistema e vínculos sugeridos
  seed/manuais/DEMO.*.json manuais de exemplo (um arquivo por código)
  ferramentas/importar_processos.py
                           conversão de PDF/Word/.txt em manuais
  ferramentas/curadoria.exemplo.json
                           modelo de curadoria (qual documento vai para qual tela)
  tests/                   pytest com banco temporário
  requirements*.txt        API / ferramentas / testes, com versões travadas

frontend/
  src/paginas/             MapaSistema, ManualPagina, ManualImpressao
  src/componentes/         MenuArvore, Diagrama, Documento, Marca, Topo
  src/estilo/              app.css (interface), documento.css (modelo do manual e impressão)
  src/api.ts, tipos.ts     cliente da API e tipos
  public/marca/            marca do Support Nexus e ícones dos módulos (SVG)

iniciar.ps1                desenvolvimento: sobe API (--reload) e Vite e abre o navegador
iniciar-producao.ps1       produção: build + seed + um só processo na 8010
pytest.ini                 configuração dos testes (rodar na raiz)
```


## 5. Linguagens, frameworks e o porquê de cada escolha

**Python (backend, coletor, ferramentas)**
- Bibliotecas maduras para todas as tarefas do projeto: MySQL, PDF, Word e imagens.
- Scripts simples de rodar e de manter pela própria equipe de suporte.

**FastAPI + Uvicorn (API)**
- Valida a entrada pelos tipos (Pydantic). Exemplo: o status de uma relação só aceita "documentada",
  "descartada" ou "sugerida".
- Gera documentação automática em `/docs`.
- Pouco código para uma API de leitura e escrita simples.

**SQLite (banco da wiki)**
- Não precisa de servidor. O arquivo é recriável a partir do seed.
- Dá conta com folga do volume do projeto (centenas de tabelas, dezenas de manuais).
- As migrações são SQL simples, portável para PostgreSQL ou MySQL se a wiki passar a ter muitos usuários
  editando ao mesmo tempo.

**PyMySQL (coletor)**
- Driver MySQL em Python puro, sem compilação no Windows. Compatível com versões antigas do MySQL (5.6+).

**pypdf, python-docx e Pillow (importação de manuais)**
- Leem texto e imagens dos PDFs e documentos Word na ordem original. O Pillow valida e converte os prints.
- Não exigem o Office instalado.

**Playwright + Microsoft Edge (PDF)**
- O PDF é gerado a partir da mesma página que o usuário vê, então tela e PDF nunca divergem.
- Usa o motor do navegador (Chromium), com cabeçalho e rodapé repetidos e número de página.
- Usa o Edge já instalado no Windows (`channel="msedge"`), sem baixar outro navegador. No Linux/Docker, troque
  `NEXUS_PDF_CANAL` para `chromium` e instale com `playwright install chromium`.
- Sem o gerador disponível, o frontend recorre à impressão do navegador ("Salvar como PDF").

**TypeScript + React 18 (frontend)**
- A interface tem bastante estado: árvore, ficha, abas, seleção no diagrama e filtros. Componentes React
  organizam isso bem.
- O TypeScript pega erros de contrato com a API em tempo de compilação (`tipos.ts` espelha as respostas da API).

**Vite (build e servidor de desenvolvimento)**
- Inicialização rápida, recarga instantânea e proxy `/api` para o backend sem configuração extra.

**React Router**
- Rotas com estado na URL (`?item=…&aba=tabelas&tabela=…`). Isso permite mandar o link de uma tela ou tabela
  específica para um colega.

**React Flow (@xyflow/react) + ELK (diagrama)**
- O React Flow desenha nós como componentes React. Cada tabela vira um cartão com colunas, e cada coluna tem
  pontos de conexão próprios, o que permite ligar coluna a coluna como em um diagrama ER.
- O ELK (Eclipse Layout Kernel, via elkjs) posiciona as tabelas da esquerda para a direita e roteia as ligações
  em ângulo reto, contornando os cartões: nenhuma linha passa por cima de uma tabela ou coluna.
- Cada coluna é uma porta fixa do cartão (saída à direita na FK, entrada à esquerda na PK), então a linha encaixa
  exatamente na altura da coluna. Por isso o cartão tem medidas fixas no CSS (borda 1px, cabeçalho 38px,
  linha 25px).
- Relações com chave composta desenham uma linha por par de colunas.

**CSS próprio (sem framework de UI)**
- O manual precisa de um layout fiel na tela e na impressão (regras `@page` e `@media print`). CSS escrito à mão
  dá esse controle.
- Cores definidas como variáveis: índigo `#4F5BD5` e ciano `#22B8CF` (marca), roxo `#7C3AED` (destaque no
  diagrama).


## 6. Modelo de dados

SQLite, estrutura definida pelas migrações em `backend/app/migrations/`.

| Tabela | Conteúdo |
|---|---|
| `modulos` | pdv / adm / fin e o schema de banco de referência de cada um |
| `tabelas` | tabelas do banco do ERP (engine, linhas estimadas, descrição) |
| `colunas` | colunas, tipo, PK e ordem |
| `relacoes` | relações: tipo `fk` (declarada) ou `sug` (inferida), com as colunas do JOIN e a regra que gerou a relação |
| `relacao_status` | decisão da equipe sobre cada relação (documentada ou descartada), observação, `por` e `em` |
| `importacoes` | data e resumo de cada coleta do catálogo |
| `menus` | árvore de menus e telas (id estável, ex.: `pdv.caixa.fechamento-de-caixa`) |
| `menu_tabelas` | vínculo tela ↔ tabela, com origem `sugerido` ou `equipe`, `por` e `em` |
| `manuais` | manuais (conteúdo em JSON), tela vinculada, tabelas citadas e documentos de origem |
| `schema_version` | migrações já aplicadas |

Os ids de menu são gerados a partir do título (slug). Por isso são estáveis entre execuções do seed e os vínculos
não se perdem.

**Migrações.** Cada mudança de estrutura é um arquivo novo `NNN_nome.sql` (nunca se edita um já publicado).
`db.migrar()` aplica, em ordem, só as que faltam, cada uma numa transação, e registra em `schema_version`. O seed
e a subida da API chamam `migrar()`. Um banco criado pela versão 0.1.0 (sem `schema_version`) é reconhecido pela
estrutura: versão 2 se `manuais` já tem a coluna `fontes`, senão versão 1.

| Migração | O que faz |
|---|---|
| `001_inicial` | estrutura da 0.1.0 |
| `002_manuais_fontes` | `manuais.fontes` (documentos de origem) |
| `003_autoria` | `relacao_status.por`, `menu_tabelas.por` e `menu_tabelas.em` |


## 7. Fluxos principais

### 7.1 Coleta da estrutura do banco
`coletar.py` lê, só do `information_schema`: TABLES, COLUMNS, KEY_COLUMN_USAGE e STATISTICS. Gera CSVs em
`coletor/saida/<schema>/`. Sem banco real, `exemplo/gerar_exemplo.py` gera os mesmos CSVs para o banco fictício
demo_pdv.

### 7.2 Inferência de relações (`inferir.py`)
Muitos bancos de ERP legados quase não declaram chaves estrangeiras (tabelas MyISAM nem suportam). Por isso as
relações são inferidas por regras, em ordem de prioridade:

| # | Regra | Quando | Resultado |
|---|---|---|---|
| 1 | `fk` | chave estrangeira declarada | confirmada |
| 2 | `dicionario` | sinônimos de colunas (ex.: loja_origem → lojas) | sugerida |
| 3 | `nome_tabela` | coluna com o nome da tabela (cidade → cidades) | sugerida |
| 4 | `pk_igual` | coluna com o mesmo nome de uma PK não genérica (id_cliente → clientes) | sugerida |
| 5 | `composta` | item que repete a chave composta do cabeçalho (nfce_itens → nfce por id_loja+numero+serie) | sugerida |

No banco de exemplo: 5 FKs declaradas e 43 relações inferidas, cobrindo 29 das 30 tabelas.

### 7.3 Carga (`app/seed.py`)
Aplica as migrações e importa módulos (`modulos.json` ou `modulos.exemplo.json`), catálogo, menus e manuais.
Pode ser executado quantas vezes for preciso: preserva `relacao_status` e os vínculos `menu_tabelas` com origem
"equipe". Os manuais vêm de `backend/dados/manuais/` quando essa pasta existe; senão, dos exemplos em
`backend/seed/manuais/`.

### 7.4 Importação de manuais (`ferramentas/importar_processos.py`)
Para cada manual definido em `curadoria.json`:
- Lê as fontes. Nos PDFs, só entram as imagens que cada página realmente desenha; nos documentos Word, texto e
  imagens seguem a ordem do documento.
- Remove ruído: cabeçalhos repetidos, sumário antigo, "Elaborado por" e autores (`autores.json`).
- Classifica cada parágrafo em seção, passo (mantém a numeração original), OBS, nota, SQL, subtítulo ou texto.
- Salva os prints em `backend/dados/imagens/<código>/`, ignorando logos repetidos e imagens muito pequenas.
- Detecta as tabelas citadas (nomes técnicos e blocos SQL).
- Grava o manual em `backend/dados/manuais/<código>.json`. Manuais com `"editado": true` não são sobrescritos.

### 7.5 Exportação de PDF
O botão chama `GET /api/manuais/{código}/pdf`. O backend abre a rota `/manuais/{código}/imprimir` no Edge
headless (no endereço de `NEXUS_FRONTEND`) e gera um A4 com cabeçalho, marca e rodapé com número de página. Em
desenvolvimento o endereço é o Vite (5173); em produção, a própria API (8010).

### 7.6 Diagrama
`servicos/diagrama.py` recebe as relações (sem as descartadas) e o foco, e devolve as tabelas incluídas, as
ligações entre elas e as tabelas de apoio ocultas. Um índice `{tabela: vizinhas}` é montado uma vez, e a rota
busca tabelas e colunas em duas consultas. Com 500 tabelas e 2000 relações a resposta fica abaixo de 50 ms.


## 8. Validações e regras de negócio

**Relações**
- Três estados visíveis, para nunca apresentar uma hipótese como fato:
  - *Confirmada*: existe FK no banco. Não pode ser alterada pela equipe.
  - *Documentada*: a equipe validou pela lógica do sistema.
  - *Sugerida*: inferida por nome. Ainda não foi validada.
  
  Descartadas somem da interface, mas continuam registradas.
- Uma relação sugerida só é criada se os tipos das colunas forem compatíveis (número com número, texto com
  texto). A exceção são as regras do dicionário, que registram o aviso "tipos diferentes".
- Colunas decimal com casas decimais (valores, quantidades) não viram chave por inferência de nome.
- PKs genéricas (id, codigo, num_seq, numero…) e colunas de data não geram relação pela regra `pk_igual`.
- Cada coluna recebe no máximo uma relação inferida simples: vale a regra de maior prioridade. A regra de chave
  composta é avaliada à parte.
- Tabelas com 40 ou mais referências são marcadas como "de apoio". O diagrama não se expande a partir delas,
  porque isso traria dezenas de tabelas.
- O diagrama mostra no máximo 40 tabelas. Ficam as mais conectadas às tabelas da tela; no empate, a ordem do
  nome, para o diagrama sair sempre igual.

**Vínculos tela ↔ tabela**
- O vínculo só é aceito se a tabela existir no catálogo (o frontend valida antes de enviar).
- Sugestões vindas do seed ficam como "sugerido". Ao salvar pela interface, o vínculo passa a ser da "equipe".
  Um vínculo que já era da equipe mantém o autor e a data originais.

**Autoria**
- Validar, descartar e vincular registram `por` (quem) e `em` (quando). Até ter login, o autor é o nome que a
  pessoa informa no topo da interface, guardado no navegador e enviado no cabeçalho `X-Usuario`. Sem nome, a
  alteração é aceita com autor vazio.

**API**
- Pydantic valida o corpo das requisições. O status de relação é limitado a documentada | descartada | sugerida.
- Módulo, menu, tabela, relação ou manual inexistente → HTTP 404 com mensagem.
- Falha na geração do PDF → HTTP 503 com o motivo. O frontend então recorre à impressão do navegador.

**Seed**
- Avisa quando um manual aponta para um menu inexistente e grava o manual sem vínculo.
- Vínculos sugeridos para tabelas que não existem no catálogo são ignorados.

**Importação de documentos**
- Senhas são mascaradas (`--password=…`, `password=…` e a lista do arquivo `segredos.txt`, que não vai para o git).
- Nomes de autores e linhas "Elaborado/Revisado/Aprovado por" são removidos.
- Arquivo de origem inexistente ou menu inexistente aparecem no relatório final da importação.


## 9. API

Prefixo `/api`. Documentação interativa em http://localhost:8010/docs.

| Método | Rota | O que faz |
|---|---|---|
| GET | `/saude` | `{"ok": true, "versao": "…", "schema": N}`; 503 se o banco não responder |
| GET | `/modulos` | módulos e data da última coleta |
| GET | `/modulos/{m}/menus` | árvore de menus com contagens |
| GET | `/menus/{id}` | ficha da tela: caminho, tabelas, relações, manuais e opções internas |
| PUT | `/menus/{id}/tabelas` | salva os vínculos tela ↔ tabela (autor em `X-Usuario`) |
| GET | `/modulos/{m}/catalogo` | tabelas e relações (sem colunas) |
| GET | `/modulos/{m}/tabelas/{nome}` | ficha da tabela |
| GET | `/modulos/{m}/diagrama?tabelas=a,b&nivel=1&apoio=false` | diagrama ER em volta das tabelas |
| PUT | `/modulos/{m}/relacoes/status` | valida, descarta ou desfaz uma relação (autor em `X-Usuario`) |
| GET | `/manuais?modulo=pdv` | lista de manuais |
| GET | `/manuais/{código}` | manual completo |
| GET | `/manuais/{código}/pdf` | download do PDF |
| GET | `/imagens/{código}/{arquivo}` | prints dos manuais |

No modo de produção, qualquer caminho fora de `/api` e `/docs` devolve o build do frontend (com `index.html` como
alternativa, para o React Router).


## 10. Como instalar e rodar

Requisitos: Windows com Microsoft Edge, Python 3.12 ou superior e Node.js 20 ou superior.

**Backend**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-ferramentas.txt   # só para importar manuais
.venv\Scripts\python.exe -m app.seed                                       # carrega o sistema de exemplo
```

**Frontend**
```powershell
cd frontend
npm install
```

**Desenvolvimento** — `.\iniciar.ps1` (API com recarga em http://localhost:8010, interface em
http://localhost:5173).

**Produção** — `.\iniciar-producao.ps1` compila o frontend, roda o seed e sobe um só processo em
http://localhost:8010, sem `--reload`. O PDF funciona sem o Vite. Use `-Rede` para aceitar acesso de outras
máquinas. Para monitoramento, `GET /api/saude`.

**Usar com um banco real**
```powershell
cd coletor
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env                         # host, usuário (de preferência só com SELECT) e senha
.venv\Scripts\python.exe coletar.py meu_banco
.venv\Scripts\python.exe inferir.py meu_banco
```
Depois copie `backend/modulos.exemplo.json` para `backend/modulos.json` (fora do git), aponte o módulo para
`meu_banco`, escreva os menus do sistema em `backend/seed/menus_pdv.json` e rode o seed de novo.

**Variáveis de ambiente**

| Variável | Padrão | Para quê |
|---|---|---|
| `NEXUS_FRONTEND` | `http://localhost:5173` | onde o gerador de PDF abre a página de impressão |
| `NEXUS_PDF_CANAL` | `msedge` | navegador do Playwright (`chromium` no Linux/Docker) |


## 11. Testes

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd ..
backend\.venv\Scripts\python.exe -m pytest -q      # na raiz do projeto
```

- Cada teste usa um SQLite temporário carregado com o demo_pdv, isolado de qualquer dado real da máquina.
- Cobrem: algoritmo do diagrama (níveis, apoio, corte em 40, equivalência com a 0.1.0), relações, vínculos,
  seed idempotente, migrações (banco novo e banco da 0.1.0 terminam com a mesma estrutura), autoria, manuais e
  PDF, modo de produção, mascaramento de senhas, regras de inferência do coletor e desempenho com 500 tabelas.
- Regra: `pytest -q` e `npm run build` verdes antes de cada commit.


## 12. Segurança e dados sensíveis

- O coletor lê somente o `information_schema`: estrutura, nunca dados de clientes, vendas ou produtos.
- Ficam fora do git (`.gitignore`):

  | Caminho | O que é |
  |---|---|
  | `coletor/.env` | credenciais do banco |
  | `backend/ferramentas/segredos.txt` | senhas a mascarar na importação |
  | `backend/ferramentas/curadoria.json`, `autores.json` | dados reais da importação |
  | `coletor/saida/` | estrutura de um banco real |
  | `backend/dados/` | SQLite gerado, manuais e prints importados |
  | `backend/modulos.json` | módulos e bancos reais |

- Em `backend/seed/` o `.gitignore` só aceita os arquivos `DEMO.*`: um manual real que caia ali por engano não é
  versionado.
- Os manuais importados passam por mascaramento de senhas e remoção de autores antes de serem gravados.
- A interface não executa SQL no banco do ERP. Os blocos SQL dos manuais são só texto para o analista copiar.
- O modo de produção serve só arquivos de dentro de `frontend/dist`.
- **O repositório é público**: nunca commitar manuais reais, prints, catálogo de banco real, `.env`, nomes de
  servidores ou de clientes.


## 13. Versões e commits

- Uma tag por versão (`v0.1.0`, `v0.2.0`…) e o [CHANGELOG](../CHANGELOG.md) atualizado junto.
- A versão fica em `backend/app/config.py` (`VERSAO`) e em `frontend/package.json`.
- Commit antes de publicar ou usar uma versão.
- Mensagens no padrão Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `perf:`, `build:`.


## 14. Limitações conhecidas e próximos passos

- **Login**: a autoria hoje é o nome informado na interface, sem verificação. Antes de abrir para uma equipe
  grande, incluir login (conta Microsoft da empresa via Entra ID, ou senha simples se for só uso local), com
  leitura livre para logados e alterações só para o perfil "curador".
- Os manuais não têm editor na interface. A edição é feita nos arquivos JSON.
- Módulos Retaguarda e Financeiro: a estrutura está pronta (tabela `modulos`), falta mapear menus e bancos.
- Relações entre bancos de módulos diferentes (ex.: PDV ← Retaguarda) como um quarto tipo de ligação.
- Integração com a ferramenta de chamados da equipe de suporte.
- Testes do frontend (Vitest) para `caminhoTexto` e a montagem do layout ELK.
- Dockerfile com `HEALTHCHECK` em `/api/saude`, se a wiki for para um servidor.
