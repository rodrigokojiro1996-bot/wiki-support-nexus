-- dicionário de dados: o que cada tabela e cada coluna guarda, escrito pela equipe (balão no diagrama).
-- Fica fora de "tabelas"/"colunas", que são regravadas a cada importação do catálogo. A chave é o módulo (pdv, adm),
-- não o banco: a descrição de um módulo ainda sem banco ligado já fica guardada.
--   (modulo, tabela, '')     descrição da tabela
--   ('', '', coluna)         descrição do nome de coluna, vale para todas as tabelas em que ele aparece
--   (modulo, tabela, coluna) exceção: o nome quer dizer outra coisa nessa tabela
CREATE TABLE descricoes (
  modulo  TEXT NOT NULL DEFAULT '',
  tabela  TEXT NOT NULL DEFAULT '',
  coluna  TEXT NOT NULL DEFAULT '',
  texto   TEXT NOT NULL,
  por     TEXT NOT NULL DEFAULT '',
  em      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (modulo, tabela, coluna)
);
