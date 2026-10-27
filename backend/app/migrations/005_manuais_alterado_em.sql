-- quando alguém salvou o manual pelo editor, na hora de Brasília ("AAAA-MM-DD HH:MM:SS"); vai no rodapé do manual
-- como "Manual alterado em ...". Fica vazio nos manuais que ninguém alterou pela interface (exemplos e importados).
ALTER TABLE manuais ADD COLUMN alterado_em TEXT;
