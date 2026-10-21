-- quem criou ou editou o manual por último pela interface (até ter login: o nome informado no topo)
ALTER TABLE manuais ADD COLUMN por TEXT NOT NULL DEFAULT '';
