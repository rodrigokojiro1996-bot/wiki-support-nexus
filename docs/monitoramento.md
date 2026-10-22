# Monitoramento: Prometheus e Grafana

Como o Support Nexus é monitorado, o que cada métrica significa e o porquê de cada escolha. Para subir os
contêineres, veja [docker.md](docker.md).

1. [Visão geral](#1-visão-geral)
2. [Conceitos](#2-conceitos)
3. [Subir e acessar](#3-subir-e-acessar)
4. [As métricas da API](#4-as-métricas-da-api)
5. [O painel do Grafana](#5-o-painel-do-grafana)
6. [Alertas](#6-alertas)
7. [Consultas úteis (PromQL)](#7-consultas-úteis-promql)
8. [Segurança](#8-segurança)
9. [Operação](#9-operação)
10. [Problemas comuns](#10-problemas-comuns)


## 1. Visão geral

```
  ┌──────────────┐  GET /metrics a cada 15 s   ┌──────────────┐  consultas PromQL   ┌──────────────┐
  │    nexus     │ <────────────────────────── │  prometheus  │ <────────────────── │   grafana    │
  │ API :8010    │                              │ :9090        │                     │ :3000        │
  │ conta e mede │                              │ guarda séries│                     │ desenha o    │
  │ cada pedido  │                              │ avalia regras│                     │ painel       │
  └──────────────┘                              └──────────────┘                     └──────────────┘
     volume nexus-dados                          volume prometheus-dados              volume grafana-dados
```

- A **API** só conta e mede (biblioteca oficial `prometheus-client`) e publica os números em `/metrics`.
- O **Prometheus** busca esses números (*pull*), guarda cada um com data e hora (banco de séries temporais) e
  avalia as regras de alerta.
- O **Grafana** não guarda métricas: ele consulta o Prometheus e desenha.

Tudo é configurado por arquivos versionados, sem cliques: `docker/prometheus/` (coleta e alertas) e
`docker/grafana/` (fonte de dados e painel). Apagar os volumes e subir de novo recria tudo igual.


## 2. Conceitos

| Termo | O que é |
|---|---|
| **Série** | Uma métrica com um conjunto de rótulos, ex.: `nexus_http_requests_total{method="GET", route="/api/modulos", status="200"}` |
| **Contador** (*counter*) | Só sobe (ou zera quando o processo reinicia). Ex.: total de requisições. Sozinho diz pouco; o que interessa é a **taxa** |
| **Histograma** | Conta as ocorrências por faixa (*bucket*) de valor: quantas requisições levaram até 5 ms, até 10 ms, … Dele sai o percentil |
| **Gauge** | Sobe e desce. Ex.: memória do processo |
| **`rate(x[5m])`** | Aumento médio por segundo do contador nos últimos 5 minutos |
| **p95** | 95% das requisições levaram até este tempo. Mostra a experiência de quase todos, sem ser puxado por um caso isolado como a média |
| **Alvo** (*target*) | Endereço que o Prometheus coleta. `up` = 1 se a última coleta deu certo |
| **Cardinalidade** | Quantas séries diferentes uma métrica gera. Cada valor de rótulo novo é uma série nova guardada |

**Por que o rótulo é o modelo da rota.** `route="/api/menus/{menu_id}"` e não `/api/menus/pdv.caixa.fechamento-de-caixa`.
Com a URL real, cada tela e cada manual criariam uma série própria, e com um ERP real o Prometheus guardaria
milhares de séries inúteis (a "explosão de cardinalidade", o erro mais comum de métricas). O middleware lê a rota
que o FastAPI escolheu (`scope["route"].path`). Pedidos que não casam com rota nenhuma usam `(sem rota)`.


## 3. Subir e acessar

1. Copie `.env.example` para `.env` e troque `GRAFANA_SENHA`. Sem isso o compose para com a mensagem
   "Defina GRAFANA_SENHA…", de propósito: nada de `admin/admin`.
2. `docker compose up -d --build`, e `docker compose ps` até os três estarem `(healthy)`. O Grafana só sobe
   depois que o Prometheus está pronto (`depends_on … service_healthy`).

| Endereço | O que tem |
|---|---|
| <http://localhost:3000> | Grafana: entra com `admin` e a senha do `.env`; o painel "Support Nexus · API" é a página inicial |
| <http://localhost:9090/targets> | Prometheus: alvos e a saúde de cada coleta |
| <http://localhost:9090/alerts> | Prometheus: as regras de alerta e o estado de cada uma |
| <http://localhost:9090/query> | Prometheus: consultas PromQL avulsas |
| <http://localhost:8010/metrics> | As métricas cruas da API, no formato texto do Prometheus |


## 4. As métricas da API

Nomes no padrão do Prometheus: inglês, `snake_case`, unidade no nome (`_seconds`), `_total` nos contadores. Assim
consultas e painéis prontos da comunidade funcionam sem adaptação.

| Métrica | Tipo | Rótulos | O que mede |
|---|---|---|---|
| `nexus_http_requests_total` | contador | `method`, `route`, `status` | requisições atendidas |
| `nexus_http_request_duration_seconds` | histograma | `method`, `route` | tempo de resposta (faixas de 5 ms a 10 s) |
| `nexus_pdf_generation_duration_seconds` | histograma | — | tempo para gerar um PDF (faixas de 0,5 s a 30 s) |
| `nexus_pdf_generation_failures_total` | contador | — | PDFs que falharam (o 503 da API) |
| `nexus_info` | info | `version` | versão em execução |
| `process_resident_memory_bytes`, `process_cpu_seconds_total`, … | gauge/contador | — | do próprio `prometheus-client` (só no Linux) |

A coleta do Prometheus (`/metrics`) não entra nas métricas, para não poluir os números. O healthcheck do Docker
(`/api/saude` a cada 30 s) entra no total, mas os painéis por rota o deixam de fora.

Código: `backend/app/metricas.py` (definições e middleware) e `backend/app/rotas/metricas.py` (rota `/metrics`).
Testes: `backend/tests/test_metricas.py`.


## 5. O painel do Grafana

O JSON do painel é **gerado** por `docker/grafana/gerar_painel.py`: consultas, cores e unidades ficam em poucas
linhas de Python em vez de centenas de linhas de JSON. O Grafana relê o arquivo a cada 30 s.

```powershell
python docker\grafana\gerar_painel.py                                   # gera o JSON
python docker\grafana\gerar_painel.py --conferir http://localhost:9090  # e confere cada consulta no Prometheus
```
O painel provisionado não pode ser salvo pela tela (`allowUiUpdates: false`): a fonte da verdade é o arquivo.
Para experimentar, use **Salvar como** e crie uma cópia sua.

| Linha | Painéis | Para responder |
|---|---|---|
| 1 | API · Requisições por segundo · Erros 5xx · Tempo de resposta p95 · Versão | Está tudo bem agora? |
| 2 | Requisições por rota · Respostas por classe de status | O que estão usando? Há erros? |
| 3 | Tempo de resposta por rota (p95) · PDF: tempo de geração · Falhas de PDF (24 h) | O que está lento? O PDF funciona? |
| 4 | Memória da API · CPU da API | O contêiner está folgado? |

Escolhas de visualização:
- Números-chave em blocos de destaque, não em gráficos: a pergunta é "quanto está agora".
- Uma escala por gráfico: medidas de natureza diferente (requisições, tempo, memória) nunca dividem o mesmo eixo.
- Cada rota principal tem **sempre a mesma cor** em todos os painéis (ordem fixa de uma paleta testada para
  daltonismo); rotas secundárias ficam em cinza. Nada das cores cíclicas do Grafana, que trocam de cor quando o
  conjunto de séries muda.
- Verde, amarelo e vermelho só para estado (no ar, atenção, erro), sempre com texto ou limite junto, nunca como
  "a cor da série 3".
- Cada painel tem uma descrição (o ícone ⓘ) explicando o que mede e qual é o limite.


## 6. Alertas

Regras em `docker/prometheus/alertas.yml`, avaliadas a cada 15 s. Estados: *inactive* (tudo bem) → *pending* (a
condição é verdadeira, esperando o `for`) → *firing* (disparado) → volta a *inactive* quando a condição some.

| Alerta | Condição | Espera (`for`) | Severidade |
|---|---|---|---|
| `NexusForaDoAr` | `up{job="nexus"} == 0` | 1 min | critical |
| `NexusErros5xx` | mais de 5% das respostas são 5xx | 5 min | warning |
| `NexusLento` | p95 acima de 1 s (sem o PDF) | 10 min | warning |
| `NexusPdfFalhando` | alguma falha de PDF nos últimos 15 min | — | warning |

O `for` evita alarme por um pico isolado ou por um reinício rápido. Medido nesta máquina, parando a API:

| Tempo | O que aconteceu |
|---|---|
| 0 s | `docker compose stop nexus` |
| 10 s | coleta falha, `up` = 0 |
| 31 s | `NexusForaDoAr` *pending* |
| 92 s | `NexusForaDoAr` **firing** |
| 92 s | `docker compose start nexus` |
| 138 s | resolvido (*inactive*) |

**As regras têm testes.** `docker/prometheus/alertas.test.yml` simula séries no tempo e confere quando cada alerta
dispara e quando não:
```powershell
docker compose run --rm --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose run --rm -w /etc/prometheus --entrypoint promtool prometheus test rules alertas.test.yml
```

**Avisar alguém** (e-mail, Teams, Slack) exige um Alertmanager, que ainda não faz parte deste compose. Hoje os
alertas ficam visíveis no Prometheus.


## 7. Consultas úteis (PromQL)

Para colar em <http://localhost:9090/query> ou no Explorar do Grafana:

```promql
# requisições por segundo, por rota
sum by (route) (rate(nexus_http_requests_total[5m]))

# fração de erros 5xx
sum(rate(nexus_http_requests_total{status=~"5.."}[5m])) / sum(rate(nexus_http_requests_total[5m]))

# p95 do tempo de resposta por rota
histogram_quantile(0.95, sum by (le, route) (rate(nexus_http_request_duration_seconds_bucket[5m])))

# quantos PDFs foram gerados na última hora
increase(nexus_pdf_generation_duration_seconds_count[1h])

# as 5 rotas mais lentas agora
topk(5, histogram_quantile(0.95, sum by (le, route) (rate(nexus_http_request_duration_seconds_bucket[5m]))))
```

**Pegadinha dos contadores com rótulos.** Uma combinação nova de rótulos (ex.: a primeira vez que uma rota dá
404) nasce já valendo 1, e o `rate()` só enxerga *aumentos entre duas coletas*. Essa primeira ocorrência não
aparece nas taxas; da segunda em diante, sim. Para eventos raros, prefira olhar o contador cru ou `increase()` em
janelas longas.


## 8. Segurança

- As três portas ficam só em `127.0.0.1`. Abrir para a rede exige login na API (ainda pendente) e é uma decisão
  consciente.
- `/metrics` não expõe dados de clientes, só contagens e tempos, mas mostra a estrutura das rotas. Se a API for
  aberta na rede, restrinja `/metrics` (o Prometheus coleta pela rede interna do compose, não precisa da porta
  publicada).
- Senha do Grafana no `.env` (fora do git e fora da imagem), obrigatória; cadastro de usuários desligado.
- Grafana sem telemetria e sem consultas a servidores externos (`GF_ANALYTICS_*`, `GF_NEWS_*`).
- Configurações montadas somente leitura (`:ro`); as imagens do Prometheus e do Grafana já rodam sem root
  (`nobody` e `grafana`), travadas por versão e digest como as da aplicação.


## 9. Operação

| Para… | Como |
|---|---|
| guardar menos ou mais histórico | `--storage.tsdb.retention.time` (15 d) e `.size` (1 GB) no compose |
| trocar a senha do Grafana | `docker compose exec grafana grafana cli admin reset-admin-password <nova>` |
| aplicar uma mudança em `alertas.yml` ou `prometheus.yml` | `docker compose restart prometheus` |
| aplicar uma mudança no painel | gerar o JSON; o Grafana relê em até 30 s |
| zerar o histórico de métricas | `docker compose down` e `docker volume rm support-nexus_prometheus-dados` |

> `GRAFANA_SENHA` só vale na **primeira** subida, quando o Grafana cria o banco dele no volume. Mudar o `.env`
> depois não troca a senha: use o `reset-admin-password` acima.


## 10. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Defina GRAFANA_SENHA no arquivo .env` | `.env` ausente | Copie `.env.example` para `.env` |
| Painel "Sem dados no período" logo depois de subir | `rate()` precisa de pelo menos duas coletas (15 s cada) com aumento | Espere 1 a 2 minutos e use a API |
| Alvo `nexus` com `down` em `/targets` | API parada ou reiniciando | `docker compose ps`, `docker compose logs nexus` |
| Painel com triângulo vermelho | Consulta PromQL inválida | `gerar_painel.py --conferir http://localhost:9090` mostra qual e por quê |
| CPU e memória vazias | `process_*` só existem no Linux | Normal fora do Docker (`iniciar.ps1` no Windows) |
| Senha do `.env` não funciona | O Grafana já tinha sido criado com outra | [Operação](#9-operação): `reset-admin-password` |
