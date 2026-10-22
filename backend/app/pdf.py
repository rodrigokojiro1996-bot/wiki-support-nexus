"""Gera o PDF do manual abrindo a versão de impressão do frontend num navegador headless.

Usa o Microsoft Edge já instalado (channel="msedge"), então não é preciso baixar o Chromium.
Cabeçalho e rodapé (com número de página) seguem o modelo visual dos manuais do Support Nexus.
"""
from urllib.parse import quote  # noqa: F401  (reexportado para as rotas)

from playwright.sync_api import sync_playwright

from .config import FRONTEND, PDF_CANAL

AZUL, AZUL_ESCURO, CIANO = "#4f5bd5", "#2f3a9e", "#22b8cf"

# marca do Support Nexus (mesmo desenho de frontend/public/marca/nexus.svg)
MARCA = f"""<svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="{AZUL_ESCURO}"/>
<path d="M9 10 L23 10 L16 23 Z" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.6"/>
<circle cx="9" cy="10" r="3.2" fill="{CIANO}"/><circle cx="23" cy="10" r="3.2" fill="#fff"/><circle cx="16" cy="23" r="3.2" fill="#ffb84d"/></svg>"""

CABECALHO = f"""
<div style="width:100%;font-family:Segoe UI,Arial,Liberation Sans,sans-serif;font-size:8.5pt;padding:0 14mm 0 30mm;display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
  <b style="color:#222">Support Nexus – Base de conhecimento</b>
  <span style="display:flex;align-items:center;gap:6px;font-weight:800;color:{AZUL_ESCURO};font-size:10pt">{MARCA} Support Nexus</span>
</div>"""

RODAPE = f"""
<div style="width:100%;font-family:Segoe UI,Arial,Liberation Sans,sans-serif;font-size:9pt;padding:0 14mm 0 12mm;display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
  <span style="font-weight:700;color:#333"><span class="pageNumber"></span></span>
  <span style="flex:1;height:2px;margin:0 6mm;background:linear-gradient(90deg,{AZUL},{CIANO})"></span>
  <span style="color:#666;font-size:8pt">Documento gerado pelo Support Nexus</span>
</div>"""


def gerar(codigo: str) -> bytes:
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
                           header_template=CABECALHO, footer_template=RODAPE,
                           margin={"top": "24mm", "bottom": "22mm", "left": "0", "right": "0"})
        finally:
            nav.close()
