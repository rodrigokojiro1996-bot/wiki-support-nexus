-- quem validou/descartou cada relação e quem vinculou cada tabela a uma tela (até ter login: o nome informado na interface)
ALTER TABLE relacao_status ADD COLUMN por TEXT NOT NULL DEFAULT '';
ALTER TABLE menu_tabelas ADD COLUMN por TEXT NOT NULL DEFAULT '';
ALTER TABLE menu_tabelas ADD COLUMN em TEXT;  -- NULL nos vínculos sugeridos pelo seed
