"""Rodapé "Manual alterado em DD/MM/AAAA às HH:MM": só para manuais salvos pelo editor, na hora de Brasília."""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app import pdf, seed
from app.rotas import manuais as rotas

MENU = "pdv.caixa.fechamento-de-caixa"
CORPO = {"titulo": "Reabrir caixa", "subtitulo": "", "modulo": "pdv", "menu": MENU, "tipo": "chamado",
         "secoes": [{"titulo": "Procedimento", "blocos": [{"tipo": "passo", "texto": "Acesse **Caixa > Reabrir**."}]}]}


def salvar(cliente, codigo=None):
    url, metodo = (f"/api/manuais/{codigo}", cliente.put) if codigo else ("/api/manuais", cliente.post)
    return metodo(url, json=CORPO, headers={"X-Usuario": quote("Ana")})


def test_salvar_grava_a_hora_de_brasilia(cliente, banco):
    antes = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None, microsecond=0)
    codigo = salvar(cliente).json()["codigo"]
    alterado = cliente.get(f"/api/manuais/{codigo}").json()["alterado_em"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", alterado)
    # independe do fuso do servidor: comparado com o relógio de Brasília, não com o local
    assert timedelta(0) <= datetime.fromisoformat(alterado) - antes < timedelta(minutes=2)
    # vai também no JSON do manual, para sobreviver a um novo seed
    assert json.loads((banco / "manuais" / f"{codigo}.json").read_text(encoding="utf-8"))["alterado_em"] == alterado


def test_cada_edicao_atualiza_a_data(cliente, banco, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "agora_brasilia", lambda: "2026-10-27 08:05:00")
    codigo = salvar(cliente).json()["codigo"]
    monkeypatch.setattr(config, "agora_brasilia", lambda: "2026-10-28 17:42:09")
    salvar(cliente, codigo)
    assert cliente.get(f"/api/manuais/{codigo}").json()["alterado_em"] == "2026-10-28 17:42:09"


def test_manual_que_ninguem_alterou_nao_tem_data(cliente):
    assert cliente.get("/api/manuais/DEMO.001").json()["alterado_em"] is None


def test_manual_editado_antes_da_mudanca_usa_a_data_da_ultima_gravacao(banco):
    (banco / "manuais").mkdir(exist_ok=True)
    (banco / "manuais" / "PDV.900.json").write_text(json.dumps({
        "editado": True, "codigo": "PDV.900", "titulo": "Antigo", "modulo": "pdv", "menu": MENU,
        "atualizado_em": "2026-10-20 14:30:00", "secoes": [{"titulo": "A", "blocos": [{"tipo": "texto", "texto": "x"}]}],
    }), encoding="utf-8")
    seed.main()
    from app import db
    con = db.conectar()
    assert con.execute("SELECT alterado_em FROM manuais WHERE codigo = 'PDV.900'").fetchone()[0] == "2026-10-20 14:30:00"
    con.close()


def test_texto_do_rodape():
    assert pdf.texto_rodape("2026-10-27 08:05:59") == "Manual alterado em 27/10/2026 às 08:05"
    assert pdf.texto_rodape(None) == "Documento gerado pelo Support Nexus"
    assert "Manual alterado em 27/10/2026 às 08:05" in pdf.rodape("2026-10-27 08:05:59")


def test_pdf_leva_a_data_de_alteracao(cliente, banco, monkeypatch):
    recebido = {}
    monkeypatch.setattr(rotas.pdf, "gerar", lambda codigo, alterado_em=None: recebido.update(c=codigo, a=alterado_em) or b"%PDF-")
    codigo = salvar(cliente).json()["codigo"]
    assert cliente.get(f"/api/manuais/{codigo}/pdf").status_code == 200
    assert recebido["c"] == codigo and recebido["a"] == cliente.get(f"/api/manuais/{codigo}").json()["alterado_em"]
