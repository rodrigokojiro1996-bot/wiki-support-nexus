-- registro de alterações: tudo o que alguém criou, alterou, validou, descartou, moveu, importou ou excluiu no
-- Support Nexus, com quem fez e quando. Só recebe linhas novas (ninguém edita nem apaga o histórico pela API).
--   acao:    criou | alterou | excluiu | validou | descartou | importou | moveu
--   area:    manual | trecho | ligacao | informativo | diagrama | tela | dicionario
--   alvo:    o que foi mexido, para filtrar (código do manual, tabela, "origem.coluna → destino.coluna"...)
--   resumo:  a frase que a pessoa lê ("Alterou o informativo de incidentes da ligação vendas.id_cliente → ...")
--   detalhe: JSON com o antes e o depois (ou a lista de mudanças de um manual)
CREATE TABLE registro_alteracoes (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  em       TEXT NOT NULL,
  por      TEXT NOT NULL DEFAULT '',
  acao     TEXT NOT NULL,
  area     TEXT NOT NULL,
  modulo   TEXT NOT NULL DEFAULT '',
  alvo     TEXT NOT NULL DEFAULT '',
  resumo   TEXT NOT NULL,
  detalhe  TEXT
);
CREATE INDEX registro_alteracoes_em ON registro_alteracoes (id DESC);
CREATE INDEX registro_alteracoes_por ON registro_alteracoes (por, id DESC);
CREATE INDEX registro_alteracoes_area ON registro_alteracoes (area, id DESC);
