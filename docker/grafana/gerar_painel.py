"""Gera os painéis do Grafana em docker/grafana/dashboards/: "Support Nexus · API" e "Support Nexus · Cobertura da wiki".

O JSON é gerado, não editado à mão: aqui ficam as decisões (consultas, cores, unidades) em poucas linhas.
Rodar depois de mudar algo:  python docker/grafana/gerar_painel.py
Com o Prometheus no ar, confere também se toda consulta é PromQL válido:
                             python docker/grafana/gerar_painel.py --conferir http://localhost:9090

Cores: ordem fixa da paleta categórica validada (tema escuro do Grafana), cinza para o que não tem cor própria
(nunca as cores cíclicas do Grafana); verde/amarelo/vermelho só para estado, sempre com texto junto.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
SERIE = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"]  # categórica, ordem fixa
CINZA = "#898781"
BOM, ATENCAO, CRITICO = "#0ca30c", "#fab219", "#d03b3b"

# cada rota principal tem sempre a mesma cor, em qualquer painel
ROTAS = ["/api/menus/{menu_id}", "/api/modulos/{modulo}/diagrama", "/api/manuais/{codigo}", "/{caminho:path}",
         "/api/modulos/{modulo}/menus", "/api/modulos/{modulo}/catalogo", "/api/modulos/{modulo}/tabelas/{nome}"]
SEM_RUIDO = 'route!~"/api/saude|/metrics"'  # o healthcheck do Docker chama /api/saude a cada 30 s

_id = 0


def painel(tipo, titulo, x, y, w, h, alvos, descricao, defaults=None, overrides=None, options=None):
    global _id
    _id += 1
    return {"id": _id, "type": tipo, "title": titulo, "description": descricao, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [{"datasource": DS, "refId": chr(65 + i), **a} for i, a in enumerate(alvos)],
            "fieldConfig": {"defaults": defaults or {}, "overrides": overrides or []}, "options": options or {}}


def cor_fixa(nome, cor):
    return {"matcher": {"id": "byName", "options": nome}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": cor}}]}


def limites(*passos):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in passos]}


def estatistica(titulo, x, w, expr, descricao, unidade="none", cores=None, decimais=None, sem_dado="—", **extra):
    defaults = {"unit": unidade, "noValue": sem_dado, "color": {"mode": "thresholds"},
                "thresholds": cores or limites((None, "text"))}
    if decimais is not None:
        defaults["decimals"] = decimais
    defaults.update(extra.pop("defaults", {}))
    return painel("stat", titulo, x, 0, w, 4, [{"expr": expr, "instant": True, **extra.pop("alvo", {})}], descricao, defaults,
                  options={"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "value" if cores else "none",
                           "graphMode": "none", "textMode": extra.pop("texto", "value"), "justifyMode": "center"})


def linhas(titulo, x, y, w, h, alvos, descricao, unidade, overrides=None, sem_dado="Sem dados no período", **custom):
    defaults = {"unit": unidade, "noValue": sem_dado, "min": 0, "color": {"mode": "fixed", "fixedColor": CINZA},
                "custom": {"lineWidth": 2, "fillOpacity": 0, "showPoints": "never", "spanNulls": True, **custom}}
    return painel("timeseries", titulo, x, y, w, h, alvos, descricao, defaults, overrides,
                  options={"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                           "tooltip": {"mode": "multi", "sort": "desc"}})


cores_rotas = [cor_fixa(r, SERIE[i]) for i, r in enumerate(ROTAS)]

paineis = [
    # ---------- linha 1: números-chave ----------
    estatistica("API", 0, 5, 'up{job="nexus"}',
                "O Prometheus conseguiu ler /metrics na última coleta (a cada 15 s).", sem_dado="Sem dados",
                cores=limites((None, CRITICO), (1, BOM)),
                defaults={"mappings": [{"type": "value", "options": {"1": {"text": "No ar", "color": BOM},
                                                                      "0": {"text": "Fora do ar", "color": CRITICO}}}]}),
    estatistica("Requisições por segundo", 5, 5, "sum(rate(nexus_http_requests_total[5m]))",
                "Média dos últimos 5 minutos, todas as rotas (inclui o healthcheck do Docker, ~0,03/s).", "reqps", decimais=2),
    estatistica("Erros do servidor (5xx)", 10, 5,
                '(sum(rate(nexus_http_requests_total{status=~"5.."}[5m])) or vector(0)) / sum(rate(nexus_http_requests_total[5m]))',
                "Fração das respostas com status 5xx nos últimos 5 minutos. Verde < 1%, amarelo < 5%, vermelho a partir de 5% (alerta NexusErros5xx).",
                "percentunit", limites((None, BOM), (0.01, ATENCAO), (0.05, CRITICO)), decimais=1),
    estatistica("Tempo de resposta (p95)", 15, 5,
                f'histogram_quantile(0.95, sum by (le) (rate(nexus_http_request_duration_seconds_bucket{{{SEM_RUIDO},route!="/api/manuais/{{codigo}}/pdf"}}[5m])))',
                "95% das requisições respondem em até este tempo (sem o PDF, que tem painel próprio). Amarelo a partir de 0,5 s, vermelho a partir de 1 s (alerta NexusLento).",
                "s", limites((None, BOM), (0.5, ATENCAO), (1, CRITICO))),
    estatistica("Versão", 20, 4, "nexus_info", "Versão do Support Nexus em execução.", texto="name",
                alvo={"legendFormat": "{{version}}"}),

    # ---------- linha 2: tráfego ----------
    linhas("Requisições por segundo, por rota", 0, 4, 12, 9,
           [{"expr": f"topk(7, sum by (route) (rate(nexus_http_requests_total{{{SEM_RUIDO}}}[5m])))", "legendFormat": "{{route}}"}],
           "As rotas mais usadas. O rótulo é o modelo da rota ({menu_id}, {codigo}), não a URL. /{caminho:path} = interface e arquivos.",
           "reqps", cores_rotas),
    linhas("Respostas por classe de status", 12, 4, 12, 9,
           [{"expr": 'sum by (classe) (label_replace(rate(nexus_http_requests_total[5m]), "classe", "${1}xx", "status", "([0-9]).."))',
             "legendFormat": "{{classe}}"}],
           "2xx = sucesso, 4xx = pedido inválido ou inexistente (ex.: tela que não existe), 5xx = erro do servidor.",
           "reqps", [cor_fixa("2xx", SERIE[0]), cor_fixa("3xx", SERIE[2]), cor_fixa("4xx", ATENCAO), cor_fixa("5xx", CRITICO)]),

    # ---------- linha 3: tempo de resposta e PDF ----------
    linhas("Tempo de resposta por rota (p95)", 0, 13, 12, 9,
           [{"expr": f'histogram_quantile(0.95, sum by (le, route) (rate(nexus_http_request_duration_seconds_bucket{{{SEM_RUIDO},route!="/api/manuais/{{codigo}}/pdf"}}[5m])))',
             "legendFormat": "{{route}}"}],
           "Para achar a rota lenta. A linha some quando a rota não teve uso no período.", "s", cores_rotas),
    linhas("PDF: tempo de geração", 12, 13, 8, 9,
           [{"expr": "histogram_quantile(0.5, sum by (le) (rate(nexus_pdf_generation_duration_seconds_bucket[15m])))", "legendFormat": "mediana (p50)"},
            {"expr": "histogram_quantile(0.95, sum by (le) (rate(nexus_pdf_generation_duration_seconds_bucket[15m])))", "legendFormat": "p95"}],
           "Tempo para o Chromium abrir a página de impressão e gerar o A4. Só tem dados depois que alguém exporta um PDF.",
           "s", [cor_fixa("mediana (p50)", SERIE[0]), cor_fixa("p95", SERIE[1])], sem_dado="Nenhum PDF gerado no período"),
    painel("stat", "Falhas de PDF (24 h)", 20, 13, 4, 9,
           [{"expr": "increase(nexus_pdf_generation_failures_total[24h])", "instant": True}],
           "PDFs que não puderam ser gerados nas últimas 24 h (alerta NexusPdfFalhando).",
           {"unit": "none", "decimals": 0, "noValue": "0", "color": {"mode": "thresholds"}, "thresholds": limites((None, BOM), (1, CRITICO))},
           options={"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "value", "graphMode": "none", "textMode": "value"}),

    # ---------- linha 4: recursos do contêiner ----------
    linhas("Memória da API", 0, 22, 12, 8,
           [{"expr": 'process_resident_memory_bytes{job="nexus"}', "legendFormat": "memória residente"}],
           "Memória do processo da API (sem o Chromium do PDF, que é um processo à parte). O limite do contêiner é 1 GiB (mem_limit no docker-compose.yml).",
           "bytes", [cor_fixa("memória residente", SERIE[0])]),
    linhas("CPU da API", 12, 22, 12, 8,
           [{"expr": 'rate(process_cpu_seconds_total{job="nexus"}[5m])', "legendFormat": "CPU"}],
           "Fração de um núcleo usada pelo processo da API (1 = 100% de um núcleo).", "percentunit", [cor_fixa("CPU", SERIE[0])]),
]


def barras(titulo, x, y, w, h, alvos, descricao, unidade="none", cor=SERIE[0], overrides=None, sem_dado="Sem dados",
           nome="left", **defaults):
    """Barras horizontais. Uma cor só quando é a mesma medida por categoria; cores próprias só via overrides.
    nome="top" põe o rótulo acima da barra (nomes longos, como os menus, não são cortados)."""
    d = {"unit": unidade, "noValue": sem_dado, "min": 0, "color": {"mode": "fixed", "fixedColor": cor}, **defaults}
    return painel("bargauge", titulo, x, y, w, h, [{"instant": True, **a} for a in alvos], descricao, d, overrides,
                  options={"orientation": "horizontal", "displayMode": "basic", "showUnfilled": True, "valueMode": "text",
                           "namePlacement": nome, "sizing": "auto", "minVizHeight": 16, "maxVizHeight": 26,
                           "reduceOptions": {"calcs": ["lastNotNull"], "values": False}})


def cor_e_nome(nome, cor, exibir):
    o = cor_fixa(nome, cor)
    o["properties"].append({"id": "displayName", "value": exibir})
    return o


paineis_api = paineis

# ---------------------------------------------------------------------------------------------------------------
# Painel 2 · Cobertura da wiki (métricas nexus_wiki_*, calculadas no banco a cada coleta; ver servicos/cobertura.py)
# ---------------------------------------------------------------------------------------------------------------
TELAS, COM_MANUAL = "sum(nexus_wiki_screens)", "sum(nexus_wiki_screens_with_manual)"
DECIDIDAS = 'sum(nexus_wiki_relations{state!="sugerida"}) / sum(nexus_wiki_relations)'
ESTADOS = [("confirmada", SERIE[0]), ("documentada", SERIE[2]), ("sugerida", SERIE[3]), ("descartada", CINZA)]
TIPOS = [("relacao", "Relações"), ("vinculo", "Vínculos"), ("manual", "Manuais")]

paineis_cobertura = [
    # ---------- linha 1: números-chave ----------
    estatistica("Telas com manual", 0, 5, f"{COM_MANUAL} / {TELAS}",
                "Fração das telas (itens de menu sem subitens) com pelo menos um manual.", "percentunit", decimais=0),
    estatistica("Telas sem manual", 5, 4, f"{TELAS} - {COM_MANUAL}",
                "Telas que ainda não têm nenhum manual: o tamanho da fila de documentação.", decimais=0),
    estatistica("Vínculos de tabela confirmados", 9, 5, "sum(nexus_wiki_screens_tables_confirmed) / sum(nexus_wiki_screens)",
                "Fração das telas cujas tabelas a equipe já confirmou (nenhum vínculo só sugerido).", "percentunit", decimais=0),
    estatistica("Relações a validar", 14, 5, 'sum(nexus_wiki_relations{state="sugerida"})',
                "Relações inferidas pelo nome das colunas que ninguém validou nem descartou ainda.", decimais=0),
    estatistica("Contribuições (7 dias)", 19, 5, "sum(nexus_wiki_contributions_7d) or vector(0)",
                "Relações validadas ou descartadas, vínculos confirmados e manuais salvos pela interface nos últimos 7 dias.", decimais=0),

    # ---------- linha 2: onde está e onde falta ----------
    barras("Cobertura de manuais por menu", 0, 4, 12, 12,
           [{"expr": "sort_desc(sum by (menu) (nexus_wiki_screens_with_manual) / sum by (menu) (nexus_wiki_screens))", "legendFormat": "{{menu}}"}],
           "Fração das telas de cada menu principal que já têm manual.", "percentunit", nome="top", max=1, decimals=0),
    barras("Telas sem manual, por menu", 12, 4, 12, 12,
           [{"expr": "sort_desc(sum by (menu) (nexus_wiki_screens) - sum by (menu) (nexus_wiki_screens_with_manual))", "legendFormat": "{{menu}}"}],
           "Onde começar: quantas telas de cada menu ainda não têm nenhum manual.", cor=SERIE[1], nome="top", decimals=0),

    # ---------- linha 3: evolução e relações ----------
    linhas("Cobertura ao longo do tempo", 0, 16, 16, 9,
           [{"expr": f"{COM_MANUAL} / {TELAS}", "legendFormat": "telas com manual"},
            {"expr": "sum(nexus_wiki_screens_tables_confirmed) / sum(nexus_wiki_screens)", "legendFormat": "vínculos confirmados"},
            {"expr": DECIDIDAS, "legendFormat": "relações decididas"}],
           "Evolução da documentação. O Prometheus guarda 15 dias: para comparar períodos maiores, aumente a retenção (docs/monitoramento.md).",
           "percentunit", [cor_fixa("telas com manual", SERIE[0]), cor_fixa("vínculos confirmados", SERIE[1]), cor_fixa("relações decididas", SERIE[2])],
           sem_dado="Sem histórico ainda"),
    # uma consulta por estado: a ordem das consultas é a ordem das barras (o ciclo de vida de uma relação)
    barras("Relações por estado", 16, 16, 8, 9,
           [{"expr": f'sum(nexus_wiki_relations{{state="{e}"}}) or vector(0)', "legendFormat": e} for e, _ in ESTADOS],
           "Confirmada = FK no banco; documentada = validada pela equipe; sugerida = inferida, falta validar; descartada = a equipe rejeitou.",
           overrides=[cor_fixa(e, c) for e, c in ESTADOS], decimals=0),

    # ---------- linha 4: quem está contribuindo ----------
    barras("Contribuições por pessoa (7 dias)", 0, 25, 12, 8,
           [{"expr": "sort_desc(sum by (author) (nexus_wiki_contributions_7d))", "legendFormat": "{{author}}"}],
           'Nome informado no campo "Seu nome" do topo da interface. (sem nome) = alteração feita sem preencher o nome.',
           decimals=0, sem_dado="Nenhuma contribuição nos últimos 7 dias"),
    barras("Contribuições por tipo (7 dias)", 12, 25, 12, 8,
           [{"expr": f'sum(nexus_wiki_contributions_7d{{kind="{k}"}}) or vector(0)', "legendFormat": k} for k, _ in TIPOS],
           "Relações = validadas ou descartadas; Vínculos = tabelas confirmadas numa tela; Manuais = criados ou editados pela interface.",
           overrides=[cor_e_nome(k, SERIE[i], nome) for i, (k, nome) in enumerate(TIPOS)],
           decimals=0, sem_dado="Nenhuma contribuição nos últimos 7 dias"),
]

LINKS = [{"title": "Painéis do Support Nexus", "type": "dashboards", "tags": ["support-nexus"], "asDropdown": False, "includeVars": False},
         {"title": "Abrir o Support Nexus", "type": "link", "url": "http://localhost:8010", "targetBlank": True, "icon": "external link"}]


def dashboard(uid, titulo, descricao, paineis_, desde, refresh):
    return {"uid": uid, "title": titulo, "tags": ["support-nexus"], "editable": True, "description": descricao,
            "schemaVersion": 39, "version": 1, "refresh": refresh, "time": {"from": desde, "to": "now"},
            "timezone": "browser", "graphTooltip": 1, "links": LINKS, "panels": paineis_}


PAINEIS = {
    "support-nexus.json": dashboard("support-nexus", "Support Nexus · API",
                                    "Saúde técnica da API do Support Nexus (métricas de /metrics coletadas pelo Prometheus).",
                                    paineis_api, "now-1h", "15s"),
    "support-nexus-cobertura.json": dashboard("support-nexus-cobertura", "Support Nexus · Cobertura da wiki",
                                              "Quanto do sistema está documentado e quem está contribuindo (métricas nexus_wiki_*).",
                                              paineis_cobertura, "now-7d", "1m"),
}

pasta = Path(__file__).parent / "dashboards"
pasta.mkdir(exist_ok=True)
for arquivo, d in PAINEIS.items():
    (pasta / arquivo).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{pasta / arquivo} · {len(d['panels'])} painéis")


def conferir(prometheus: str) -> int:
    """Manda cada consulta ao Prometheus: erro de sintaxe aparece aqui, não como um painel vermelho no Grafana."""
    erros = 0
    for d in PAINEIS.values():
        print(d["title"])
        for p in d["panels"]:
            for t in p["targets"]:
                url = f"{prometheus.rstrip('/')}/api/v1/query?" + urllib.parse.urlencode({"query": t["expr"]})
                try:
                    n = len(json.load(urllib.request.urlopen(url, timeout=10))["data"]["result"])
                    print(f"  ok    {n:2} série(s)  {p['title']}")
                except urllib.error.HTTPError as e:
                    erros += 1
                    print(f"  ERRO  {p['title']}: {json.load(e).get('error')}")
    return erros


if len(sys.argv) == 3 and sys.argv[1] == "--conferir":
    sys.exit(1 if conferir(sys.argv[2]) else 0)
