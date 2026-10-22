"""Cobertura da wiki: quanto do sistema já está documentado e quem está contribuindo.

Definições (as mesmas do painel "Support Nexus · Cobertura da wiki"):
  tela                  item de menu sem subitens (os menus e submenus só agrupam telas)
  com manual            tela com pelo menos um manual vinculado
  com tabelas           tela com pelo menos uma tabela vinculada (sugerida ou da equipe)
  tabelas confirmadas   tela com tabelas, todas confirmadas pela equipe (nenhum vínculo só sugerido)
  a detalhar            tela marcada com submenu ainda não mapeado
  relação validada      confirmada (FK), documentada ou descartada: alguém já decidiu; "sugerida" ainda não
  contribuição          relação validada/descartada, vínculo confirmado ou manual salvo pela interface,
                        nos últimos 7 dias, por autor (o nome informado no topo; vazio = "(sem nome)")
Agrupado por módulo e menu principal (Cadastros, Vendas, Caixa…): poucos valores fixos, sem explosão de séries.
"""
import sqlite3
from dataclasses import dataclass, field

SEM_NOME = "(sem nome)"

# telas (folhas da árvore) com o menu principal de cada uma
_SQL_TELAS = """
WITH RECURSIVE arvore(id, modulo, raiz) AS (
    SELECT id, modulo, titulo FROM menus WHERE pai IS NULL
    UNION ALL
    SELECT m.id, m.modulo, a.raiz FROM menus m JOIN arvore a ON m.pai = a.id
)
SELECT a.modulo, a.raiz AS menu,
       COUNT(*) AS telas,
       SUM(EXISTS (SELECT 1 FROM manuais d WHERE d.menu = a.id)) AS com_manual,
       SUM(EXISTS (SELECT 1 FROM menu_tabelas t WHERE t.menu = a.id)) AS com_tabelas,
       SUM(EXISTS (SELECT 1 FROM menu_tabelas t WHERE t.menu = a.id)
           AND NOT EXISTS (SELECT 1 FROM menu_tabelas t WHERE t.menu = a.id AND t.origem = 'sugerido')) AS tabelas_confirmadas,
       SUM(m.submenu) AS a_detalhar
FROM arvore a JOIN menus m ON m.id = a.id
WHERE NOT EXISTS (SELECT 1 FROM menus f WHERE f.pai = a.id)
GROUP BY a.modulo, a.raiz
"""

_SQL_RELACOES = """
SELECT mo.id AS modulo,
       CASE WHEN r.tipo = 'fk' THEN 'confirmada' ELSE COALESCE(s.status, 'sugerida') END AS estado,
       COUNT(*) AS n
FROM relacoes r JOIN modulos mo ON mo.banco = r.banco
LEFT JOIN relacao_status s ON s.banco = r.banco AND s.id = r.id
GROUP BY 1, 2
"""

# datas gravadas em horário local ('localtime'), então a janela também é local
_SQL_CONTRIBUICOES = """
SELECT autor, tipo, COUNT(*) AS n FROM (
    SELECT por AS autor, 'relacao' AS tipo FROM relacao_status WHERE em >= datetime('now', 'localtime', '-7 days')
    UNION ALL
    SELECT por, 'vinculo' FROM menu_tabelas WHERE origem = 'equipe' AND em >= datetime('now', 'localtime', '-7 days')
    UNION ALL
    SELECT por, 'manual' FROM manuais WHERE por <> '' AND atualizado_em >= datetime('now', 'localtime', '-7 days')
) GROUP BY autor, tipo
"""


@dataclass
class Cobertura:
    telas: list[dict] = field(default_factory=list)          # [{modulo, menu, telas, com_manual, ...}]
    relacoes: list[dict] = field(default_factory=list)       # [{modulo, estado, n}]
    manuais: dict[str, int] = field(default_factory=dict)    # {modulo: n}
    contribuicoes: list[dict] = field(default_factory=list)  # [{autor, tipo, n}] últimos 7 dias


def calcular(con: sqlite3.Connection) -> Cobertura:
    return Cobertura(
        telas=[dict(r) for r in con.execute(_SQL_TELAS)],
        relacoes=[dict(r) for r in con.execute(_SQL_RELACOES)],
        manuais={r["modulo"]: r["n"] for r in con.execute("SELECT modulo, COUNT(*) AS n FROM manuais GROUP BY modulo")},
        contribuicoes=[{**dict(r), "autor": r["autor"] or SEM_NOME} for r in con.execute(_SQL_CONTRIBUICOES)],
    )
