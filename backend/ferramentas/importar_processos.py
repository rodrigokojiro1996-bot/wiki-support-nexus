"""Converte documentos de suporte (PDF, Word e .txt) em manuais da Wiki.

Lê ferramentas/curadoria.json (modelo em curadoria.exemplo.json), grava um JSON por manual em dados/manuais/ e os prints em
dados/imagens/<código>/ (fora do git: manuais reais nunca vão para o repositório). Depois rode `python -m app.seed` para carregar no banco.

Uso (dentro de backend/):
    .venv\\Scripts\\python.exe -m ferramentas.importar_processos

Manuais com "editado": true no JSON não são sobrescritos (proteção para ajustes feitos à mão).
"""
import hashlib
import io
import json
import re
import shutil
import sqlite3
import unicodedata
from collections import Counter
from math import ceil
from pathlib import Path

import docx
import pypdf
from PIL import Image

from app.servicos.limpeza import mascarar, tabelas_citadas

RAIZ = Path(__file__).resolve().parent.parent
# conteúdo real fica em backend/dados/ (no .gitignore); backend/seed/ guarda só o exemplo DEMO.*
MANUAIS = RAIZ / "dados" / "manuais"
IMAGENS = RAIZ / "dados" / "imagens"
CURADORIA = Path(__file__).with_name("curadoria.json")

# ---------------- limpeza ----------------
# senhas mascaradas e tabelas citadas: as mesmas regras do editor de manuais (app/servicos/limpeza.py)
RUIDO = re.compile(r"(elaborado por|revisado por|aprovado por|^cria[cç][aã]o:|^revis[aã]o:|n[ºo°]\.?\s*revis|vers[aã]o do documento|"
                   r"^sum[aá]rio$|\.{6,}|erro! indicador|^vers[aã]o \d{4} de)", re.I)
SQL = re.compile(r"^(-|//)?\s*(select|update|delete|insert|repair|cd\\|mysql\b|mysqlcheck|mysqladmin)", re.I)
PASSO = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\.?\s*[-–]?\s*(.+)$")
TOPO = re.compile(r"^(\d+)\s*[\.\)]\s*[-–]?\s*(.+)$")
BULLET = re.compile(r"^[•\uf0b7\uf0a7\uf0d8▪●◦\-–*]\s*(.+)$")
OBS = re.compile(r"^OBS\S*\s*[:.]?\s*(.+)$", re.I)
NOTA = re.compile(r"^(importante|aten[cç][aã]o|nota)\s*[:!]\s*(.+)$", re.I)
FIM_FRASE = (".", ":", ";", "!", "?")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def limpar_emoji(t: str) -> str:
    # ícones das fontes de símbolo e emojis decorativos não aparecem nos manuais
    t = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u20E3\uE000-\uF8FF\uAC00-\uD7AF\u8100-\u8FFF\ud800-\udfff]", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


