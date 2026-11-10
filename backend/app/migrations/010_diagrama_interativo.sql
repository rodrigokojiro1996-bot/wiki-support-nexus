-- diagrama interativo: a equipe organiza as tabelas e anota as ligações.
-- posicoes_diagrama: onde cada tabela foi arrastada, por tela (chave = tabelas da tela, como o /diagrama recebe).
--   Vale para todos; "Reorganizar" apaga e o diagrama volta ao layout automático.
CREATE TABLE posicoes_diagrama (
  modulo  TEXT NOT NULL,
  chave   TEXT NOT NULL,
  tabela  TEXT NOT NULL,
  x       REAL NOT NULL,
  y       REAL NOT NULL,
  por     TEXT NOT NULL DEFAULT '',
  em      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (modulo, chave, tabela)
);

-- relacao_notas: informativo de incidentes de uma ligação (o post-it em cima da linha).
--   posicao: onde o post-it fica ao longo da linha, de 0 (lado N) a 1 (lado 1).
CREATE TABLE relacao_notas (
  banco    TEXT NOT NULL,
  id       TEXT NOT NULL,           -- id da relação (catálogo ou equipe)
  texto    TEXT NOT NULL,
  posicao  REAL NOT NULL DEFAULT 0.5,
  por      TEXT NOT NULL DEFAULT '',
  em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (banco, id)
);
