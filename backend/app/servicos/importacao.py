"""Converte um documento de suporte (PDF, Word, .txt ou .md) num rascunho de manual da Wiki.

Usado pela rota POST /api/manuais/importar e pela importação em lote (ferramentas/importar_processos.py). Os prints
vão para onde a função `guardar` mandar: por padrão, para o rascunho do editor (guardar_rascunho), e só viram
definitivos quando o manual é salvo.

O arquivo vem de fora: o tipo é decidido pelos bytes (não pela extensão), com limites de tamanho, de páginas e de
imagens, e nada do documento é executado (macros, scripts). Recusas levantam ImportacaoRecusada com o status HTTP.
"""
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Callable
from math import ceil
from pathlib import Path

import docx
import pypdf
from PIL import Image

from ..config import RAIZ
from .limpeza import contar_segredos, mascarar, tabelas_citadas
from .manuais import guardar_rascunho

# ---------------- limites e tipo do arquivo ----------------
TAMANHO_MAXIMO = 20 * 1024 * 1024        # arquivo enviado
DESCOMPACTADO_MAXIMO = 100 * 1024 * 1024  # soma do conteúdo de um .docx (zip)
TAXA_MAXIMA = 100                         # descompactado / compactado; documentos normais ficam bem abaixo de 20
PAGINAS_MAXIMO = 200
IMAGENS_MAXIMO = 300                      # imagens lidas do documento; as demais ficam de fora (com aviso)
FORMATOS = "PDF, Word (.docx), .txt ou .md"
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # Word 97-2003 (.doc) e outros arquivos antigos do Office


class ImportacaoRecusada(Exception):
    """Documento que não pode ser importado: `status` é o código HTTP e `mensagem` vai para quem enviou."""

    def __init__(self, status: int, mensagem: str, formato: str = "desconhecido"):
        super().__init__(mensagem)
        self.status, self.mensagem, self.formato = status, mensagem, formato


def _conferir_zip(dados: bytes) -> set[str]:
    try:
        itens = zipfile.ZipFile(io.BytesIO(dados)).infolist()
    except (zipfile.BadZipFile, ValueError) as e:
        raise ImportacaoRecusada(415, f"Arquivo compactado danificado. Envie {FORMATOS}.") from e
    # zip bomb: o tamanho declarado de cada item é conferido antes de descompactar qualquer coisa
    total = sum(i.file_size for i in itens)
    compactado = max(1, sum(i.compress_size for i in itens))
    if total > DESCOMPACTADO_MAXIMO or total / compactado > TAXA_MAXIMA:
        raise ImportacaoRecusada(413, "O documento descompactado fica grande demais para importar.", "docx")
    return {i.filename for i in itens}


def decodificar(dados: bytes) -> tuple[str, str] | None:
    """Texto puro em UTF-8 (com ou sem BOM) ou cp1252 (Bloco de Notas antigo). None se parecer binário."""
    if b"\x00" in dados:
        return None
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            t = dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
        controles = sum(1 for c in t if ord(c) < 32 and c not in "\t\n\r\f")
        return (t, codificacao) if controles <= len(t) * 0.01 else None
    return None


def identificar(dados: bytes, nome_arquivo: str) -> str:
    """Tipo do documento pelos bytes: "pdf", "docx", "md" ou "txt". Recusa o resto com ImportacaoRecusada."""
    ext = Path(nome_arquivo).suffix.lower()
    if len(dados) > TAMANHO_MAXIMO:
        raise ImportacaoRecusada(413, f"Arquivo maior que {TAMANHO_MAXIMO // 1024 // 1024} MB.")
    if not dados.strip():
        raise ImportacaoRecusada(422, "Arquivo vazio.")
    if ext == ".doc" or dados.startswith(OLE):
        raise ImportacaoRecusada(415, "Arquivo do Word antigo (.doc): abra no Word, salve como .docx e importe de novo.", "doc")
    if ext == ".docm":
        raise ImportacaoRecusada(415, "Documento do Word com macros (.docm): salve como .docx sem macros e importe de novo.", "docm")
    if dados.startswith(b"%PDF-"):
        return "pdf"
    if dados.startswith(b"PK\x03\x04"):
        nomes = _conferir_zip(dados)
        if "word/vbaProject.bin" in nomes:
            raise ImportacaoRecusada(415, "Documento do Word com macros: salve como .docx sem macros e importe de novo.", "docm")
        if "word/document.xml" not in nomes:
            raise ImportacaoRecusada(415, f"Arquivo compactado que não é um documento do Word. Envie {FORMATOS}.")
        return "docx"
    if decodificar(dados) is None:
        raise ImportacaoRecusada(415, f"Tipo de arquivo não suportado. Envie {FORMATOS}.")
    return "md" if ext == ".md" else "txt"

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
PADRAO = "Procedimento"  # título da seção quando o documento começa sem título
VERSAO = re.compile(r"Vers[aã]o\s+(\d{4})\s+de")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def limpar_emoji(t: str) -> str:
    # ícones das fontes de símbolo e emojis decorativos não aparecem nos manuais
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️⃣-가-힯脀-迿\ud800-\udfff]", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


