"""Regras de limpeza comuns ao importador de documentos e ao editor de manuais.

Só biblioteca padrão: a API usa sem precisar das dependências do importador (pypdf, python-docx, pillow).
"""
import re
from pathlib import Path

from ..config import RAIZ

SEGREDOS = [
    (re.compile(r"(--password=)\S+", re.I), r"\1******"),
    (re.compile(r"(\bpassword\s*=\s*)\S+", re.I), r"\1******"),
]


def carregar_segredos(arq: Path) -> list:
    """Senhas conhecidas que aparecem soltas nas anotações: uma por linha (linhas com # são comentário)."""
    if not arq.exists():
        return []
    return [(re.compile(re.escape(s.strip())), "******")
            for s in arq.read_text(encoding="utf-8").splitlines() if s.strip() and not s.startswith("#")]


SEGREDOS += carregar_segredos(RAIZ / "ferramentas" / "segredos.txt")  # fora do git


def mascarar(t: str) -> str:
    for rx, sub in SEGREDOS:
        t = rx.sub(sub, t)
    return t


def contar_segredos(t: str) -> int:
    """Quantas senhas mascarar() troca no texto (o aviso da importação mostra o número)."""
    n = 0

    def trocar(m: re.Match, sub: str) -> str:
        nonlocal n
        novo = m.expand(sub)
        n += novo != m.group(0)  # "--password=******" casa de novo na regra seguinte: não conta duas vezes
        return novo

    for rx, sub in SEGREDOS:
        t = rx.sub(lambda m: trocar(m, sub), t)
    return n


# nomes de tabela sem "_" que também valem como citação técnica no texto (ajuste para o seu banco)
TECNICAS = {"vendas", "produtos", "clientes", "caixas", "estoque"}


def tabelas_citadas(texto: str, sqls: str, nomes: set[str]) -> list[str]:
    achadas = set()
    baixo, sql_baixo = texto.lower(), sqls.lower()
    for n in nomes:
        rx = re.compile(rf"\b{re.escape(n)}\b")
        if rx.search(sql_baixo):
            achadas.add(n)
        elif ("_" in n or n in TECNICAS) and rx.search(baixo) and (n not in TECNICAS or re.search(rf"tabela\s+[\"'“]?{re.escape(n)}\b", baixo) or "_" in n):
            achadas.add(n)
    for cand in re.findall(r"tabela\s+[\"'“]?([a-z0-9_]+)", baixo):
        if cand in nomes:
            achadas.add(cand)
    return sorted(achadas)
