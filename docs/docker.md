# Support Nexus com Docker

Como rodar o Support Nexus em um contêiner, e o porquê de cada escolha. Para a arquitetura da aplicação em si,
veja [arquitetura.md](arquitetura.md); para o Prometheus e o Grafana, que sobem no mesmo compose,
[monitoramento.md](monitoramento.md); para o servidor na internet, [oracle-cloud.md](oracle-cloud.md).

1. [Conceitos em 1 minuto](#1-conceitos-em-1-minuto)
2. [Arquivos](#2-arquivos)
3. [Instalar o Docker no Windows](#3-instalar-o-docker-no-windows)
4. [Subir, acompanhar e parar](#4-subir-acompanhar-e-parar)
5. [Dados: volume, backup e restauração](#5-dados-volume-backup-e-restauração)
6. [Usar com um banco real](#6-usar-com-um-banco-real)
7. [Atualizar para uma versão nova](#7-atualizar-para-uma-versão-nova)
8. [Segurança](#8-segurança)
9. [Problemas comuns](#9-problemas-comuns)


## 1. Conceitos em 1 minuto

| Termo | O que é | No Support Nexus |
|---|---|---|
| **Imagem** | Pacote somente leitura com o sistema operacional mínimo, as dependências e a aplicação. Montada a partir do `Dockerfile`. | `support-nexus:local`: Python 3.14, FastAPI, Chromium e o build da interface |
| **Contêiner** | Uma imagem em execução, isolada do resto da máquina. Pode ser apagado e recriado a qualquer momento. | o processo da API na porta 8010 |
| **Volume** | Pasta gerenciada pelo Docker que fica **fora** do contêiner e sobrevive quando ele é recriado. | `nexus-dados`: o SQLite, os manuais e os prints |
| **Porta publicada** | Ligação entre uma porta da sua máquina e uma porta do contêiner. | `127.0.0.1:8010` → `8010` |
| **Compose** | Arquivo que descreve como rodar um ou mais contêineres (portas, volumes, limites). | `docker-compose.yml` |
| **Healthcheck** | Comando que o Docker roda de tempos em tempos para saber se a aplicação está respondendo. | `GET /api/saude` a cada 30 s |

A ideia central: **a imagem é descartável e reproduzível; os dados ficam no volume.** Por isso atualizar é "montar
imagem nova e recriar o contêiner", sem medo de perder manuais.


## 2. Arquivos

| Arquivo | Papel |
|---|---|
| `Dockerfile` | Receita da imagem, em duas etapas |
| `docker-compose.yml` | Como o contêiner roda nesta máquina |
| `docker/entrypoint.sh` | O que acontece quando o contêiner sobe |
| `.dockerignore` | O que não entra no build |
| `.gitattributes` | Garante quebra de linha LF nos arquivos lidos pelo Linux |

### 2.1 `Dockerfile`: duas etapas (*multi-stage build*)

```
 etapa "frontend"  node:22 ── npm ci ── npm run build ──┐
                                                         │ só frontend/dist
 etapa "app"       python:3.14 ── pip install ── Chromium ┴── código da API ── usuário nexus
```

- **Por que duas etapas.** O Node só é preciso para compilar a interface. A imagem final recebe apenas o
  resultado (`dist/`), sem Node, sem `node_modules` e sem o código-fonte do frontend: fica menor e com menos
  software que possa ter falha de segurança.
- **Imagens base travadas por versão e digest** (`python:3.14.9-slim-bookworm@sha256:…`). A tag sozinha pode ser
  republicada com outro conteúdo; o digest é a impressão digital daquela imagem exata. O build de hoje e o de
  daqui a um ano partem da mesma base. Para atualizar, troque versão e digest juntos e rode os testes.
- **Variante `slim`.** Debian mínimo: centenas de MB a menos que a imagem completa.
- **Dependências antes do código.** O Docker guarda cada instrução como uma camada em cache. Copiando primeiro só
  `package-lock.json` / `requirements.txt`, a instalação (a parte demorada) só roda de novo quando as
  dependências mudam; mudar o código refaz apenas as últimas camadas.
- **`npm ci` em vez de `npm install`.** Instala exatamente o que está no `package-lock.json` e falha se ele estiver
  desatualizado: o build nunca "escolhe" versões sozinho.
- **Só `requirements.txt`.** A imagem leva só a API. O importador de documentos e os testes ficam de fora.
- **Chromium do Playwright no lugar do Edge.** No Linux não há Edge; `NEXUS_PDF_CANAL=chromium` faz o PDF usar o
  Chromium que `playwright install --with-deps --no-shell chromium` instala com as bibliotecas de sistema
  necessárias (inclusive a fonte de emoji). O `--no-shell` pula o "headless shell", um segundo navegador que o
  canal `chromium` não usa: 273 MB a menos (imagem de 1,9 GB para 1,5 GB).
- **Fontes.** A interface leva Inter e JetBrains Mono no próprio build (pacotes `@fontsource-variable`), sem
  depender do Google Fonts. O manual usa Segoe UI e Consolas, que são da Microsoft e não existem no Linux: no
  contêiner o PDF sai com as equivalentes abertas Liberation Sans e Liberation Mono (mesmas medidas). O gerador
  espera `document.fonts.ready` antes de imprimir.
- **Limpeza do `apt` no mesmo `RUN`.** Cada `RUN` vira uma camada; apagar a lista de pacotes num `RUN` seguinte não
  diminui a imagem, porque ela já ficou gravada na camada anterior.
- **Usuário sem privilégios (`nexus`, uid 10001).** Se alguém explorar uma falha da aplicação, não é root dentro
  do contêiner.
- **`HEALTHCHECK` com Python.** A imagem slim não tem `curl`; instalar só para isso aumentaria a imagem.

### 2.2 `docker/entrypoint.sh`

1. `python -m app.seed`: aplica as migrações que faltam e carrega catálogo, menus e manuais. Roda a cada subida
   porque é idempotente: não duplica nada e preserva validações, vínculos e manuais da equipe.
2. `exec python -m uvicorn … --host 0.0.0.0`: dentro do contêiner a API escuta em todas as interfaces; quem
   decide o que fica acessível de fora é o mapeamento de portas do compose. O `exec` faz o uvicorn substituir o
   script e receber direto o sinal do `docker stop`, encerrando com calma.

### 2.3 `docker-compose.yml`

| Opção | Por quê |
|---|---|
| `ports: "127.0.0.1:8010:8010"` | Só esta máquina acessa. Ainda não há login (ver [Segurança](#8-segurança)). |
| `volumes: nexus-dados:/app/backend/dados` | Banco, manuais e prints sobrevivem a `down` e a uma imagem nova. |
| `shm_size: "256m"` | O Chromium usa memória compartilhada; com os 64 MB padrão do Docker, PDFs grandes falham. |
| `mem_limit: 1g` | Um vazamento de memória não derruba a máquina inteira. |
| `restart: unless-stopped` | Volta sozinho se cair ou se o Windows reiniciar; só não volta se você parou. |

Na própria imagem: o `tini` é o PID 1 e recolhe os processos do Chromium que terminam (evita zumbis), e o
Chromium do PDF roda com `--disable-dev-shm-usage`. Por isso a imagem funciona também num `docker run` simples,
sem as opções do compose (seção 10).

### 2.4 `.dockerignore` e `.gitattributes`

- O `.dockerignore` deixa de fora `.venv`, `node_modules` (velocidade) e `dados/`, `.env`, `segredos.txt`,
  `modulos.json`, `coletor/saida` (segurança): nada real vai parar dentro de uma imagem que pode ser compartilhada.
- O `.gitattributes` força LF em `*.sh`, `Dockerfile` e no compose. O Git do Windows converte para CRLF, e um
  script com CRLF falha no Linux com `bad interpreter` ou `set: illegal option -`.


## 3. Instalar o Docker no Windows

O Docker Desktop no Windows 11 Home roda sobre o **WSL2** (um Linux leve dentro do Windows). Requisitos: CPU com
virtualização ligada na BIOS (nesta máquina já está: i5-9600KF, `VirtualizationFirmwareEnabled = True`), 8 GB de
RAM ou mais e uns 10 GB livres em disco.

1. **Ativar o WSL2.** PowerShell **como administrador**:
   ```powershell
   wsl --install --no-distribution
   ```
   Isso liga os recursos "Subsistema do Windows para Linux" e "Plataforma de Máquina Virtual". **Reinicie** o
   computador.
2. **Conferir:** `wsl --status` deve mostrar "Versão Padrão: 2" sem avisos.
3. **Instalar o Docker Desktop:** baixe em <https://www.docker.com/products/docker-desktop/> ou, no PowerShell,
   `winget install Docker.DockerDesktop`. Na instalação, deixe marcado **"Use WSL 2 instead of Hyper-V"**.
4. Abra o Docker Desktop uma vez e aceite os termos. O ícone da baleia na bandeja fica verde quando o motor está
   pronto.
5. **Conferir:** `docker version` mostra *Client* e *Server*; `docker run --rm hello-world` imprime a mensagem de
   boas-vindas.

> Uso comercial: o Docker Desktop é gratuito para uso pessoal, educação e empresas pequenas (menos de 250
> funcionários **e** menos de US$ 10 milhões de faturamento anual); acima disso exige assinatura. Para servidores
> Linux, o Docker Engine é livre.


## 4. Subir, acompanhar e parar

Na raiz do projeto (onde está o `docker-compose.yml`):

```powershell
docker compose up -d --build     # monta a imagem (a 1ª vez leva alguns minutos) e sobe em segundo plano
docker compose ps                # STATUS deve chegar a "Up … (healthy)" em até ~30 s
```

Abra <http://localhost:8010>.

Números desta máquina (i5-9600KF, 16 GB): primeiro build ~2,5 min (a camada do pip + Chromium leva ~90 s);
build depois de mudar só o código ~40 s (essa camada sai do cache); contêiner saudável ~7 s depois de subir.

| Para… | Comando |
|---|---|
| ver o log ao vivo | `docker compose logs -f` |
| ver se está saudável | `docker compose ps` ou `docker inspect --format "{{.State.Health.Status}}" support-nexus-nexus-1` |
| abrir um terminal dentro do contêiner | `docker compose exec nexus sh` |
| reiniciar | `docker compose restart` |
| parar (mantém o contêiner) | `docker compose stop` |
| parar e remover o contêiner (**os dados continuam no volume**) | `docker compose down` |
| ver o tamanho da imagem | `docker image ls support-nexus` |

> Não rode o `iniciar.ps1`/`iniciar-producao.ps1` e o contêiner ao mesmo tempo: todos usam a porta 8010.

### 4.1 Build atrás de antivírus ou proxy que inspeciona HTTPS

Alguns antivírus (Avast, AVG, Kaspersky, ESET…) e proxies corporativos abrem as conexões HTTPS para examiná-las e
as assinam com um certificado próprio. O Windows confia nesse certificado (o antivírus o instalou nele), mas o
Linux do build não, e recusa a conexão, corretamente:

```
SSLError(SSLCertVerificationError(... certificate verify failed: unable to get local issuer certificate))
ERROR: No matching distribution found for fastapi==0.159.1
```

Para saber se é isso, veja quem assina o certificado de um site, no PowerShell:
```powershell
$t = New-Object Net.Sockets.TcpClient('pypi.org', 443); $s = New-Object Net.Security.SslStream($t.GetStream(), $false, { $true })
$s.AuthenticateAsClient('pypi.org'); $c = New-Object Security.Cryptography.X509Certificates.X509Chain
[void]$c.Build($s.RemoteCertificate); $c.ChainElements | ForEach-Object { $_.Certificate.Subject }
```
Se a última linha for o antivírus (ex.: `Avast Web/Mail Shield Root`) em vez de uma autoridade pública
(GlobalSign, DigiCert, ISRG…), adicione exceções no antivírus para os sites que o build usa:

| Site | Usado por |
|---|---|
| `pypi.org`, `files.pythonhosted.org` | pip |
| `registry.npmjs.org` | npm |
| `deb.debian.org` | apt (bibliotecas do Chromium) |
| `cdn.playwright.dev`, `playwright.download.prss.microsoft.com` | download do Chromium |

No Avast: Menu → Configurações → Geral → Exceções → Adicionar exceção, no formato `https://pypi.org/*`. Rode o
teste acima de novo: a raiz tem que ser a autoridade pública antes de tentar o build. **Não** desligue a
verificação de certificado no build (`--trusted-host`, `strict-ssl false`): isso esconde o problema e abre a porta
para pacotes adulterados.

O contêiner em execução não precisa de internet (fontes e interface vão na imagem), então isso só afeta o build.


## 5. Dados: volume, backup e restauração

O volume chama-se `support-nexus_nexus-dados` (o compose prefixa o nome do projeto). Ele guarda `nexus.db`,
`manuais/` e `imagens/`. É independente da pasta `backend/dados` do Windows: o contêiner começa com o sistema de
exemplo, e o que for criado nele fica nele.

**Backup** (com o contêiner rodando):
```powershell
docker compose cp nexus:/app/backend/dados .\backup-dados
```

**Restauração:**
```powershell
docker compose cp .\backup-dados\. nexus:/app/backend/dados
docker compose exec -u root nexus chown -R nexus:nexus /app/backend/dados   # arquivos copiados chegam como root
docker compose restart
```

**Levar o que você fez no modo local** (`iniciar.ps1`) para o contêiner: o volume é independente da pasta
`backend\dados` do Windows. Com o contêiner rodando:
```powershell
docker compose cp backend\dados\. nexus:/app/backend/dados
docker compose exec -u root nexus chown -R nexus:nexus /app/backend/dados
docker compose restart
```

**Começar do zero** (apaga manuais e validações feitos no contêiner):
```powershell
docker compose down -v           # -v remove também o volume
```

> A pasta `backup-dados` contém dados reais: ela já está fora do contexto do build, mas **não a coloque no git**.


## 6. Usar com um banco real

O catálogo real e a lista de módulos ficam fora da imagem e entram por volume, **somente leitura** (`:ro`):

1. Gere os arquivos como no [README](../README.md#usar-com-um-banco-real): `coletor/saida/<banco>/catalogo.json`
   e `backend/modulos.json`.
2. No `docker-compose.yml`, descomente as duas linhas de volume do banco real.
3. `docker compose up -d`: o seed da subida importa o catálogo real.


## 7. Atualizar para uma versão nova

```powershell
git pull
docker compose up -d --build     # imagem nova; o contêiner é recriado; o volume é reaproveitado
```

Na subida, o seed aplica as migrações novas no banco do volume (ver *Migrações* em
[arquitetura.md](arquitetura.md#6-modelo-de-dados)). Faça um backup antes de atualizar.

Para atualizar as **imagens base** (correções de segurança do Debian, do Python ou do Node): troque versão e
digest no `Dockerfile`, rode `pytest -q` e `npm run build` localmente e depois `docker compose up -d --build`.


## 8. Segurança

- **Sem login, a porta fica só nesta máquina** (`127.0.0.1`). Trocar para `"8010:8010"` abre para a rede inteira,
  e qualquer pessoa que alcançar a porta pode criar e editar manuais e validar relações. Faça isso só depois do
  login, ou numa rede de confiança.
- A aplicação roda como usuário `nexus`, sem privilégios.
- Segredos e dados reais nunca entram na imagem (`.dockerignore`); o banco real entra por volume `:ro`.
- O cabeçalho `server` é desligado (`--no-server-header`): a resposta não anuncia o software do servidor.
- Imagens base travadas por digest: atualizá-las é uma decisão consciente, com os testes rodando.


## 9. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `docker: command not found` / `error during connect` | Docker Desktop fechado ou não instalado | Abra o Docker Desktop e espere a baleia ficar verde |
| `CERTIFICATE_VERIFY_FAILED` / `No matching distribution found` no build | Antivírus ou proxy inspecionando HTTPS | [Seção 4.1](#41-build-atrás-de-antivírus-ou-proxy-que-inspeciona-https) |
| PDF do contêiner com fonte diferente do Windows | Segoe UI e Consolas não existem no Linux | Esperado: sai com Liberation Sans e Liberation Mono ([2.1](#21-dockerfile-duas-etapas-multi-stage-build)) |
| `WSL 2 is not installed` / "Não há suporte para WSL2" | WSL2 ou "Plataforma de Máquina Virtual" desligados | [Seção 3](#3-instalar-o-docker-no-windows), passo 1, e reinicie |
| `Bind for 127.0.0.1:8010 failed: port is already allocated` | `iniciar.ps1` ou outro processo na 8010 | Feche o outro, ou troque o lado esquerdo da porta: `"127.0.0.1:8020:8010"` |
| `exec /usr/local/bin/nexus-entrypoint: no such file or directory` | `entrypoint.sh` com CRLF (Windows) | `git add --renormalize .` e build de novo; confira o `.gitattributes` |
| Status `unhealthy` | A API não responde em `/api/saude` | `docker compose logs` mostra o erro (ex.: migração, permissão em `dados/`) |
| "Não foi possível gerar o PDF" | Chromium sem memória compartilhada ou sem memória | Confira `shm_size` e `mem_limit` no compose |
| Manual some depois de `down -v` | O `-v` apaga o volume | Restaure do backup ([seção 5](#5-dados-volume-backup-e-restauração)) |


## 10. Homologação num servidor (sem o compose)

> Esta seção é para um servidor que **já tem** um proxy reverso com HTTPS (Traefik, nginx…). Num servidor novo e
> só seu (por exemplo, o gratuito da Oracle Cloud), use [oracle-cloud.md](oracle-cloud.md): o compose com o Caddy na
> frente faz o HTTPS, põe uma senha na entrada e já liga esta mesma faixa de homologação.

Para a equipe testar antes de usar de verdade. **Não há login**: a homologação roda só com o sistema de exemplo
(`demo_pdv`, manuais `DEMO.*`) e documentos de teste. Nada de catálogo real, manual interno ou `modulos.json`.

```bash
docker build -t support-nexus:0.3.0 .
docker run -d --name support-nexus-homolog --restart unless-stopped \
  --memory 1g --cpus 1 \
  -e NEXUS_AMBIENTE=homologacao \
  -v support-nexus-homolog-dados:/app/backend/dados \
  support-nexus:0.3.0
```

| Opção | Por quê |
|---|---|
| `NEXUS_AMBIENTE=homologacao` | Faixa "Ambiente de homologação — dados de exemplo" no topo de todas as telas. |
| `--memory 1g --cpus 1` | Os mesmos limites do compose: a homologação não disputa a máquina com outros sistemas. |
| volume próprio | Banco, manuais e prints sobrevivem a um deploy; não compartilhe com nenhum outro app. |
| sem `-p` | O proxy reverso (Traefik, nginx…) do servidor fala com a porta **8010** do contêiner e cuida do HTTPS. |

- **Fora dos buscadores:** toda resposta leva `X-Robots-Tag: noindex, nofollow` e o `robots.txt` bloqueia tudo.
- **Rede:** não ligue o contêiner na rede onde ficam os bancos de outros sistemas; uma rede só dele, que o
  proxy alcance, basta.
- **Zerar:** `docker rm -f support-nexus-homolog && docker volume rm support-nexus-homolog-dados` e subir de
  novo. O seed recarrega o exemplo sozinho.
- **Saúde:** `GET /api/saude` responde `{"ok": true, "versao": ..., "ambiente": "homologacao"}`.