# ---------------- classificação de linhas em blocos ----------------
AUTORES = RAIZ / "ferramentas" / "autores.json"  # fora do git: nomes de quem elaborou/revisou os documentos reais


class Montador:
    """Recebe parágrafos e imagens na ordem do documento e monta seções/blocos."""

    # nomes de quem elaborou/revisou: nunca entram no manual
    autores: set[str] = {norm(n) for n in json.loads(AUTORES.read_text(encoding="utf-8"))} if AUTORES.exists() else set()

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
            self.subtitulo(texto)
        else:
            self.secoes.append({"titulo": texto, "blocos": []})

    def subtitulo(self, texto: str):
        self._atual().append({"tipo": "subtitulo", "texto": limpar_emoji(texto).rstrip(" .:")})

    def passo(self, rotulo: str, texto: str):
        """Item de lista numerada do Word: o número não está no texto, vem da numeração do documento."""
        if t := limpar_emoji(mascarar(texto.strip())):
            self._atual().append({"tipo": "passo", "rotulo": rotulo, "texto": t})

    def codigo(self, linha: str):
        """Parágrafo em fonte monoespaçada (Word): linhas seguidas viram um bloco sql só."""
        linha = mascarar(linha.rstrip())
        blocos = self._atual()
        if blocos and blocos[-1]["tipo"] == "sql":
            blocos[-1]["texto"] += "\n" + linha
        else:
            blocos.append({"tipo": "sql", "texto": linha})

    def _item_de_lista(self, item: str, nivel: int):
        """Itens seguidos (e a linha terminada em ":" que os apresenta) ficam num bloco de texto só, com Tab antes do
        marcador nos subitens: é assim que o editor guarda uma lista colada, e o textoRico.tsx a mostra igual."""
        blocos = self._atual()
        linha = "\t" * nivel + "• " + item
        if blocos and blocos[-1]["tipo"] == "texto":
            ultima = blocos[-1]["texto"].rsplit("\n", 1)[-1].lstrip("\t")
            if ultima.startswith("• ") or ultima.endswith(":"):
                blocos[-1]["texto"] += "\n" + linha
                return
        blocos.append({"tipo": "texto", "texto": linha})

    def paragrafo(self, p: str, nivel: int = 0):
        """`nivel`: recuo do item de lista (0 = primeiro nível); só vale para linhas com marcador."""
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
        # SQL antes da limpeza de asteriscos: o "*" de "SELECT * FROM" faz parte do comando
        if SQL.match(p):
            linha = re.sub(r"^(-|//)\s*", "", p)
            if blocos and blocos[-1]["tipo"] == "sql":
                blocos[-1]["texto"] += "\n" + linha
            else:
                blocos.append({"tipo": "sql", "texto": linha})
            return
        if p.count("*") % 2 == 1:
            p = p.replace("*", "") if "**" not in p else re.sub(r"(?<!\*)\*(?!\*)", "", p)
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
            self._item_de_lista(m.group(1), nivel)
            return
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
        self.repetidas = 0     # descartadas por aparecerem 3+ vezes (logo, rodapé)
        self.excedeu = False   # passou de IMAGENS_MAXIMO: o resto ficou de fora
        self.lidas = 0
        self.vistos: set[str] = set()

    def preparar(self, candidatos: list[bytes]) -> set[str]:
        """Hashes repetidos 3+ vezes no documento são logos/rodapés."""
        c = Counter(hashlib.md5(b).hexdigest() for b in candidatos)
        return {h for h, n in c.items() if n >= 3}

    def salvar(self, dados: bytes, ignorar: set[str]) -> str | None:
        h = hashlib.md5(dados).hexdigest()
        if h in ignorar:
            self.repetidas += 1
            return None
        if h in self.vistos or len(dados) < 2500:
            return None
        if self.lidas >= IMAGENS_MAXIMO:
            self.excedeu = True
            return None
        self.lidas += 1
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


