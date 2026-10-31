-- tipo do manual: 'processo' = o manual da tela (passo a passo e funcionalidades; um por tela) ou
-- 'chamado' = chamado frequente (problema recorrente que aparece na tela e como resolver; vários por tela).
-- Os manuais que já existiam são manuais da tela.
ALTER TABLE manuais ADD COLUMN tipo TEXT NOT NULL DEFAULT 'processo';
