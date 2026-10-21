"""Algoritmo do diagrama ER: quais tabelas entram em volta do foco. Sem SQL, para ser testável isolado."""
from dataclasses import dataclass

from ..config import APOIO_MINIMO, LIMITE_DIAGRAMA, NIVEL_MAXIMO


@dataclass
class Recorte:
    incluidas: set[str]
    arestas: list[dict]
    apoio: set[str]           # tabelas de apoio do banco inteiro (muito referenciadas)
    apoio_ocultas: list[str]  # tabelas de apoio vizinhas que ficaram de fora


def tabelas_de_apoio(rels: list[dict], minimo: int = APOIO_MINIMO) -> set[str]:
    grau: dict[str, int] = {}
    for r in rels:
        grau[r["destino"]] = grau.get(r["destino"], 0) + 1
    return {t for t, n in grau.items() if n >= minimo}


def recortar(foco: list[str], rels: list[dict], nivel: int = 1, apoio: bool = False,
             limite: int = LIMITE_DIAGRAMA, apoio_minimo: int = APOIO_MINIMO) -> Recorte:
    """As tabelas do foco, as vizinhas até `nivel` e as ligações entre todas.

    `rels` são as relações já sem as descartadas ({origem, destino, ...}).
    """
    apoio_tab = tabelas_de_apoio(rels, apoio_minimo)
    incluidas, fronteira, apoio_ocultas = set(foco), set(foco), set()
    for _ in range(max(0, min(nivel, NIVEL_MAXIMO))):
        nova = set()
        for r in rels:
            for a, b in ((r["origem"], r["destino"]), (r["destino"], r["origem"])):
                # a expansão não passa por tabelas de apoio (clientes, usuarios…): elas trariam dezenas de vizinhas
                if a in fronteira and b not in incluidas and (apoio or a not in apoio_tab):
                    if b in apoio_tab and not apoio:
                        apoio_ocultas.add(b)
                    else:
                        nova.add(b)
        incluidas |= nova
        fronteira = nova
    # limite para o diagrama continuar legível: mantém as mais conectadas ao foco
    if len(incluidas) > limite:
        conexoes = {t: sum(1 for r in rels if {r["origem"], r["destino"]} & set(foco) and t in (r["origem"], r["destino"])) for t in incluidas}
        incluidas = set(foco) | set(sorted(incluidas - set(foco), key=lambda t: -conexoes[t])[: max(0, limite - len(foco))])
    arestas = [r for r in rels if r["origem"] in incluidas and r["destino"] in incluidas]
    return Recorte(incluidas, arestas, apoio_tab, sorted(apoio_ocultas - incluidas))
