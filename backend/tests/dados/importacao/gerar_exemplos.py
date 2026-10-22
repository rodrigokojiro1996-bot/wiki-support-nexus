"""Gera os documentos FICTÍCIOS usados nos testes da importação (nada de manual real).

- exemplo.txt  : anotação de suporte em UTF-8
- exemplo.pdf  : 3 páginas com cabeçalho e logo repetidos (devem sumir), passos, OBS, SQL, senha e um print
- docx         : gerado dentro dos testes (ver criar_docx), não fica versionado

Rodar de novo só se os exemplos mudarem (o PDF sai pelo Playwright, no navegador da exportação de manuais):
    backend\\.venv\\Scripts\\python.exe backend\\tests\\dados\\importacao\\gerar_exemplos.py
"""
import base64
import io
import os
import random
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

# mesmo navegador da exportação de manuais (app/config.py: NEXUS_PDF_CANAL)
PDF_CANAL = os.environ.get("NEXUS_PDF_CANAL", "msedge")

AQUI = Path(__file__).resolve().parent

TXT = """Transferência entre lojas
1. Transferência presa como em uso
1.1 Abra Estoque > Transferência entre Lojas > Saída de Transferência.
1.2 Confirme se a transferência ficou marcada como em uso por outro computador.
OBS: só a loja de origem consegue liberar a transferência.
SELECT id_transf, em_uso FROM transferencias WHERE id_transf = 42;
2. Transferência não aparece no destino
Importante: confira a fila de sincronização antes de reenviar.
• Fila parada há mais de 30 minutos
• Terminal sem internet
Senha do banco de teste: password=segredo123
"""


def png(largura: int, altura: int, semente: int) -> bytes:
    """PNG com ruído (comprime pouco: passa do tamanho mínimo que o conversor aceita)."""
    rnd = random.Random(semente)
    img = Image.new("RGB", (largura, altura))
    img.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(largura * altura)])
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def data_uri(dados: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(dados).decode()


def html_pdf() -> str:
    logo = data_uri(png(120, 45, 1))
    tela = data_uri(png(200, 100, 2))
    cab = f'<header>Manual de exemplo do Support Nexus<br><img src="{logo}" width="120" height="45"></header>'
    paginas = [
        """<p>1. Abrir o caixa</p>
           <p>1.1 Acesse Caixa &gt; Abertura de Caixa.</p>
           <p>1.2 Informe o valor inicial e confirme.</p>
           <p>OBS: o caixa só abre com o operador logado.</p>""" + f'<img src="{tela}" width="200" height="100">',
        """<p>2. Conferir o fechamento</p>
           <p>2.1 Acesse Caixa &gt; Fechamento de Caixa.</p>
           <p>Importante: confira as sangrias antes de fechar.</p>
           <p>SELECT * FROM caixa_mov WHERE id_caixa = 10;</p>
           <p>Senha do banco de teste: password=segredo123</p>""",
        """<p>3. Dúvidas frequentes</p>
           <p>O valor informado não bate com o calculado quando falta lançar uma sangria.</p>""",
    ]
    corpo = "".join(f'<section>{cab}{p}</section>' for p in paginas)
    return f"""<!doctype html><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 20mm; }}
      body {{ font-family: Arial, sans-serif; font-size: 12pt; }}
      section {{ break-after: page; }}
      header {{ color: #555; margin-bottom: 8mm; }}
    </style>{corpo}"""


def main():
    (AQUI / "exemplo.txt").write_text(TXT, encoding="utf-8")
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(channel=PDF_CANAL)
        pagina = navegador.new_page()
        pagina.set_content(html_pdf())
        pagina.pdf(path=str(AQUI / "exemplo.pdf"), format="A4")
        navegador.close()
    print("ok:", sorted(p.name for p in AQUI.iterdir()))


if __name__ == "__main__":
    main()
