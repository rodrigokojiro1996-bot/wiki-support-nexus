-- trechos do manual da tela que a equipe ligou a uma tabela: no diagrama, a pessoa seleciona o texto do manual em
-- que a tabela age e valida. O trecho fica em destaque quando alguém olha essa tabela.
--   secao (1, 2...) e bloco (0, 1... dentro da seção) dizem onde o texto estava; texto é o que foi selecionado.
--   Se o manual for editado e o texto mudar, o trecho continua guardado e aparece como "não encontrado".
CREATE TABLE manual_trechos (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  manual  TEXT NOT NULL,
  tabela  TEXT NOT NULL,
  secao   INTEGER NOT NULL,
  bloco   INTEGER NOT NULL,
  texto   TEXT NOT NULL,
  versao  TEXT NOT NULL DEFAULT '',   -- versão do manual quando o trecho foi ligado
  por     TEXT NOT NULL DEFAULT '',
  em      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX manual_trechos_tabela ON manual_trechos (manual, tabela);
