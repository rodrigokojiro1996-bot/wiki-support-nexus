-- trecho do manual que pega vários blocos (passos, parágrafos, observações, até de seções diferentes): cada bloco
-- vira uma linha (o destaque acha o texto bloco a bloco), e todas as linhas da mesma seleção têm o mesmo grupo,
-- que é o id da primeira. Na tela, o grupo é um trecho só: um item na lista, desliga de uma vez.
ALTER TABLE manual_trechos ADD COLUMN grupo INTEGER;
UPDATE manual_trechos SET grupo = id WHERE grupo IS NULL;
CREATE INDEX manual_trechos_grupo ON manual_trechos (grupo);
