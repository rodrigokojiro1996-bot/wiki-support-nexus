"""Converte um documento de suporte (PDF, Word ou .txt) num rascunho de manual da Wiki.

Usado pela importação em lote (ferramentas/importar_processos.py). Os prints vão para onde a função `guardar`
mandar: por padrão, para o rascunho do editor (guardar_rascunho), e só viram definitivos quando o manual é salvo.
"""
import hashlib
import io
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from math import ceil
from pathlib import Path

import docx
import pypdf
from PIL import Image

from .limpeza import mascarar, tabelas_citadas
from .manuais import guardar_rascunho

# ---------------- limpeza ----------------
# senhas mascaradas e tabelas citadas: as mesmas regras do editor de manuais (limpeza.py)
RUIDO = re.compile(r"(elaborado por|revisado por|aprovado por|^cria[cç][aã]o:|^revis[aã]o:|n[ºo°]\.?\s*revis|vers[aã]o do documento|"
                   r"^sum[aá]rio$|\.{6,}|erro! indicador|^vers[aã]o \d{4} de)", re.I)
SQL = re.compile(r"^(-|//)?\s*(select|update|delete|insert|repair|cd\\|mysql\b|mysqlcheck|mysqladmin)", re.I)
PASSO = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\.?\s*[-–]?\s*(.+)$")
TOPO = re.compile(r"^(\d+)\s*[\.\)]\s*[-–]?\s*(.+)$")
BULLET = re.compile(r"^[•▪●◦\-–*]\s*(.+)$")
OBS = re.compile(r"^OBS\S*\s*[:.]?\s*(.+)$", re.I)
NOTA = re.compile(r"^(importante|aten[cç][aã]o|nota)\s*[:!]\s*(.+)$", re.I)
FIM_FRASE = (".", ":", ";", "!", "?")
VERSAO = re.compile(r"Vers[aã]o\s+(\d{4})\s+de")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def limpar_emoji(t: str) -> str:
    # ícones das fontes de símbolo e emojis decorativos não aparecem nos manuais
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️⃣-가-힯脀-迿\ud800-\udfff]", "", t)
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
    """Filtra os prints do documento (logos, ícones, repetidos) e entrega cada um, já em png/jpg/gif, para `guardar`."""

    def __init__(self, guardar: Callable[[bytes], str | None]):
        self.guardar = guardar
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
        if (img.format or "").lower() not in ("png", "jpeg", "gif"):
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "PNG")
            dados = buf.getvalue()
        nome = self.guardar(dados)
        if nome:
            self.n += 1
        return nome


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


def ler_pdf(dados: bytes, m: Montador, imgs: Imagens) -> str:
    r = pypdf.PdfReader(io.BytesIO(dados))
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


def ler_docx(dados: bytes, m: Montador, imgs: Imagens) -> str:
    d = docx.Document(io.BytesIO(dados))
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


def ler_txt(dados: bytes, nome_arquivo: str, m: Montador) -> str:
    try:
        t = dados.decode("utf-8")
    except UnicodeDecodeError:
        t = dados.decode("cp1252", "replace")
    stem = Path(nome_arquivo).stem
    linhas = [l.strip() for l in t.splitlines() if l.strip()]
    # a primeira linha costuma repetir o nome do arquivo: ela vira o título, não um parágrafo
    if linhas and norm(stem)[:12] and norm(linhas[0]).startswith(norm(stem)[:12]):
        resto = linhas[0][len(stem):].strip(" :-")
        linhas = ([resto] if len(resto) > 3 and norm(resto) != norm(stem) else []) + linhas[1:]
    for p in linhas:
        m.paragrafo(p)
    return t


def titulo_do_arquivo(nome_arquivo: str) -> str:
    t = re.sub(r"[_\s]+", " ", Path(nome_arquivo).stem).strip()
    return t[:1].upper() + t[1:]


def converter(dados: bytes, nome_arquivo: str, nomes_tabelas: set[str], secao_unica: str | None = None, *,
              guardar: Callable[[bytes], str | None] = guardar_rascunho, imagens: Imagens | None = None) -> dict:
    """Documento -> rascunho de manual (não grava nada além dos prints).

    nomes_tabelas: tabelas do banco do módulo, para achar as citadas no texto. secao_unica: o documento inteiro vira
    uma seção com esse título (manuais de perguntas frequentes). `imagens` permite que vários documentos de um mesmo
    manual compartilhem a numeração e o descarte de prints repetidos.
    """
    imgs = imagens or Imagens(guardar)
    m = Montador("Procedimento", secao_unica)
    ext = Path(nome_arquivo).suffix.lower()
    if ext == ".pdf":
        texto = ler_pdf(dados, m, imgs)
    elif ext == ".docx":
        texto = ler_docx(dados, m, imgs)
    else:
        texto = ler_txt(dados, nome_arquivo, m)
    secoes = m.resultado()
    sqls = "\n".join(b["texto"] for s in secoes for b in s["blocos"] if b["tipo"] == "sql")
    v = VERSAO.search(texto)
    return {
        "titulo": titulo_do_arquivo(nome_arquivo), "subtitulo": "", "versao": v.group(1) if v else None,
        "secoes": secoes, "fontes": [nome_arquivo],
        "tabelas": tabelas_citadas(mascarar(texto), sqls, nomes_tabelas),
        "avisos": [],
    }
