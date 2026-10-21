-- documentos de origem de cada manual (PDF/Word/.txt que o importador usou)
ALTER TABLE manuais ADD COLUMN fontes TEXT NOT NULL DEFAULT '[]';