# ---------------- classificação de linhas em blocos ----------------
class Montador:
    """Recebe parágrafos e imagens na ordem do documento e monta seções/blocos."""

    autores: set[str] = set()  # nomes de quem elaborou/revisou: nunca entram no manual

    def __init__(self, titulo_padrao: str, secao_unica: str | None):
        self.secoes: list[dict] = []
        self.unica = secao_unica
        self.em_codigo = False
        if secao_unica:
            self.secoes.append({"titulo": secao_unica, "blocos": []})
        self.titulo_padrao = titulo_padrao

    def _atual(self) -> list:
        if not self.secoes:
            self.secoes.append({"titulo": self.titulo_padrao, "blocos": []})
        return self.secoes[-1]["blocos"]

    def titulo(self, texto: str):
        texto = texto.rstrip(" .:")
        if self.unica:
            self._atual().append({"tipo": "subtitulo", "texto": texto})
        else:
            self.secoes.append({"titulo": texto, "blocos": []})

    def paragrafo(self, p: str):
        p = limpar_emoji(mascarar(p.strip()))
        if not p or RUIDO.search(p) or norm(p) in Montador.autores:
            return
        blocos = self._atual()
        # bloco de código Markdown (```sql ... ```)
        if p.startswith("```"):
            self.em_codigo = not self.em_codigo
            if self.em_codigo:
                blocos.append({"tipo": "sql", "texto": ""})
            return
        if self.em_codigo:
            blocos[-1]["texto"] = (blocos[-1]["texto"] + "\n" + p).strip("\n")
            return
        if p.count("*") % 2 == 1:
            p = p.replace("*", "") if "**" not in p else re.sub(r"(?<!\*)\*(?!\*)", "", p)
        if SQL.match(p):
            linha = re.sub(r"^(-|//)\s*", "", p)
            if blocos and blocos[-1]["tipo"] == "sql":
                blocos[-1]["texto"] += "\n" + linha
            else:
                blocos.append({"tipo": "sql", "texto": linha})
            return
        if m := PASSO.match(p):
            blocos.append({"tipo": "passo", "rotulo": m.group(1), "texto": m.group(2)})
            return
        if (m := TOPO.match(p)) and not p.endswith((";", ":", ",")) and len(p) <= 80:
            self.titulo(m.group(2))
            return
        if m := TOPO.match(p):
            blocos.append({"tipo": "passo", "rotulo": m.group(1), "texto": m.group(2)})
            return
        if m := OBS.match(p):
            blocos.append({"tipo": "obs", "texto": m.group(1)})
            return
        if m := NOTA.match(p):
            blocos.append({"tipo": "nota", "texto": m.group(2)})
            return
        if p.startswith("#"):
            nivel = len(p) - len(p.lstrip("#"))
            txt = p.lstrip("#").strip().strip("*").strip()
            if txt:
                (self.titulo(txt) if nivel <= 1 and not self.unica else blocos.append({"tipo": "subtitulo", "texto": txt}))
            return
        if set(p) <= set("-—_ "):
            return
        if m := BULLET.match(p):
            p = "• " + m.group(1)
        blocos.append({"tipo": "texto", "texto": p})

    def imagem(self, arquivo: str):
        self._atual().append({"tipo": "imagem", "arquivo": arquivo, "legenda": ""})

    def resultado(self) -> list[dict]:
        return [s for s in self.secoes if s["blocos"]]


def juntar_linhas(linhas: list[str]) -> list[str]:
    """Junta linhas quebradas pelo PDF em parágrafos."""
    out: list[str] = []
    for l in linhas:
        l = l.strip()
        if not l:
            continue
        marcador = PASSO.match(l) or TOPO.match(l) or BULLET.match(l) or OBS.match(l) or NOTA.match(l) or SQL.match(l) or l.startswith("#")
        if out and not marcador and not out[-1].endswith(FIM_FRASE) and not SQL.match(out[-1]):
            out[-1] += " " + l
        else:
            out.append(l)
    return out


# ---------------- imagens ----------------
class Imagens:
    def __init__(self, codigo: str):
        self.dir = IMAGENS / codigo
        self.codigo = codigo
        self.n = 0
        self.vistos: set[str] = set()

    def preparar(self, candidatos: list[bytes]) -> set[str]:
        """Hashes repetidos 3+ vezes no documento são logos/rodapés."""
        c = Counter(hashlib.md5(b).hexdigest() for b in candidatos)
        return {h for h, n in c.items() if n >= 3}

    def salvar(self, dados: bytes, ignorar: set[str]) -> str | None:
        h = hashlib.md5(dados).hexdigest()
        if h in ignorar or h in self.vistos or len(dados) < 2500:
            return None
        try:
            img = Image.open(io.BytesIO(dados))
            img.load()
        except Exception:
            return None
        if img.width < 90 or img.height < 40:
            return None
        self.vistos.add(h)
        self.n += 1
        self.dir.mkdir(parents=True, exist_ok=True)
        fmt = (img.format or "").lower()
        if fmt in ("png", "jpeg", "gif"):
            nome = f"{self.n:02d}.{'jpg' if fmt == 'jpeg' else fmt}"
            (self.dir / nome).write_bytes(dados)
        else:
            nome = f"{self.n:02d}.png"
            img.convert("RGB").save(self.dir / nome, "PNG")
        return f"{self.codigo}/{nome}"


