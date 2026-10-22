"""Importa em lote documentos de suporte (PDF, Word e .txt) como manuais da Wiki.

Lê ferramentas/curadoria.json (modelo em curadoria.exemplo.json), grava um JSON por manual em dados/manuais/ e os prints em
dados/imagens/<código>/ (fora do git: manuais reais nunca vão para o repositório). Depois rode `python -m app.seed` para carregar no banco.
A conversão de cada documento é a mesma da importação pela interface (app/servicos/importacao.py).

Uso (dentro de backend/):
    .venv\Scripts\python.exe -m ferramentas.importar_processos

Manuais com "editado": true no JSON não são sobrescritos (proteção para ajustes feitos à mão).
"""
import json
import shutil
from pathlib import Path

from app import config, db
from app.servicos.importacao import Imagens, Montador, converter, norm
from app.servicos.manuais import extensao_imagem

# conteúdo real fica em backend/dados/ (no .gitignore); backend/seed/ guarda só o exemplo DEMO.*
CURADORIA = Path(__file__).with_name("curadoria.json")
AUTORES = Path(__file__).with_name("autores.json")


def pasta_manuais() -> Path:
    return config.DADOS / "manuais"


def pasta_imagens() -> Path:
    return config.DADOS / "imagens"


def modulo_do_item(spec: dict) -> str:
    """O módulo vem do item da curadoria; sem ele, é o prefixo do id do menu ("fin.contas..." -> "fin")."""
    return spec.get("modulo") or spec["menu"].split(".", 1)[0]


def prints_do_manual(codigo: str):
    """Prints do lote vão direto para dados/imagens/<código>/01.png, 02.jpg... (sem passar pelo rascunho do editor)."""
    pasta, n = pasta_imagens() / codigo, 0

    def guardar(dados: bytes) -> str:
        nonlocal n
        n += 1
        pasta.mkdir(parents=True, exist_ok=True)
        nome = f"{n:02d}.{extensao_imagem(dados)}"
        (pasta / nome).write_bytes(dados)
        return f"{codigo}/{nome}"
    return guardar


def main(curadoria: Path = CURADORIA) -> list[str]:
    """Importa os manuais da curadoria; devolve a lista de problemas encontrados (também impressa)."""
    cur = json.loads(curadoria.read_text(encoding="utf-8"))
    origem = Path(cur["origem"])
    con = db.conectar()
    # o banco de cada módulo (tabela modulos) diz em quais tabelas procurar as citações do manual
    bancos = {r["id"]: r["banco"] for r in con.execute("SELECT id, banco FROM modulos")}
    nomes_por_banco = {b: {r[0].lower() for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (b,))}
                       for b in set(bancos.values()) if b}
    menus = {r[0] for r in con.execute("SELECT id FROM menus")}
    con.close()
    pasta_manuais().mkdir(parents=True, exist_ok=True)
    pasta_imagens().mkdir(parents=True, exist_ok=True)
    problemas = []
    # autores citados nos documentos ("Elaborado por: …"): removidos de qualquer linha solta
    Montador.autores = {norm(n) for n in json.loads(AUTORES.read_text(encoding="utf-8"))} if AUTORES.exists() else set()
    for spec in cur["manuais"]:
        modulo = modulo_do_item(spec)
        if modulo not in bancos:
            problemas.append(f"{spec['codigo']}: módulo {modulo} não existe; manual não importado")
            continue
        destino = pasta_manuais() / f"{spec['codigo']}.json"
        try:
            editado = destino.exists() and json.loads(destino.read_text(encoding="utf-8")).get("editado")
        except ValueError:
            editado = False
        if editado:
            print(f"= {spec['codigo']} editado à mão, mantido")
            continue
        if spec["menu"] not in menus:
            problemas.append(f"{spec['codigo']}: menu {spec['menu']} não existe")
        shutil.rmtree(pasta_imagens() / spec["codigo"], ignore_errors=True)
        # um Imagens por manual: numeração contínua e prints repetidos descartados entre os documentos
        imgs = Imagens(prints_do_manual(spec["codigo"]))
        secoes, tabelas, versao = [], set(), "1.0"
        for f in spec["fontes"]:
            arq = origem / f["arquivo"]
            if not arq.exists():
                problemas.append(f"{spec['codigo']}: arquivo não encontrado: {f['arquivo']}")
                continue
            r = converter(arq.read_bytes(), arq.name, nomes_por_banco.get(bancos[modulo], set()), f.get("secao"), imagens=imgs)
            versao = r["versao"] or versao
            secoes += r["secoes"]
            tabelas.update(r["tabelas"])
        manual = {
            "codigo": spec["codigo"], "titulo": spec["titulo"], "subtitulo": spec.get("subtitulo", ""), "versao": versao,
            "modulo": modulo, "menu": spec["menu"], "fontes": [f["arquivo"] for f in spec["fontes"]],
            "tabelas": sorted(tabelas), "secoes": secoes,
        }
        destino.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
        nb = sum(len(s["blocos"]) for s in secoes)
        print(f"+ {spec['codigo']:12} {len(secoes):2} seções {nb:3} blocos {imgs.n:3} prints  tabelas={','.join(manual['tabelas'][:6])}")
    if problemas:
        print("\nATENÇÃO:\n  " + "\n  ".join(problemas))
    return problemas


if __name__ == "__main__":
    main()
