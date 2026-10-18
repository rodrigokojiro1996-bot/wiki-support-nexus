===============================================================================
 SUPPORT NEXUS — Mapa vivo do sistema
 Documentação técnica
===============================================================================

Sumário
  1. Objetivo
  2. Funcionalidades
  3. Arquitetura
  4. Estrutura de pastas
  5. Linguagens, frameworks e o porquê de cada escolha
  6. Modelo de dados
  7. Fluxos principais
  8. Validações e regras de negócio
  9. API (endpoints)
 10. Como instalar e rodar
 11. Segurança e dados sensíveis
 12. Limitações conhecidas e próximos passos


-------------------------------------------------------------------------------
 1. OBJETIVO
-------------------------------------------------------------------------------

O Support Nexus é uma base de conhecimento para equipes de suporte de ERP.
Uma wiki comum guarda só texto. O Support Nexus liga três coisas que costumam
ficar separadas:

  - o MAPA DO SISTEMA: os menus e telas do ERP, na mesma ordem em que aparecem
    para o usuário;
  - o CATÁLOGO DO BANCO: as tabelas, colunas e relações do banco de dados;
  - os MANUAIS: procedimentos, erros conhecidos e comandos de suporte.

Na prática, o atendente escolhe a tela que o cliente está usando e vê, no mesmo
lugar:
  - o caminho no menu;
  - os manuais daquela tela;
  - as tabelas que a tela usa;
  - um diagrama mostrando como essas tabelas se ligam.

O repositório traz um SISTEMA DE EXEMPLO: um PDV de varejo fictício com 30
tabelas, menus e 6 manuais. Ele serve para rodar o projeto sem nenhum banco
real. Os módulos Retaguarda e Financeiro aparecem na interface como "em
breve".


-------------------------------------------------------------------------------
 2. FUNCIONALIDADES
-------------------------------------------------------------------------------

Mapa do sistema
  - Árvore de menus e telas, com atalho de teclado, código da janela e
    quantidade de manuais de cada item.
  - Só um menu principal fica aberto por vez.
  - Submenus que ainda não foram mapeados aparecem com a marca "a detalhar".
  - Filtro por nome de menu ou tela.

Ficha da tela, aba "Visão geral"
  - Caminho completo (ex.: PDV > Caixa > Fechamento de Caixa (F10)).
  - Manuais vinculados.
  - Tabelas que a tela usa. O vínculo pode ser "sugerido" (borda tracejada) ou
    "confirmado pela equipe" (borda contínua), e a equipe pode vincular e
    remover tabelas.
  - Ligações entre as tabelas da tela, com os botões Validar, Descartar e
    Desfazer.

Ficha da tela, aba "Tabelas" (diagrama ER)
  - Cada tabela é um cartão com colunas e tipos. As ligações saem da coluna
    exata e mostram a cardinalidade N → 1.
  - As tabelas da tela ficam destacadas e as ligações delas aparecem
    tracejadas e animadas.
  - Clicar numa tabela deixa acesas só ela e as vizinhas. Duplo clique abre a
    ficha da tabela.
  - Opções: só chaves ou todas as colunas; 0, 1 ou 2 níveis de ligação;
    tabelas de apoio; busca por tabela ou coluna; zoom.

Ficha da tabela
  - Engine, quantidade estimada de linhas, colunas e PK.
  - Relações, cada uma com o seu estado.
  - Telas que usam a tabela e manuais que a citam.

Manuais
  - Modelo visual próprio: faixa lateral, traço de destaque, sumário
    automático, seções numeradas, OBS, notas, blocos SQL e prints.
  - Exibem o caminho da tela no sistema.
  - Botão "Exportar PDF": gera um A4 com cabeçalho, rodapé e número de página.

Importação de documentos
  - Converte PDFs, documentos Word e anotações .txt em manuais. O destino de
    cada documento é definido por uma curadoria em JSON. Na importação, os
    autores são removidos, as senhas são mascaradas e os prints são extraídos
    na ordem do documento.

Coleta e inferência do banco
  - Lê somente a estrutura do MySQL (information_schema).
  - Infere as relações que não existem como chave estrangeira.


-------------------------------------------------------------------------------
 3. ARQUITETURA
