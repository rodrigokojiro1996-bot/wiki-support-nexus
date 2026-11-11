-- diagrama: tabelas que a equipe adicionou à mão numa tela (botão direito no fundo › Adicionar tabela), para ligar
-- colunas com uma tabela que o recorte automático não trazia. Por tela (chave = tabelas da tela, como o /diagrama
-- recebe) e para todos; a posição onde foi colocada fica em posicoes_diagrama.
CREATE TABLE diagrama_tabelas (
  modulo  TEXT NOT NULL,
  chave   TEXT NOT NULL,
  tabela  TEXT NOT NULL,
  por     TEXT NOT NULL DEFAULT '',
  em      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (modulo, chave, tabela)
);
