"""Support Nexus · monta o catálogo técnico a partir dos CSVs do coletor.

Lê os CSVs de coletor/saida/<schema>/ (coleta real) ou coletor/exemplo/<schema>/ (banco de exemplo),
mais coletor/dicionario.json, e grava catalogo.json na mesma pasta (o backend importa no seed).

Regras, em ordem de prioridade (a primeira que achar uma coluna vence):
  fk          chave estrangeira declarada no MySQL          -> confirmada
  dicionario  sinônimo cadastrado em dicionario.json         -> sugerida
  nome_tabela coluna com o nome da tabela (cidade -> cidades) -> sugerida
  pk_igual    coluna com o mesmo nome da PK de outra tabela  -> sugerida
  composta    item que repete a chave composta do cabeçalho  -> sugerida

Uso:
    python inferir.py demo_pdv
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

# Nomes de PK que se repetem no banco inteiro e não identificam uma tabela.
PK_GENERICA = {"id", "codigo", "cod", "num_seq", "numseq", "numero", "chave", "seq", "sequencia", "item", "nro_doc", "docto", "linha"}
HUB_MINIMO = 40  # tabelas com tantas referências ou mais são "de apoio" (empresas, usuarios…)


def ler(pasta, nome):
    arq = pasta / f"{nome}.csv"
    return list(csv.DictReader(open(arq, encoding="utf-8"))) if arq.exists() else []


def familia(tipo):
    t = tipo.lower()
    if any(x in t for x in ("int", "decimal", "numeric", "float", "double", "bit")):
        return "num"
    if any(x in t for x in ("char", "text", "enum")):
        return "str"
    return "outro"


def main():
    if len(sys.argv) < 2:
        sys.exit("Informe o schema: python inferir.py demo_pdv")
    schema = sys.argv[1]
    pasta = AQUI / "saida" / schema
    if not pasta.exists():
        pasta = AQUI / "exemplo" / schema
    tab_rows, col_rows, fk_rows, idx_rows = (ler(pasta, n) for n in ("tabelas", "colunas", "fks", "indices"))
    if not col_rows:
        sys.exit(f"Não achei {pasta / 'colunas.csv'}. Rode antes: python coletar.py {schema}")
    dic = json.loads((AQUI / "dicionario.json").read_text(encoding="utf-8"))["regras"]

    # ---------- tabelas e colunas ----------
    tabelas = {}
    for r in tab_rows:
        tabelas[r["TABLE_NAME"]] = {"id": r["TABLE_NAME"], "desc": r.get("TABLE_COMMENT", ""), "engine": r.get("ENGINE", ""),
                                    "rows": r.get("linhas_estimadas", ""), "cols": []}
    for r in sorted(col_rows, key=lambda r: (r["TABLE_NAME"], int(r["ORDINAL_POSITION"] or 0))):
        t = tabelas.setdefault(r["TABLE_NAME"], {"id": r["TABLE_NAME"], "desc": "", "engine": "", "rows": "", "cols": []})
        t["cols"].append({"name": r["COLUMN_NAME"], "type": r["COLUMN_TYPE"], "pk": r["COLUMN_KEY"] == "PRI"})

    tipo = {(t, c["name"]): c["type"] for t, d in tabelas.items() for c in d["cols"]}
    colset = {t: {c["name"] for c in d["cols"]} for t, d in tabelas.items()}
    pk = {t: [c["name"] for c in d["cols"] if c["pk"]] for t, d in tabelas.items()}
    pk1 = {t: v[0] for t, v in pk.items() if len(v) == 1}

    indices = defaultdict(lambda: defaultdict(list))
    unicos = defaultdict(set)
    for r in sorted(idx_rows, key=lambda r: (r["TABLE_NAME"], r["INDEX_NAME"], int(r["SEQ_IN_INDEX"] or 0))):
        indices[r["TABLE_NAME"]][r["INDEX_NAME"]].append(r["COLUMN_NAME"])
        if r["NON_UNIQUE"] == "0":
            unicos[r["TABLE_NAME"]].add(r["INDEX_NAME"])

    # ---------- relações ----------
    rel, usadas = [], set()   # usadas: (tabela, coluna) que já ganharam uma relação

    def add(origem, destino, pares, regra, motivo):
        if origem == destino or destino not in tabelas:
            return False
        chave_cols = [a for a, _ in pares if a != "empresa"] or [pares[0][0]]
        # na chave composta cada coluna pode já ter a própria relação (id_loja → lojas); o que conta é o conjunto
        if regra != "composta" and any((origem, c) in usadas for c in chave_cols):
            return False
        avisos = [f"{a} ({tipo[(origem, a)]}) × {b} ({tipo[(destino, b)]})" for a, b in pares
                  if familia(tipo[(origem, a)]) != "outro" and familia(tipo[(destino, b)]) != "outro"
                  and familia(tipo[(origem, a)]) != familia(tipo[(destino, b)])]
        if avisos and regra not in ("fk", "dicionario"):
            return False
        # decimal com casas (valor em dinheiro, quantidade) não é chave
        if regra in ("nome_tabela", "pk_igual") and any(re.search(r"decimal\(\d+,[1-9]", tipo[(origem, a)]) for a, _ in pares):
            return False
        if regra != "composta":
            for c in chave_cols:
                usadas.add((origem, c))
        rel.append({
            "id": f"{origem}.{'+'.join(a for a, _ in pares)}>{destino}",
            "source": origem, "target": destino, "cols": [list(p) for p in pares],
            "kind": "fk" if regra == "fk" else "sug", "regra": regra,
            "reason": motivo + (f"; tipos diferentes: {', '.join(avisos)}" if avisos else ""),
        })
        return True

    # fk declaradas (agrupadas por constraint para suportar FK composta)
    por_fk = defaultdict(list)
    for r in fk_rows:
        por_fk[(r["TABLE_NAME"], r["CONSTRAINT_NAME"], r["REFERENCED_TABLE_NAME"])].append((r["COLUMN_NAME"], r["REFERENCED_COLUMN_NAME"]))
    for (o, _, d), pares in por_fk.items():
        add(o, d, pares, "fk", "chave estrangeira declarada no MySQL")

    # dicionário de sinônimos do sistema
    for regra in dic:
        d = regra["tabela"]
        if d not in tabelas:
            continue
        alvo = regra.get("alvo") or pk1.get(d)
        if not alvo or alvo not in colset[d]:
            continue
        for o in sorted(regra.get("origem") or tabelas):
            if o not in tabelas:
                continue
            for c in regra["colunas"]:
                if c in colset[o]:
                    pares = [(c, alvo)]
                    if regra.get("empresa") and "empresa" in colset[o] and "empresa" in colset[d]:
                        pares.append(("empresa", "empresa"))
                    add(o, d, pares, "dicionario", f"dicionário de sinônimos: {c} → {d}.{alvo}")

    # coluna com o nome da tabela (vem antes de pk_igual: "empresa" é empresas, não a tabela que usa empresa como PK)
    nomes = set(tabelas)
    com_nome_de_tabela = set()
    for o in sorted(tabelas):
        for c in sorted(colset[o]):
            if (o, c) in usadas or (c in pk[o] and len(pk[o]) == 1):
                continue
            for cand in (c, c + "s", c + "es"):
                if cand in nomes and cand != o and cand in pk1:
                    com_nome_de_tabela.add(c)
                    add(o, cand, [(c, pk1[cand])], "nome_tabela", f"a coluna tem o nome da tabela {cand}")
                    break

    # mesmo nome de uma PK não genérica (datas e nomes de outras tabelas não contam)
    por_pk = defaultdict(list)
    for t, c in pk1.items():
        if c.lower() not in PK_GENERICA and c not in com_nome_de_tabela and familia(tipo[(t, c)]) != "outro":
            por_pk[c].append(t)
    for o in sorted(tabelas):
        for c in sorted(colset[o]):
            alvos = [t for t in por_pk.get(c, []) if t != o]
            if len(alvos) == 1:
                add(o, alvos[0], [(c, c)], "pk_igual", f"mesmo nome da chave de {alvos[0]}")

    # chave composta de cabeçalho repetida no item
    def prefixo(n):
        return n.split("_")[0][:4]
    for d in sorted(tabelas):
        chaves = []
        if len(pk[d]) >= 2:
            chaves.append(pk[d])
        chaves += [v for k, v in indices[d].items() if k in unicos[d] and k != "PRIMARY" and len(v) >= 2]
        for chave in chaves:
            if all(c.lower() in PK_GENERICA or c == "empresa" for c in chave):
                continue
            for o in sorted(tabelas):
                if o == d or prefixo(o) != prefixo(d) or not set(chave) <= colset[o]:
                    continue
                maiores = [v for v in indices[o].values() if len(v) > len(chave) and set(v[:len(chave)]) == set(chave)]
                if maiores:
                    add(o, d, [(c, c) for c in chave], "composta", f"repete a chave ({', '.join(chave)}) de {d}")

    # ---------- tabelas de apoio (muito referenciadas) ----------
    entrada = Counter(r["target"] for r in rel)
    hubs = sorted(t for t, n in entrada.items() if n >= HUB_MINIMO)

    cat = {"banco": schema, "origem": "importado", "importadoEm": datetime.now().strftime("%d/%m/%Y %H:%M"),
           "tables": tabelas, "edges": rel, "hubs": hubs}
    (pasta / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- relatório ----------
    ligadas = {r["source"] for r in rel} | {r["target"] for r in rel}
    print(f"Tabelas: {len(tabelas)} · com alguma relação: {len(ligadas)} · isoladas: {len(tabelas) - len(ligadas)}")
    print("Relações por regra:", dict(Counter(r["regra"] for r in rel)))
    print("Tabelas de apoio (>= %d referências):" % HUB_MINIMO, ", ".join(f"{h} ({entrada[h]})" for h in hubs))
    print("Mais referenciadas:", entrada.most_common(15))
    sem = Counter(c for t in tabelas for c in colset[t] if (t, c) not in usadas and c not in pk[t]
                  and familia(tipo[(t, c)]) == "num" and not c.startswith(("vlr", "qt", "valor", "saldo", "perc", "alq", "aliq")))
    print("Colunas numéricas frequentes ainda sem relação (candidatas ao dicionário):", sem.most_common(30))
    print("Catálogo:", pasta / "catalogo.json")


if __name__ == "__main__":
    main()
