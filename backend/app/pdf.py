"""Gera o PDF do manual abrindo a versão de impressão do frontend num navegador headless.

Usa o Microsoft Edge já instalado (channel="msedge"), então não é preciso baixar o Chromium.
Cabeçalho e rodapé (com número de página) seguem a identidade visual da rede Farmácias Associadas.
"""
import base64
import html
from urllib.parse import quote  # noqa: F401  (reexportado para as rotas)

from playwright.sync_api import sync_playwright

from .config import DIST, FRONTEND, PDF_CANAL, PROJETO

# turquesa (Pantone 326C), turquesa escuro (texto) e laranja do logo da rede
TURQUESA, TURQUESA_ESCURO, LARANJA = "#00b2a9", "#007a73", "#f36f21"


def _logo() -> str:
    """O cabeçalho do PDF não carrega arquivos externos: o logo vai embutido. No contêiner ele está no build
    (frontend/dist), em desenvolvimento em frontend/public; sem nenhum dos dois, o nome em texto."""
    for pasta in (DIST, PROJETO / "frontend" / "public"):
        arq = pasta / "marca" / "logo-associadas.png"
        if arq.exists():
            return f'<img src="data:image/png;base64,{base64.b64encode(arq.read_bytes()).decode()}" style="height:8mm">'
    return f'<span style="font-weight:800;color:{TURQUESA_ESCURO}">Farmácias Associadas</span>'


MARCA = _logo()

CABECALHO = f"""
<div style="width:100%;font-family:Segoe UI,Arial,Liberation Sans,sans-serif;font-size:8.5pt;padding:0 14mm 0 30mm;display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
  <b style="color:#222">Support Nexus – Base de conhecimento</b>
  <span style="display:flex;align-items:center">{MARCA}</span>
</div>"""

def texto_rodape(alterado_em: str | None) -> str:
    """"Manual alterado em 27/10/2026 às 20:15" (hora de Brasília, gravada assim); sem alteração, o texto padrão."""
    if not alterado_em:
        return "Documento gerado pelo Support Nexus"
    data, _, hora = alterado_em.partition(" ")
    ano, mes, dia = data.split("-")
    return f"Manual alterado em {dia}/{mes}/{ano} às {hora[:5]}"


def rodape(alterado_em: str | None) -> str:
    return f"""
<div style="width:100%;font-family:Segoe UI,Arial,Liberation Sans,sans-serif;font-size:9pt;padding:0 14mm 0 12mm;display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
  <span style="font-weight:700;color:#333"><span class="pageNumber"></span></span>
  <span style="flex:1;height:2px;margin:0 6mm;background:linear-gradient(90deg,{TURQUESA},{LARANJA})"></span>
  <span style="color:#666;font-size:8pt">{html.escape(texto_rodape(alterado_em))}</span>
</div>"""


def gerar(codigo: str, alterado_em: str | None = None) -> bytes:
    with sync_playwright() as p:
        # --disable-dev-shm-usage: fora do docker-compose (shm_size) o /dev/shm do contêiner tem só 64 MB e o
        # Chromium quebra em PDFs grandes; com a opção ele usa /tmp. No Windows (Edge) não muda nada.
        nav = p.chromium.launch(channel=PDF_CANAL, args=["--disable-dev-shm-usage"])
        try:
            pag = nav.new_page()
            pag.goto(f"{FRONTEND}/manuais/{quote(codigo)}/imprimir", wait_until="networkidle")
            pag.wait_for_selector("[data-pronto]", timeout=15000)
            pag.evaluate("() => document.fonts.ready.then(() => true)")  # sem isso o PDF pode sair com a fonte reserva
            pag.emulate_media(media="print")
            return pag.pdf(format="A4", print_background=True, display_header_footer=True,
                           header_template=CABECALHO, footer_template=rodape(alterado_em),
                           margin={"top": "24mm", "bottom": "22mm", "left": "0", "right": "0"})
        finally:
            nav.close()
