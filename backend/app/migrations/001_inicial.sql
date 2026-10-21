-- Support Nexus · banco próprio da Wiki (SQLite) · migração 001: estrutura da versão 0.1.0
-- Guarda só metadados do sistema mapeado e o conhecimento da equipe; nenhum dado de cliente.

CREATE TABLE modulos (
  id     TEXT PRIMARY KEY,          -- pdv, adm, fin
  nome   TEXT NOT NULL,             -- PDV
  banco  TEXT                       -- schema MySQL de referência (ex.: demo_pdv)
);

-- ---------- catálogo técnico (vem do coletor) ----------
CREATE TABLE tabelas (
  banco      TEXT NOT NULL,
  nome       TEXT NOT NULL,
  engine     TEXT,
  linhas     INTEGER,
  descricao  TEXT DEFAULT '',       -- descrição funcional escrita pela equipe
  PRIMARY KEY (banco, nome)
);

CREATE TABLE colunas (
  banco   TEXT NOT NULL,
  tabela  TEXT NOT NULL,
  nome    TEXT NOT NULL,
  tipo    TEXT NOT NULL,
  pk      INTEGER NOT NULL DEFAULT 0,
  ordem   INTEGER NOT NULL,
  PRIMARY KEY (banco, tabela, nome)
);

CREATE TABLE relacoes (
  banco    TEXT NOT NULL,
  id       TEXT NOT NULL,           -- origem.colunas>destino
  origem   TEXT NOT NULL,
  destino  TEXT NOT NULL,
  colunas  TEXT NOT NULL,           -- JSON [[col_origem, col_destino], ...]
  tipo     TEXT NOT NULL,           -- fk | sug
  regra    TEXT,
  motivo   TEXT,
  PRIMARY KEY (banco, id)
);

-- decisões da equipe ficam separadas, para sobreviver a uma nova importação do catálogo
CREATE TABLE relacao_status (
  banco      TEXT NOT NULL,
  id         TEXT NOT NULL,
  status     TEXT NOT NULL CHECK (status IN ('documentada', 'descartada')),
  observacao TEXT DEFAULT '',
  em         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (banco, id)
);

CREATE TABLE importacoes (
  banco  TEXT PRIMARY KEY,
  em     TEXT NOT NULL,
  resumo TEXT
);

-- ---------- mapa do sistema (menus e telas do sistema) ----------
CREATE TABLE menus (
  id           TEXT PRIMARY KEY,    -- pdv.atendimento.caixa
  modulo       TEXT NOT NULL REFERENCES modulos(id),
  pai          TEXT REFERENCES menus(id),
  titulo       TEXT NOT NULL,
  atalho       TEXT,
  tela_codigo  TEXT,                -- código da janela no sistema (ex.: cx03)
  desabilitado INTEGER NOT NULL DEFAULT 0,
  submenu      INTEGER NOT NULL DEFAULT 0,  -- tem submenu no sistema que ainda não foi detalhado
  ordem        INTEGER NOT NULL
);

CREATE TABLE menu_tabelas (
  menu    TEXT NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
  tabela  TEXT NOT NULL,
  origem  TEXT NOT NULL DEFAULT 'equipe',  -- sugerido | equipe
  PRIMARY KEY (menu, tabela)
);

-- ---------- documentação ----------
CREATE TABLE manuais (
  codigo        TEXT PRIMARY KEY,   -- DEMO.001
  titulo        TEXT NOT NULL,
  subtitulo     TEXT DEFAULT '',
  versao        TEXT NOT NULL DEFAULT '1.0',
  modulo        TEXT NOT NULL REFERENCES modulos(id),
  menu          TEXT REFERENCES menus(id),
  conteudo      TEXT NOT NULL,      -- JSON: seções e blocos
  tabelas       TEXT NOT NULL DEFAULT '[]',
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