-------------------------------------------------------------------------------

   MySQL (somente leitura)            Documentos de suporte
   information_schema                 (PDF / Word / .txt)
          |                                    |
          v                                    v
   coletor/coletar.py --> CSVs        backend/ferramentas/
   coletor/inferir.py --> catalogo     importar_processos.py
   (ou coletor/exemplo/demo_pdv)               |
          |                                    v
          |                        backend/seed/manuais/*.json
          +-----------------+------------------+
                            v
                  backend/app/seed.py
                            |
                            v
              SQLite: backend/dados/nexus.db
                            |
                            v
             FastAPI (backend/app/main.py) :8010
                 |                       |
                 | JSON (/api)           | PDF: Playwright abre a
                 v                       v página de impressão no Edge
        React + Vite (frontend/) :5173  <--+

Decisões de arquitetura:

  a) Catálogo importado, não consulta ao vivo.
     A wiki nunca se conecta ao banco do ERP. Um coletor tira uma "foto" da
     estrutura e a wiki trabalha sobre essa cópia. Assim:
       - não há risco de carga ou de acesso indevido à produção;
       - a wiki funciona com o ERP fora do ar;
       - comparar duas coletas mostra o que mudou na estrutura.

  b) Conhecimento da equipe separado do catálogo.
     As validações de relação e os vínculos tela ↔ tabela ficam em tabelas
     próprias. Por isso, reimportar o catálogo não apaga o trabalho da equipe.

  c) Conteúdo versionado em JSON.
     Menus (seed/menus_pdv.json) e manuais (seed/manuais/*.json) ficam em
     arquivos no git. O SQLite é um banco derivado, reconstruído com o seed.
     Isso permite revisar alterações por diff e recriar o ambiente do zero.

  d) Frontend e backend separados.
     O backend expõe uma API JSON e o frontend consome essa API. Em
     desenvolvimento, o Vite encaminha /api para a porta 8010.


-------------------------------------------------------------------------------
 4. ESTRUTURA DE PASTAS
-------------------------------------------------------------------------------

  coletor/
    coletar.py               conecta no MySQL e exporta tabelas, colunas, FKs
                             e índices (CSV)
    inferir.py               aplica as regras de inferência e gera
                             catalogo.json
    dicionario.json          sinônimos de colunas (conhecimento da equipe)
    extrair_metadados.sql    mesmas consultas, para rodar manualmente no
                             DBeaver
    exemplo/gerar_exemplo.py gera o banco fictício demo_pdv no formato do
                             coletor
    exemplo/demo_pdv/        CSVs e catalogo.json do banco de exemplo

  backend/
    app/main.py              API FastAPI
    app/db.py                conexão SQLite e utilitários
    app/schema.sql           estrutura do banco da wiki
    app/seed.py              carrega catálogo, menus e manuais no SQLite
    app/pdf.py               geração do PDF dos manuais (Playwright + Edge)
    seed/menus_pdv.json      menus e telas do sistema e vínculos sugeridos
    seed/manuais/*.json      manuais (um arquivo por código)
    ferramentas/importar_processos.py
                             conversão de PDF/Word/.txt em manuais
    ferramentas/curadoria.exemplo.json
                             modelo de curadoria (qual documento vai para qual
                             tela)

  frontend/
    src/paginas/             MapaSistema, ManualPagina, ManualImpressao
    src/componentes/         MenuArvore, Diagrama, Documento, Marca, Topo
    src/estilo/              app.css (interface), documento.css (modelo do
                             manual e impressão)
    src/api.ts, tipos.ts     cliente da API e tipos
    public/marca/            marca do Support Nexus e ícones dos módulos (SVG)

  iniciar.ps1                sobe API e frontend e abre o navegador


-------------------------------------------------------------------------------
 5. LINGUAGENS, FRAMEWORKS E O PORQUÊ DE CADA ESCOLHA
-------------------------------------------------------------------------------

Python (backend, coletor, ferramentas)
  - Bibliotecas maduras para todas as tarefas do projeto: MySQL, PDF, Word e
    imagens.
  - Scripts simples de rodar e de manter pela própria equipe de suporte.

FastAPI + Uvicorn (API)
  - Valida a entrada pelos tipos (Pydantic). Exemplo: o status de uma relação
    só aceita "documentada", "descartada" ou "sugerida".
  - Gera documentação automática em /docs.
  - Pouco código para uma API de leitura e escrita simples.

SQLite (banco da wiki)
  - Não precisa de servidor. O arquivo é recriável a partir do seed.
  - Dá conta com folga do volume do projeto (centenas de tabelas, dezenas de
    manuais).
  - O schema.sql é portável para PostgreSQL ou MySQL se a wiki passar a ter
    muitos usuários editando ao mesmo tempo.

PyMySQL (coletor)
  - Driver MySQL em Python puro, sem compilação no Windows. Compatível com
    versões antigas do MySQL (5.6+).

pypdf, python-docx e Pillow (importação de manuais)
  - Leem texto e imagens dos PDFs e documentos Word na ordem original.
  - O Pillow valida e converte os prints.
  - Não exigem o Office instalado.

Playwright + Microsoft Edge (PDF)
  - O PDF é gerado a partir da mesma página que o usuário vê, então tela e PDF
    nunca divergem.
  - Usa o motor do navegador (Chromium), com cabeçalho e rodapé repetidos e
    número de página.
  - Usa o Edge já instalado no Windows (channel="msedge"), sem baixar outro
    navegador.
  - Sem o gerador disponível, o frontend recorre à impressão do navegador
    ("Salvar como PDF").

TypeScript + React 18 (frontend)
  - A interface tem bastante estado: árvore, ficha, abas, seleção no diagrama e
    filtros. Componentes React organizam isso bem.
  - O TypeScript pega erros de contrato com a API em tempo de compilação
    (tipos.ts espelha as respostas da API).

Vite (build e servidor de desenvolvimento)
  - Inicialização rápida, recarga instantânea e proxy /api para o backend sem
    configuração extra.

React Router
  - Rotas com estado na URL (?item=…&aba=tabelas&tabela=…). Isso permite
    mandar o link de uma tela ou tabela específica para um colega.

React Flow (@xyflow/react) + ELK (diagrama)
  - O React Flow desenha nós como componentes React. Assim cada tabela vira um
    cartão com colunas, e cada coluna tem pontos de conexão próprios, o que
    permite ligar coluna a coluna como em um diagrama ER.
  - O ELK (Eclipse Layout Kernel, via elkjs) posiciona as tabelas da esquerda
    para a direita e roteia as ligações em ângulo reto, contornando os
    cartões: nenhuma linha passa por cima de uma tabela ou coluna.
  - Cada coluna é uma porta fixa do cartão (saída à direita na FK, entrada à
    esquerda na PK), então a linha encaixa exatamente na altura da coluna.
    Por isso o cartão tem medidas fixas no CSS (borda 1px, cabeçalho 38px,
    linha 25px).
  - Relações com chave composta desenham uma linha por par de colunas.

CSS próprio (sem framework de UI)
  - O manual precisa de um layout fiel na tela e na impressão (regras @page e
    @media print). CSS escrito à mão dá esse controle.
  - Cores definidas como variáveis:
      índigo #4F5BD5 e ciano #22B8CF   marca
      roxo   #7C3AED                   destaque no diagrama


-------------------------------------------------------------------------------
 6. MODELO DE DADOS (SQLite — backend/app/schema.sql)
-------------------------------------------------------------------------------

  modulos         pdv / adm / fin e o schema de banco de referência de cada um
  tabelas         tabelas do banco do ERP (engine, linhas estimadas, descrição)
  colunas         colunas, tipo, PK e ordem
  relacoes        relações. tipo "fk" (declarada) ou "sug" (inferida), com as
                  colunas do JOIN e a regra que gerou a relação
  relacao_status  decisão da equipe sobre cada relação: documentada ou
                  descartada
  importacoes     data e resumo de cada coleta do catálogo
  menus           árvore de menus e telas (id estável, ex.:
                  pdv.caixa.fechamento-de-caixa)
  menu_tabelas    vínculo tela ↔ tabela, com origem "sugerido" ou "equipe"
  manuais         manuais (conteúdo em JSON), tela vinculada, tabelas citadas
                  e documentos de origem

Os ids de menu são gerados a partir do título (slug). Por isso são estáveis
entre execuções do seed e os vínculos não se perdem.


-------------------------------------------------------------------------------
 7. FLUXOS PRINCIPAIS
-------------------------------------------------------------------------------

7.1 Coleta da estrutura do banco
  coletar.py lê, só do information_schema: TABLES, COLUMNS, KEY_COLUMN_USAGE
  e STATISTICS. Gera CSVs em coletor/saida/<schema>/.
  Sem banco real, exemplo/gerar_exemplo.py gera os mesmos CSVs para o banco
  fictício demo_pdv.

7.2 Inferência de relações (inferir.py)
  Muitos bancos de ERP legados quase não declaram chaves estrangeiras (tabelas
  MyISAM nem suportam). Por isso as relações são inferidas por regras, em
  ordem de prioridade:
    1. fk           chave estrangeira declarada              → confirmada
    2. dicionario   sinônimos de colunas                     → sugerida
                    (ex.: loja_origem → lojas)
    3. nome_tabela  coluna com o nome da tabela              → sugerida
                    (cidade → cidades)
    4. pk_igual     coluna com o mesmo nome de uma PK        → sugerida
                    não genérica (id_cliente → clientes)
    5. composta     item que repete a chave composta do      → sugerida
                    cabeçalho (nfce_itens → nfce por
                    id_loja+numero+serie)
  No banco de exemplo: 5 FKs declaradas e 43 relações inferidas, cobrindo 29
  das 30 tabelas.

7.3 Carga (app/seed.py)
  Cria o schema e importa catálogo, menus e manuais. Pode ser executado
  quantas vezes for preciso: ele preserva relacao_status e os vínculos
  menu_tabelas com origem "equipe".

7.4 Importação de manuais (ferramentas/importar_processos.py)
  Para cada manual definido em curadoria.json:
  - Lê as fontes. Nos PDFs, só entram as imagens que cada página realmente
    desenha; nos documentos Word, texto e imagens seguem a ordem do documento.
  - Remove ruído: cabeçalhos repetidos, sumário antigo, "Elaborado por" e
    autores (autores.json).
  - Classifica cada parágrafo em seção, passo (mantém a numeração original),
    OBS, nota, SQL, subtítulo ou texto.
  - Salva os prints, ignorando logos repetidos e imagens muito pequenas.
  - Detecta as tabelas citadas (nomes técnicos e blocos SQL).
  Manuais com "editado": true no JSON não são sobrescritos.

7.5 Exportação de PDF
  O botão chama GET /api/manuais/{código}/pdf. O backend abre a rota
  /manuais/{código}/imprimir no Edge headless e gera um A4 com cabeçalho,
  marca e rodapé com número de página.


-------------------------------------------------------------------------------
 8. VALIDAÇÕES E REGRAS DE NEGÓCIO
-------------------------------------------------------------------------------

Relações
  - Três estados visíveis, para nunca apresentar uma hipótese como fato:
      Confirmada   existe FK no banco. Não pode ser alterada pela equipe.
      Documentada  a equipe validou pela lógica do sistema.
      Sugerida     inferida por nome. Ainda não foi validada.
    Descartadas somem da interface, mas continuam registradas.
  - Uma relação sugerida só é criada se os tipos das colunas forem compatíveis
    (número com número, texto com texto). A exceção são as regras do
    dicionário, que registram o aviso "tipos diferentes".
  - Colunas decimal com casas decimais (valores, quantidades) não viram chave
    por inferência de nome.
  - PKs genéricas (id, codigo, num_seq, numero…) e colunas de data não geram
    relação pela regra pk_igual.
  - Cada coluna recebe no máximo uma relação inferida simples: vale a regra de
    maior prioridade. A regra de chave composta é avaliada à parte.
  - Tabelas com 40 ou mais referências são marcadas como "de apoio". O
    diagrama não se expande a partir delas, porque isso traria dezenas de
    tabelas.
  - O diagrama mostra no máximo 40 tabelas. Ficam as mais conectadas às
    tabelas da tela.

Vínculos tela ↔ tabela
  - O vínculo só é aceito se a tabela existir no catálogo (o frontend valida
    antes de enviar).
  - Sugestões vindas do seed ficam como "sugerido". Ao salvar pela interface,
    o vínculo passa a ser da "equipe".

API
  - Pydantic valida o corpo das requisições. O status de relação é limitado a
    documentada | descartada | sugerida.
  - Módulo, menu, tabela, relação ou manual inexistente → HTTP 404 com
    mensagem.
  - Falha na geração do PDF → HTTP 503 com o motivo. O frontend então recorre
    à impressão do navegador.

Seed
  - Avisa quando um manual aponta para um menu inexistente e grava o manual
    sem vínculo.
  - Vínculos sugeridos para tabelas que não existem no catálogo são ignorados.

Importação de documentos
  - Senhas são mascaradas (--password=…, password=… e a lista do arquivo
    segredos.txt, que não vai para o git).
  - Nomes de autores e linhas "Elaborado/Revisado/Aprovado por" são removidos.
  - Arquivo de origem inexistente ou menu inexistente aparecem no relatório
    final da importação.


-------------------------------------------------------------------------------
 9. API (prefixo /api — documentação interativa em http://localhost:8010/docs)
-------------------------------------------------------------------------------

  GET  /modulos                               módulos e data da última coleta
  GET  /modulos/{m}/menus                     árvore de menus com contagens
  GET  /menus/{id}                            ficha da tela: caminho, tabelas,
                                              relações, manuais e opções
                                              internas
  PUT  /menus/{id}/tabelas                    salva os vínculos tela ↔ tabela
  GET  /modulos/{m}/catalogo                  tabelas e relações (sem colunas)
  GET  /modulos/{m}/tabelas/{nome}            ficha da tabela
  GET  /modulos/{m}/diagrama?tabelas=a,b&nivel=1&apoio=false
                                              diagrama ER em volta das tabelas
  PUT  /modulos/{m}/relacoes/status           valida, descarta ou desfaz uma
                                              relação
  GET  /manuais?modulo=pdv                    lista de manuais
  GET  /manuais/{código}                      manual completo
  GET  /manuais/{código}/pdf                  download do PDF
  GET  /imagens/{código}/{arquivo}            prints dos manuais


-------------------------------------------------------------------------------
 10. COMO INSTALAR E RODAR
-------------------------------------------------------------------------------

Requisitos: Windows com Microsoft Edge, Python 3.12 ou superior e Node.js 20
ou superior.

  Backend
    cd backend
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m app.seed       (carrega o sistema de exemplo)

  Frontend
    cd frontend
    npm install

  Subir tudo
    .\iniciar.ps1      (API em http://localhost:8010, interface em
                        http://localhost:5173)

  Usar com um banco real
    cd coletor
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    copie .env.example para .env e preencha (de preferência um usuário só com
    SELECT)
    .venv\Scripts\python.exe coletar.py meu_banco
    .venv\Scripts\python.exe inferir.py meu_banco
    Aponte o módulo para "meu_banco" em backend/app/seed.py, escreva os menus
    do sistema em backend/seed/menus_pdv.json e rode o seed de novo.


-------------------------------------------------------------------------------
 11. SEGURANÇA E DADOS SENSÍVEIS
-------------------------------------------------------------------------------

  - O coletor lê somente o information_schema: estrutura, nunca dados de
    clientes, vendas ou produtos.
  - Ficam fora do git (.gitignore):
      coletor/.env                        credenciais do banco
      backend/ferramentas/segredos.txt
      backend/ferramentas/curadoria.json  e autores.json (dados reais)
      coletor/saida/                      estrutura de um banco real
      backend/dados/                      SQLite gerado
  - Os manuais importados passam por mascaramento de senhas e remoção de
    autores antes de serem gravados.
  - A interface não executa SQL no banco do ERP. Os blocos SQL dos manuais são
    só texto para o analista copiar.


-------------------------------------------------------------------------------
 12. LIMITAÇÕES CONHECIDAS E PRÓXIMOS PASSOS
-------------------------------------------------------------------------------

  - Sem autenticação: antes de abrir para uma equipe grande, incluir login e
    registrar quem validou cada relação.
  - Os manuais não têm editor na interface. A edição é feita nos arquivos JSON.
  - Módulos Retaguarda e Financeiro: a estrutura está pronta (tabela
    modulos), falta mapear menus e bancos.
  - Relações entre bancos de módulos diferentes (ex.: PDV ← Retaguarda) como
    um quarto tipo de ligação.
  - Integração com a ferramenta de chamados da equipe de suporte.