def ler_pdf(dados: bytes, m: Montador, imgs: Imagens, avisos: list[str]) -> str:
    r = pypdf.PdfReader(io.BytesIO(dados))
    if r.is_encrypted and not r.decrypt(""):
        raise ImportacaoRecusada(422, "PDF protegido por senha: salve uma cópia sem senha e importe de novo.", "pdf")
    if len(r.pages) > PAGINAS_MAXIMO:
        raise ImportacaoRecusada(413, f"PDF com {len(r.pages)} páginas; o limite é {PAGINAS_MAXIMO}. Divida o documento.", "pdf")
    paginas = [(p.extract_text() or "").splitlines() for p in r.pages]
    if sum(len(norm(l)) for pg in paginas for l in pg) < 20 * len(paginas):
        avisos.append("PDF sem texto: parece escaneado. Leitura de imagem (OCR) não é suportada.")
    freq = Counter(norm(l) for pg in paginas for l in set(pg) if norm(l))
    limite = max(2, ceil(len(paginas) * 0.5))
    capa = 0 if (paginas and any(norm(l) == "sumario" for l in paginas[0])) else None
    brutas, lidas = [], 0
    for pg in r.pages:
        # só as imagens que a página realmente desenha; alguns PDFs listam todas as imagens em todas as páginas
        try:
            usadas: set[int] = set()
            conteudo = pg.get_contents()
            if conteudo is not None:
                imagens_desenhadas(pg.get("/Resources"), conteudo.get_data(), usadas)
            lista = [i for i in pg.images if not usadas or getattr(i.indirect_reference, "idnum", None) in usadas]
            # cada imagem é descompactada ao ler .data: o limite vale antes disso
            if lidas + len(lista) > IMAGENS_MAXIMO:
                imgs.excedeu = True
                lista = lista[:max(0, IMAGENS_MAXIMO - lidas)]
            lidas += len(lista)
            brutas.append([i.data for i in lista])
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


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ESTILO_TITULO = re.compile(r"^(heading|t[ií]?tulo|title)\s*(\d)?$", re.I)  # o Word em português grava "Ttulo1"
MONOESPACADAS = {"consolas", "courier new", "courier", "lucida console", "cascadia code", "cascadia mono",
                 "jetbrains mono", "source code pro", "menlo", "monaco", "dejavu sans mono", "liberation mono"}


def formatos_de_lista(d) -> dict[tuple[str, int], str]:
    """(numId, nível) -> formato da numeração do Word ("bullet", "decimal", "lowerLetter"...)."""
    try:
        numeracao = d.part.numbering_part.element
    except (KeyError, NotImplementedError):
        return {}
    abstratos = {}
    for a in numeracao.findall(W + "abstractNum"):
        niveis = {}
        for lvl in a.findall(W + "lvl"):
            fmt = lvl.find(W + "numFmt")
            niveis[int(lvl.get(W + "ilvl"))] = fmt.get(W + "val") if fmt is not None else "decimal"
        abstratos[a.get(W + "abstractNumId")] = niveis
    mapa = {}
    for n in numeracao.findall(W + "num"):
        ref = n.find(W + "abstractNumId")
        for nivel, fmt in abstratos.get(ref.get(W + "val") if ref is not None else None, {}).items():
            mapa[(n.get(W + "numId"), nivel)] = fmt
    return mapa