# ---------------- leitores ----------------
def imagens_desenhadas(recursos, dados: bytes, saida: set[int], nivel: int = 0) -> None:
    """Segue os operadores "/Nome Do" do conteúdo (inclusive dentro de Forms) e guarda o id das imagens."""
    if recursos is None or nivel > 5:
        return
    recursos = recursos.get_object()
    xobjs = recursos.get("/XObject")
    if xobjs is None:
        return
    xobjs = xobjs.get_object()
    for nome in re.findall(rb"/([^\s/\[\]<>(){}%]+)\s+Do\b", dados):
        chave = "/" + nome.decode("latin-1")
        if chave not in xobjs:
            continue
        ref = xobjs.raw_get(chave)
        obj = ref.get_object()
        if obj.get("/Subtype") == "/Image":
            if hasattr(ref, "idnum"):
                saida.add(ref.idnum)
        elif obj.get("/Subtype") == "/Form":
            imagens_desenhadas(obj.get("/Resources"), obj.get_data(), saida, nivel + 1)


def ler_pdf(arq: Path, m: Montador, imgs: Imagens) -> str:
    r = pypdf.PdfReader(str(arq))
    paginas = [(p.extract_text() or "").splitlines() for p in r.pages]
    freq = Counter(norm(l) for pg in paginas for l in set(pg) if norm(l))
    limite = max(2, ceil(len(paginas) * 0.5))
    capa = 0 if (paginas and any(norm(l) == "sumario" for l in paginas[0])) else None
    brutas = []
    for pg in r.pages:
        # só as imagens que a página realmente desenha; alguns PDFs listam todas as imagens em todas as páginas
        try:
            usadas: set[int] = set()
            conteudo = pg.get_contents()
            if conteudo is not None:
                imagens_desenhadas(pg.get("/Resources"), conteudo.get_data(), usadas)
            lista = pg.images
            brutas.append([i.data for i in lista if not usadas or getattr(i.indirect_reference, "idnum", None) in usadas])
        except Exception:
            brutas.append([])
    ignorar = imgs.preparar([b for pg in brutas for b in pg])
    texto_total = []
    for i, linhas in enumerate(paginas):
        if i == capa:
            continue
        uteis = [l for l in linhas if norm(l) and not (len(paginas) > 1 and freq[norm(l)] >= limite) and not norm(l).isdigit()]
        texto_total += uteis
        for p in juntar_linhas(uteis):
            m.paragrafo(p)
        for b in brutas[i]:
            if nome := imgs.salvar(b, ignorar):
                m.imagem(nome)
    return "\n".join(texto_total)


