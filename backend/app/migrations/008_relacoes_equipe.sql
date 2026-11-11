-- relações ligadas pela equipe no diagrama (clicar numa coluna e na coluna de outra tabela, depois Validar).
-- Ficam fora de "relacoes", que é regravada a cada importação do catálogo; a decisão "documentada" de quem
-- ligou fica em relacao_status, como a das relações sugeridas.
CREATE TABLE relacoes_equipe (
  banco      TEXT NOT NULL,
  id         TEXT NOT NULL,           -- origem.coluna>destino, mesmo formato do coletor
  origem     TEXT NOT NULL,           -- tabela com a chave estrangeira (lado N)
  destino    TEXT NOT NULL,           -- tabela referenciada (lado 1)
  colunas    TEXT NOT NULL,           -- JSON [[col_origem, col_destino]]
  observacao TEXT NOT NULL DEFAULT '',
  por        TEXT NOT NULL DEFAULT '',
  em         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (banco, id)
);