def lista_do_paragrafo(el, d, estilo: str) -> tuple[str, int] | None:
    """(numId, nível) da lista do parágrafo: no próprio parágrafo ou no estilo dele ("List Number", "Lista")."""
    num = el.xpath("string(./w:pPr/w:numPr/w:numId/@w:val)")
    nivel = el.xpath("string(./w:pPr/w:numPr/w:ilvl/@w:val)")
    if not num and estilo:
        st = d.styles.element.xpath(f'./w:style[@w:styleId="{estilo}"]')
        if st:
            num = st[0].xpath("string(./w:pPr/w:numPr/w:numId/@w:val)")
            nivel = nivel or st[0].xpath("string(./w:pPr/w:numPr/w:ilvl/@w:val)")
            # "List Bullet 2", "Lista com marcadores 3": o recuo vem do estilo, não do nível da numeração
            if not nivel and (n := re.search(r"(\d)$", estilo)):
                nivel = str(int(n.group(1)) - 1)
    return (num, int(nivel or 0)) if num and num != "0" else None


def monoespacado(el, d, estilo: str) -> bool:
    """Todo o texto do parágrafo numa fonte de código (Consolas, Courier...): candidato a bloco sql."""
    fonte_estilo = ""
    if estilo:
        fonte_estilo = d.styles.element.xpath(f'string(./w:style[@w:styleId="{estilo}"]/w:rPr/w:rFonts/@w:ascii)')
    runs = [r for r in el.xpath("./w:r") if "".join(t.text or "" for t in r.iter(W + "t")).strip()]
    return bool(runs) and all(
        (r.xpath("string(./w:rPr/w:rFonts/@w:ascii)") or fonte_estilo).lower() in MONOESPACADAS for r in runs)


AVISO_TABELA = "Tabela do Word convertida em texto com ' | ' entre as colunas: confira o alinhamento."


