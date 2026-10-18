-- Support Nexus · coletor de metadados (MySQL / MariaDB)
-- Lê somente information_schema: estrutura do banco, nenhum dado de cliente.
-- Uso no DBeaver: troque 'meu_banco' pelo nome do schema, rode cada bloco e exporte o resultado (CSV ou JSON).

SET @schema = 'meu_banco';

-- 0. Diagnóstico rápido: motor das tabelas e quantidade de FKs declaradas.
--    Tabelas MyISAM não suportam FK, então nesse caso quase tudo vai ser relação sugerida.
SELECT ENGINE, COUNT(*) AS tabelas
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = @schema AND TABLE_TYPE = 'BASE TABLE'
GROUP BY ENGINE;

SELECT COUNT(*) AS fks_declaradas
FROM information_schema.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = @schema;

-- 1. Tabelas  -> exportar como tabelas.csv
SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS AS linhas_estimadas, TABLE_COMMENT
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = @schema
ORDER BY TABLE_NAME;

-- 2. Colunas  -> exportar como colunas.csv
SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = @schema
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 3. Chaves estrangeiras declaradas (relações confirmadas)  -> exportar como fks.csv
SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = @schema AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 4. Índices (ajudam a inferir relações quando não há FK)  -> exportar como indices.csv
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = @schema
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