def ler_docx(arq: Path, m: Montador, imgs: Imagens) -> str:
    d = docx.Document(str(arq))
    partes = d.part.related_parts
    todas = [p.blob for p in partes.values() if "image" in p.content_type]
    ignorar = imgs.preparar(todas)
    texto = []
    for el in d.element.body.iterchildren():
        tag = el.tag.split("}")[-1]
        if tag == "p":
            t = "".join(n.text or "" for n in el.iter() if n.tag.endswith("}t")).strip()
            estilo = el.xpath("string(./w:pPr/w:pStyle/@w:val)") or ""
            if t:
                texto.append(t)
                if re.match(r"(heading|t[ií]tulo)\s*[12]?$", estilo, re.I) and len(t) < 90:
                    m.titulo(limpar_emoji(t))
                else:
                    m.paragrafo(t)
            for rid in el.xpath(".//a:blip/@r:embed"):
                if rid in partes and (nome := imgs.salvar(partes[rid].blob, ignorar)):
                    m.imagem(nome)
        elif tag == "tbl":
            for linha in el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cel = [("".join(n.text or "" for n in c.iter() if n.tag.endswith("}t"))).strip() for c in linha.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")]
                if any(cel):
                    m.paragrafo(" | ".join(cel))
                    texto.append(" ".join(cel))
    return "\n".join(texto)


def ler_txt(arq: Path, m: Montador) -> str:
    b = arq.read_bytes()
    try:
        t = b.decode("utf-8")
    except UnicodeDecodeError:
        t = b.decode("cp1252", "replace")
    linhas = [l.strip() for l in t.splitlines() if l.strip()]
    if linhas and norm(arq.stem)[:12] and norm(linhas[0]).startswith(norm(arq.stem)[:12]):
        resto = linhas[0][len(arq.stem):].strip(" :-")
        linhas = ([resto] if len(resto) > 3 and norm(resto) != norm(arq.stem) else []) + linhas[1:]
    for p in linhas:
        m.paragrafo(p)
    return t


def main():
    cur = json.loads(CURADORIA.read_text(encoding="utf-8"))
    origem = Path(cur["origem"])
    con = sqlite3.connect(RAIZ / "dados" / "nexus.db")
    nomes = {r[0].lower() for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (cur.get("banco", "demo_pdv"),))}
    menus = {r[0] for r in con.execute("SELECT id FROM menus")}
    con.close()
    MANUAIS.mkdir(parents=True, exist_ok=True)
    IMAGENS.mkdir(parents=True, exist_ok=True)
    problemas = []
    # autores citados nos documentos ("Elaborado por: …"): coletados para serem removidos de qualquer linha solta
    textos_brutos = json.loads((Path(__file__).with_name("autores.json")).read_text(encoding="utf-8")) if Path(__file__).with_name("autores.json").exists() else []
    Montador.autores = {norm(n) for n in textos_brutos}
    for spec in cur["manuais"]:
        destino = MANUAIS / f"{spec['codigo']}.json"
        try:
            editado = destino.exists() and json.loads(destino.read_text(encoding="utf-8")).get("editado")
        except ValueError:
            editado = False
        if editado:
            print(f"= {spec['codigo']} editado à mão, mantido")
            continue
        if spec["menu"] not in menus:
            problemas.append(f"{spec['codigo']}: menu {spec['menu']} não existe")
        shutil.rmtree(IMAGENS / spec["codigo"], ignore_errors=True)
        imgs = Imagens(spec["codigo"])
        secoes, textos, versao = [], [], "1.0"
        for f in spec["fontes"]:
            arq = origem / f["arquivo"]
            if not arq.exists():
                problemas.append(f"{spec['codigo']}: arquivo não encontrado: {f['arquivo']}")
                continue
            m = Montador("Procedimento", f.get("secao"))
            ext = arq.suffix.lower()
            if ext == ".pdf":
                t = ler_pdf(arq, m, imgs)
            elif ext == ".docx":
                t = ler_docx(arq, m, imgs)
            else:
                t = ler_txt(arq, m)
            if v := re.search(r"Vers[aã]o\s+(\d{4})\s+de", t):
                versao = v.group(1)
            textos.append(t)
            secoes += m.resultado()
        sqls = "\n".join(b["texto"] for s in secoes for b in s["blocos"] if b["tipo"] == "sql")
        manual = {
            "codigo": spec["codigo"], "titulo": spec["titulo"], "subtitulo": spec.get("subtitulo", ""), "versao": versao,
            "modulo": "pdv", "menu": spec["menu"], "fontes": [f["arquivo"] for f in spec["fontes"]],
            "tabelas": tabelas_citadas(mascarar("\n".join(textos)), sqls, nomes), "secoes": secoes,
        }
        destino.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
        nb = sum(len(s["blocos"]) for s in secoes)
        print(f"+ {spec['codigo']:12} {len(secoes):2} seções {nb:3} blocos {imgs.n:3} prints  tabelas={','.join(manual['tabelas'][:6])}")
    if problemas:
        print("\nATENÇÃO:\n  " + "\n  ".join(problemas))


if __name__ == "__main__":
    main()