def ler_docx(dados: bytes, m: Montador, imgs: Imagens, avisos: list[str]) -> str:
    d = docx.Document(io.BytesIO(dados))
    partes = d.part.related_parts
    # o Word guarda uma imagem repetida uma vez só e a referencia várias: conta as referências, não os arquivos
    todas = [partes[rid].blob for rid in d.element.body.xpath(".//a:blip/@r:embed") if rid in partes]
    ignorar = imgs.preparar(todas)
    formatos = formatos_de_lista(d)
    contagem: dict[str, list[int]] = {}  # numeração de cada lista numerada, por nível (1, 1.1, 1.2, 2...)
    texto = []
    for el in d.element.body.iterchildren():
        tag = el.tag.split("}")[-1]
        if tag == "p":
            t = "".join(n.text or "" for n in el.iter() if n.tag.endswith("}t")).strip()
            estilo = el.xpath("string(./w:pPr/w:pStyle/@w:val)") or ""
            if t:
                texto.append(t)
                titulo = ESTILO_TITULO.match(estilo)
                lista = lista_do_paragrafo(el, d, estilo)
                # o nível pode vir do estilo ("List Bullet 2") e não existir na numeração: vale o formato do nível 0
                fmt = (formatos.get(lista) or formatos.get((lista[0], 0)) or "decimal") if lista else None
                if titulo and len(t) < 90:
                    # Título 1 (ou sem número) abre seção; Título 2 em diante vira subtítulo dentro dela
                    (m.titulo if (titulo.group(2) or "1") == "1" else m.subtitulo)(limpar_emoji(t))
                elif fmt == "bullet":
                    m.paragrafo("• " + t, lista[1])
                elif fmt and fmt != "none":
                    num, nivel = lista
                    c = contagem.setdefault(num, [])
                    del c[nivel + 1:]
                    c.extend([0] * (nivel + 1 - len(c)))
                    c[nivel] += 1
                    m.passo(".".join(str(x or 1) for x in c), t)
                elif monoespacado(el, d, estilo):
                    m.codigo(t)
                else:
                    m.paragrafo(t)
            for rid in el.xpath(".//a:blip/@r:embed"):
                if rid in partes and (nome := imgs.salvar(partes[rid].blob, ignorar)):
                    m.imagem(nome)
        elif tag == "tbl":
            if AVISO_TABELA not in avisos:
                avisos.append(AVISO_TABELA)
            for linha in el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cel = [("".join(n.text or "" for n in c.iter() if n.tag.endswith("}t"))).strip() for c in linha.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")]
                if any(cel):
                    m.paragrafo(" | ".join(cel))
                    texto.append(" ".join(cel))
    return "\n".join(texto)


def ler_txt(t: str, nome_arquivo: str, m: Montador) -> str:
    stem = Path(nome_arquivo).stem
    linhas = [l.rstrip() for l in t.splitlines() if l.strip()]
    # a primeira linha costuma repetir o nome do arquivo: ela vira o título, não um parágrafo
    if linhas and norm(stem)[:12] and norm(linhas[0]).startswith(norm(stem)[:12]):
        resto = linhas[0].strip()[len(stem):].strip(" :-")
        linhas = ([resto] if len(resto) > 3 and norm(resto) != norm(stem) else []) + linhas[1:]
    for p in linhas:
        m.paragrafo(p, nivel_do_recuo(p))
    return t


def nivel_do_recuo(linha: str) -> int:
    """Mesma regra do textoRico.tsx (nivelDe): Tab vale 2 espaços, cada 2 espaços é um nível."""
    recuo = linha[:len(linha) - len(linha.lstrip(" \t"))]
    return sum(2 if c == "\t" else 1 for c in recuo) >> 1


def titulo_do_arquivo(nome_arquivo: str) -> str:
    t = re.sub(r"[_\s]+", " ", Path(nome_arquivo).stem).strip()
    return t[:1].upper() + t[1:]


def plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def converter(dados: bytes, nome_arquivo: str, nomes_tabelas: set[str], secao_unica: str | None = None, *,
              guardar: Callable[[bytes], str | None] = guardar_rascunho, imagens: Imagens | None = None) -> dict:
    """Documento -> rascunho de manual (não grava nada além dos prints).

    nomes_tabelas: tabelas do banco do módulo, para achar as citadas no texto. secao_unica: o documento inteiro vira
    uma seção com esse título (manuais de perguntas frequentes). `imagens` permite que vários documentos de um mesmo
    manual compartilhem a numeração e o descarte de prints repetidos.
    Levanta ImportacaoRecusada se o arquivo não puder ser importado.
    """
    formato = identificar(dados, nome_arquivo)
    imgs = imagens or Imagens(guardar)
    repetidas_antes = imgs.repetidas
    m = Montador(PADRAO, secao_unica)
    avisos: list[str] = []
    try:
        if formato == "pdf":
            texto = ler_pdf(dados, m, imgs, avisos)
        elif formato == "docx":
            texto = ler_docx(dados, m, imgs, avisos)
        else:
            texto, codificacao = decodificar(dados)
            if codificacao == "cp1252":
                avisos.append(f"Arquivo {Path(nome_arquivo).suffix or 'de texto'} em cp1252 (não UTF-8): confira os acentos.")
            ler_txt(texto, nome_arquivo, m)
    except ImportacaoRecusada:
        raise
    except Exception as e:  # PDF/Word danificado: a biblioteca levanta tipos variados
        raise ImportacaoRecusada(422, f"Não foi possível ler o documento ({formato}): o arquivo parece danificado.", formato) from e
    secoes = m.resultado()
    titulos = [s["titulo"] for s in secoes if s["titulo"] != PADRAO]
    if secao_unica is None and not titulos and secoes:
        avisos.append("Nenhum título encontrado: todo o conteúdo ficou em uma seção.")
    if n := imgs.repetidas - repetidas_antes:
        avisos.append(f"{plural(n, 'imagem ignorada', 'imagens ignoradas')} por se repetir no documento (logo, rodapé).")
    if imgs.excedeu:
        avisos.append(f"O documento tem mais de {IMAGENS_MAXIMO} imagens: só as primeiras foram importadas.")
    if n := contar_segredos(texto):
        avisos.append(f"{plural(n, 'senha mascarada', 'senhas mascaradas')} (******): confira se o texto continua claro.")
    sqls = "\n".join(b["texto"] for s in secoes for b in s["blocos"] if b["tipo"] == "sql")
    v = VERSAO.search(texto)
    return {
        # título sugerido: o primeiro título do documento; senão, o nome do arquivo
        "titulo": titulos[0] if titulos and secao_unica is None else titulo_do_arquivo(nome_arquivo),
        "subtitulo": "", "versao": v.group(1) if v else None, "formato": formato,
        "secoes": secoes, "fontes": [nome_arquivo],
        "tabelas": tabelas_citadas(mascarar(texto), sqls, nomes_tabelas),
        "avisos": avisos,
    }
