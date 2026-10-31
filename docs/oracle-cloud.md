# Support Nexus na Oracle Cloud (versão de testes para a equipe)

Como colocar o Support Nexus num servidor gratuito da Oracle Cloud, com um link HTTPS para a equipe testar. Para o
que é o Docker e o porquê de cada escolha da imagem, veja [docker.md](docker.md). Se o servidor já tiver um proxy
com HTTPS (um servidor da empresa, por exemplo), o caminho mais curto é o `docker run` da seção 10 de
[docker.md](docker.md); este guia é para um servidor novo e só seu.

1. [O que vai ficar no ar](#1-o-que-vai-ficar-no-ar)
2. [Antes de começar](#2-antes-de-começar)
3. [Criar o servidor na Oracle Cloud](#3-criar-o-servidor-na-oracle-cloud)
4. [Liberar as portas 80 e 443 na rede da Oracle](#4-liberar-as-portas-80-e-443-na-rede-da-oracle)
5. [Dar um nome ao servidor (domínio)](#5-dar-um-nome-ao-servidor-domínio)
6. [Entrar no servidor pelo SSH](#6-entrar-no-servidor-pelo-ssh)
7. [Preparar o servidor e subir o Support Nexus](#7-preparar-o-servidor-e-subir-o-support-nexus)
8. [Conferir antes de mandar o link](#8-conferir-antes-de-mandar-o-link)
9. [Mensagem para a equipe](#9-mensagem-para-a-equipe)
10. [Dia a dia](#10-dia-a-dia)
11. [Segurança desta versão de testes](#11-segurança-desta-versão-de-testes)
12. [Custos e regras do plano gratuito](#12-custos-e-regras-do-plano-gratuito)
13. [Problemas comuns](#13-problemas-comuns)
14. [Usar a estrutura real do sistema](#14-usar-a-estrutura-real-do-sistema)


## 1. O que vai ficar no ar

```
  equipe (navegador)
        │  https://nexus-suporte.duckdns.org   ← senha única da equipe (janela do navegador)
        ▼
  ┌───────────────────────── servidor Oracle (Ubuntu 24.04, ARM) ─────────────────────────┐
  │  caddy :80 :443   HTTPS automático (Let's Encrypt), senha da entrada, bloqueios       │
  │     │ rede interna do Docker                                                          │
  │     ▼                                                                                 │
  │  nexus :8010      a aplicação (sem porta própria para fora)                           │
  │  prometheus, grafana   só em 127.0.0.1 do servidor: acesso por túnel SSH              │
  └───────────────────────────────────────────────────────────────────────────────────────┘
```

- **Uma senha única na entrada** (usuário `equipe`). Não é o login do sistema, que fica para a versão de
  homologação: é um portão para que robôs e curiosos da internet não apaguem manuais, encham o disco de imagens
  ou ocupem o servidor gerando PDFs. O campo "Seu nome" continua registrando quem fez cada alteração.
- **Faixa "Ambiente de homologação"** no topo de todas as telas (`NEXUS_AMBIENTE=homologacao`,
  ligado no `docker-compose.oracle.yml`), e o site **fora dos buscadores** (`robots.txt` e `X-Robots-Tag`).
- **Só o sistema de exemplo** (o PDV fictício). Para os testes, não coloque manuais reais nem dados de clientes:
  a senha é compartilhada e a autoria é só um nome digitado.
- **Fechados para a internet:** `/metrics` (tem os nomes de quem contribuiu), a documentação da API (`/docs`), o
  Grafana e o Prometheus.

Os arquivos do servidor ficam em `deploy/oracle/`:

| Arquivo | Para quê |
|---|---|
| `docker-compose.oracle.yml` | complemento do `docker-compose.yml`: põe o Caddy na frente e tira a porta da API para fora |
| `Caddyfile` | HTTPS, senha da entrada, bloqueios, cabeçalhos de segurança, limite de 10 MB por envio |
| `preparar-servidor.sh` | roda uma vez no servidor novo: Docker, fuso, atualizações automáticas, firewall, swap |
| `configurar.sh` | cria o `.env` do servidor: domínio, e-mail, senha da entrada (cifrada) e do Grafana |
| `backup.sh` | compacta banco, manuais e prints; mantém os 14 mais recentes |

O que foi ensaiado antes, nesta máquina:
- **A imagem para ARM** (o processador do servidor gratuito), compilada e rodando num processador ARM emulado: a
  aplicação sobe saudável e o **Chromium ARM gera o PDF** do manual. Na emulação o Chromium só funciona em modo
  simplificado (o emulador trava com os vários processos dele); no servidor, que é ARM de verdade, ele roda no modo
  normal, como em qualquer Linux.
- **A API atrás do Caddy**: sem senha 401; com senha a interface abre; `/metrics`, `/docs` e `/openapi.json` 404;
  envio de 12 MB recusado; PDF pelo HTTPS; `http://` redirecionando para `https://`; cabeçalhos de segurança; e o
  editor de ponta a ponta no navegador (criar manual, colar print, salvar, editar).
- **O `configurar.sh`**, o **backup** e a **restauração** (inclusive que um backup que falha não deixa arquivo
  quebrado para trás).


## 2. Antes de começar

Tempo estimado: 40 a 60 minutos na primeira vez (a maior parte é esperar a Oracle criar a conta e o build).

- Uma conta na Oracle Cloud (pede cartão de crédito só para verificar a identidade; o plano gratuito não cobra).
- Um e-mail para os avisos do certificado HTTPS.
- O código no GitHub, no `main` (os arquivos deste guia já estão nele).

> **Região de origem.** Na criação da conta a Oracle pede a "home region", e ela **não pode ser trocada depois**.
> As máquinas gratuitas ficam nela. Escolha uma perto (São Paulo ou Vinhedo); se a máquina ARM gratuita estiver
> sempre sem capacidade numa delas, é ali que você vai ficar, então não escolha às pressas.


## 3. Criar o servidor na Oracle Cloud

No console (<https://cloud.oracle.com>): **Compute → Instances → Create instance**. Os nomes das telas mudam de
vez em quando; o que importa são as escolhas:

| Campo | Escolha | Por quê |
|---|---|---|
| Name | `support-nexus` | |
| Image | **Canonical Ubuntu 24.04** | os scripts foram feitos para ele |
| Shape | **Ampere → VM.Standard.A1.Flex**, **1 OCPU e 4 GB** | máquina ARM do plano gratuito, que hoje vai até 2 OCPUs e 12 GB no total. O projeto usa bem menos (API ~70 MB parada, PDF ~300 MB por alguns segundos), e uma máquina menor fica longe do critério de "ociosa" da seção 12 |
| Networking | criar uma VCN nova com **sub-rede pública** e **atribuir IPv4 público** | o servidor precisa de endereço na internet |
| SSH keys | **Generate a key pair** e **baixe a chave privada** (`.key`) | é a "senha" de acesso ao servidor; guarde bem e nunca mande para ninguém |
| Boot volume | padrão (~47 GB) | a imagem tem 1,5 GB; sobra muito |

Clique em **Create** e espere o estado **Running**. Anote o **Public IP address**.

> **"Out of capacity"** é comum nas máquinas ARM gratuitas. Tente outro *Availability Domain*, outro tamanho
> (1 OCPU e 2 GB ainda roda tudo) ou outro horário. Plano B: a máquina AMD gratuita (`VM.Standard.E2.1.Micro`,
> 1 GB de memória) roda o Support Nexus sem o monitoramento; veja [Problemas comuns](#13-problemas-comuns).


## 4. Liberar as portas 80 e 443 na rede da Oracle

A Oracle tem **dois firewalls**: o da rede (aqui, no console) e o de dentro do servidor (o `preparar-servidor.sh`
cuida dele). Os dois precisam liberar as portas.

**Networking → Virtual cloud networks →** a VCN criada **→** a sub-rede pública **→ Security List →
Add Ingress Rules**, uma regra por linha:

| Source CIDR | IP Protocol | Destination Port | Para quê |
|---|---|---|---|
| `0.0.0.0/0` | TCP | `80` | o Let's Encrypt confirma o domínio por aqui; depois só redireciona para o HTTPS |
| `0.0.0.0/0` | TCP | `443` | o site (HTTPS) |
| `0.0.0.0/0` | UDP | `443` | HTTP/3 (opcional, mais rápido em celular) |

A porta 22 (SSH) já vem liberada. **Não** libere 3000, 9090 nem 8010.

> Para restringir aos colegas: em vez de `0.0.0.0/0`, use o IP público da empresa (ex.: `200.100.50.10/32`).
> Quem estiver fora da empresa não abre o link, mas também nenhum robô da internet chega na senha.


## 5. Dar um nome ao servidor (domínio)

O HTTPS precisa de um nome, não só do IP. O jeito gratuito e simples é o **DuckDNS**:

1. Entre em <https://www.duckdns.org> (com conta Google ou GitHub).
2. Crie um subdomínio, ex.: `nexus-suporte` → fica `nexus-suporte.duckdns.org`.
3. No campo **current ip**, ponha o IP público do servidor e clique em **update ip**.
4. Confira no PowerShell: `nslookup nexus-suporte.duckdns.org` deve responder o IP do servidor (pode levar alguns
   minutos).

> Alternativa sem cadastro: `IP-com-traços.sslip.io` (ex.: `150-230-10-5.sslip.io`) já aponta para o IP
> sozinho. Funciona, mas o link fica menos legível e depende de um serviço de terceiros.


## 6. Entrar no servidor pelo SSH

No PowerShell do Windows. O Windows exige que a chave privada só possa ser lida por você:

```powershell
$chave = "$HOME\.ssh\support-nexus.key"
Move-Item "$HOME\Downloads\ssh-key-*.key" $chave          # a chave baixada no passo 3
icacls $chave /inheritance:r /grant:r "$($env:USERNAME):(R)"
ssh -i $chave ubuntu@IP_DO_SERVIDOR                       # aceite a impressão digital na primeira vez (yes)
```

Daqui em diante, os comandos são **no servidor** (o prompt muda para `ubuntu@support-nexus:~$`).


## 7. Preparar o servidor e subir o Support Nexus

```bash
# 1) baixar o projeto
git clone https://github.com/rodrigokojiro1996-bot/wiki-support-nexus.git     # antes do merge: -b feat/deploy-oracle
cd wiki-support-nexus

# 2) preparar o servidor (uma vez só): Docker, fuso, atualizações automáticas, firewall interno, swap
sudo bash deploy/oracle/preparar-servidor.sh
exit                                    # sair e entrar de novo (ssh ...) para o grupo "docker" valer
```

Depois de entrar de novo:

```bash
cd wiki-support-nexus

# 3) configurar: domínio, e-mail e a senha da entrada (Enter na senha = gerar uma forte)
bash deploy/oracle/configurar.sh

# 4) subir: compila a imagem no próprio servidor (ARM) e sobe API, Caddy, Prometheus e Grafana
docker compose up -d --build            # o primeiro build leva alguns minutos
docker compose ps                       # espere todos "(healthy)"; o caddy aparece como "Up"
docker compose logs caddy | grep -i certificate    # deve mostrar "certificate obtained successfully"
```

O que cada passo faz:
- **`preparar-servidor.sh`** instala o Docker do repositório oficial (não a versão antiga do Ubuntu), põe o
  relógio em São Paulo, liga as **atualizações automáticas de segurança**, libera 80 e 443 no firewall interno
  (as imagens Ubuntu da Oracle vêm recusando tudo além do SSH, e isso pega muita gente) e cria swap se a máquina
  tiver menos de 4 GB.
- **`configurar.sh`** grava o `.env` com permissão só para o dono. A senha da entrada é **cifrada** pelo próprio
  Caddy (bcrypt) e gravada entre aspas simples, porque o hash tem vários `$` que o compose leria como variáveis.
  Se você deixar a senha em branco, ele gera uma e **mostra uma vez só**: anote. Ele também põe no `.env` o
  `COMPOSE_FILE`, que faz o `docker compose` usar o complemento do servidor sem precisar digitar `-f`.
- **`docker compose up -d --build`** compila a imagem **no servidor** (nativa para ARM) e sobe tudo. O Caddy pede
  o certificado ao Let's Encrypt sozinho na primeira subida e renova antes de vencer.


## 8. Conferir antes de mandar o link

Do seu computador (troque o domínio e a senha):

```powershell
$u = "https://nexus-suporte.duckdns.org"
curl.exe -s -o NUL -w "%{http_code}  sem senha (espera 401)`n" "$u/"
curl.exe -s -o NUL -w "%{http_code}  com senha (espera 200)`n" -u equipe:SENHA "$u/"
curl.exe -s -o NUL -w "%{http_code}  /metrics  (espera 404)`n" -u equipe:SENHA "$u/metrics"
curl.exe -s "$u/api/saude"; ""                                # sem senha: {"ok":true,...,"ambiente":"homologacao"}
curl.exe -s -o NUL -w "%{http_code}  PDF (espera 200)`n" -u equipe:SENHA "$u/api/manuais/DEMO.001/pdf"
curl.exe -s -o NUL -w "%{http_code}  Grafana de fora (espera 000: recusado)`n" -m 5 "http://IP_DO_SERVIDOR:3000/"
```

E no navegador, de preferência pelo celular (outra rede):
- [ ] o navegador pede usuário e senha, e mostra o cadeado (HTTPS válido);
- [ ] a faixa "Ambiente de homologação" aparece no topo;
- [ ] o mapa do sistema abre; uma tela com tabelas mostra o diagrama;
- [ ] **Criar manual para esta tela** → colar um print com Ctrl+V → salvar → o manual aparece na tela;
- [ ] **Exportar PDF** baixa o arquivo;
- [ ] apague o manual de teste começando do zero ([Dia a dia](#10-dia-a-dia), "voltar ao exemplo limpo"), para a
      equipe ver o exemplo intacto.


## 9. Mensagem para a equipe

> Pessoal, está no ar a versão de testes do **Support Nexus**, uma base de conhecimento que liga cada tela do
> sistema aos manuais e às tabelas do banco.
>
> 🔗 https://nexus-suporte.duckdns.org
> 👤 usuário: `equipe` · 🔑 senha: *(mando separado)*
>
> **O que testar**
> 1. Escolha uma tela no mapa à esquerda e veja a ficha: caminho, manuais, tabelas e o diagrama (aba Tabelas).
> 2. Valide ou descarte as ligações sugeridas entre tabelas.
> 3. Numa tela sem manual, clique em **Criar manual para esta tela**. Cole prints com Ctrl+V e veja a prévia.
> 4. Exporte um manual em PDF.
>
> **Importante**
> - Preencha **Seu nome** no topo da página: é assim que fica registrado quem fez cada coisa.
> - É um **sistema de exemplo** (um PDV fictício). Não coloque manuais reais, senhas nem dados de clientes.
> - Tudo pode ser apagado ao fim dos testes.
> - Achou algo estranho ou tem uma ideia? Me manda print e a tela em que estava.

Mande a senha por outro canal (mensagem privada), não no mesmo texto do link.


## 10. Dia a dia

Sempre na pasta `~/wiki-support-nexus`, no servidor:

| Para… | Comando |
|---|---|
| ver se está tudo de pé | `docker compose ps` |
| ver o log da aplicação / do Caddy | `docker compose logs -f nexus` / `docker compose logs -f caddy` |
| atualizar para o código mais novo | `git pull && docker compose up -d --build` |
| backup agora | `bash deploy/oracle/backup.sh` (fica em `~/backups-nexus`) |
| backup todo dia às 3h | `crontab -e` e cole a linha que está no topo do `backup.sh` |
| trocar a senha da entrada | `bash deploy/oracle/configurar.sh --trocar-senha` e `docker compose up -d caddy` |
| voltar ao exemplo limpo (apaga o que a equipe fez) | `docker compose down`, `docker volume rm support-nexus_nexus-dados`, `docker compose up -d` |
| tirar do ar (mantém os dados) | `docker compose down` |
| ver o Grafana | do seu PC: `ssh -i $chave -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@IP` e abra <http://localhost:3000> (usuário `admin`, senha `GRAFANA_SENHA` do `.env` do servidor: `grep GRAFANA ~/wiki-support-nexus/.env`) |

> Os volumes se chamam `support-nexus_…` (o nome do projeto está fixo no `docker-compose.yml`). Confira com
> `docker volume ls` antes de apagar algum.

**Restaurar um backup** (substitui tudo o que está no volume pelo conteúdo do backup):
```bash
bash deploy/oracle/backup.sh                       # 1) por garantia, um backup do estado atual
docker compose rm -sf nexus                        # 2) para e remove o contêiner da aplicação
docker volume rm support-nexus_nexus-dados         # 3) remove o volume de dados (explícito, sem "rm -rf")
docker compose run --rm --no-deps -u root -v ~/backups-nexus:/b --entrypoint tar nexus \
  xzf /b/nexus-dados-AAAAMMDD-HHMM.tar.gz -C /app/backend   # 4) volume novo com o conteúdo do backup
docker compose up -d                               # 5) sobe de novo
```
O `tar` rodando como root devolve a cada arquivo o dono original (o usuário `nexus`), então não precisa ajustar
permissões.


## 11. Segurança desta versão de testes

O que protege:
- **HTTPS** com certificado válido: senha e conteúdo trafegam cifrados.
- **Senha única na entrada**, cifrada no servidor (bcrypt); errar só devolve 401.
- **Só o Caddy está exposto.** A API não tem porta própria para fora; Grafana e Prometheus só em `127.0.0.1`.
- **Bloqueados:** `/metrics`, `/docs`, `/redoc`, `/openapi.json` (404 mesmo com a senha).
- **Envios limitados** a 10 MB (o Caddy recusa antes de chegar na aplicação; a API aceita até 8 MB por print).
- **Cabeçalhos de segurança** (HSTS, nosniff, proibido abrir dentro de outro site) e sem anunciar o servidor.
- Servidor com **atualizações automáticas de segurança**; contêineres sem root; imagens travadas por versão.

O que **não** protege (fica para a homologação, com login):
- Não há usuário por pessoa: quem tem a senha pode criar, editar e validar. A autoria é o nome digitado.
- Não há permissão por perfil (ex.: só curadores editam).
- Não há limite de tentativas de senha. Para reduzir o risco, use uma senha forte (a gerada tem 16 caracteres)
  e, se possível, restrinja a porta 443 ao IP da empresa (passo 4).

Boas práticas para os testes:
- Senha por canal privado; troque ao fim dos testes (`configurar.sh --trocar-senha`).
- Nenhum dado real: só o exemplo.
- Faça backup antes de atualizar.
- Ao terminar os testes, tire do ar (`docker compose down`) ou pare a instância no console.


## 12. Custos e regras do plano gratuito

Confira as regras atuais na página "Always Free" da Oracle antes de criar; elas já mudaram no passado. Até a data
deste guia:

- Máquinas ARM (Ampere A1) até **2 OCPUs e 12 GB** no total (era 4 e 24 até agosto de 2026, quando a Oracle
  cortou pela metade sem anúncio), 200 GB de disco e tráfego de saída generoso: o Support Nexus usa uma fração.
- **Máquinas ociosas podem ser recuperadas** pela Oracle nas contas gratuitas. É ociosa a máquina que, em 7 dias,
  fica com processador, rede **e** memória (esta só nas ARM) abaixo de 20%. Uma wiki de testes pouco usada fica com
  processador e rede baixos; o que a salva é a memória passar de 20%. Por isso a máquina pequena do passo 3: com
  4 GB, a aplicação, o Caddy, o Prometheus e o Grafana juntos ficam perto ou acima disso (confira em
  *Instance → Metrics → Memory utilization* na primeira semana). Converter a conta para *Pay As You Go*
  (pagamento conforme o uso), usando só recursos Always Free, costuma evitar isso; nesse caso, crie um
  **alerta de orçamento** (Billing → Budgets) de poucos reais, para ser avisado de qualquer cobrança.
- Enquanto a conta for só gratuita, nada é cobrado: o que não é Always Free simplesmente não pode ser criado.


## 13. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| O link não abre (tempo esgotado) | porta 443 fechada na Security List (passo 4) ou no firewall interno | confira as regras; no servidor, `sudo iptables -L INPUT -n --line-numbers` deve ter ACCEPT para 80/443 antes do REJECT |
| Erro de certificado / "não seguro" | o domínio não aponta para o IP, ou a porta 80 está fechada | `nslookup DOMINIO`; `docker compose logs caddy` mostra o motivo; corrija e `docker compose restart caddy` |
| `too many certificates` no log do Caddy | limite do Let's Encrypt por apagar e recriar muitas vezes | não apague o volume `caddy-dados`; espere algumas horas ou use outro subdomínio |
| Pede a senha sem parar | usuário ou senha errados | `bash deploy/oracle/configurar.sh --trocar-senha` e `docker compose up -d caddy` |
| `permission denied ... docker.sock` | o grupo docker ainda não valeu | saia e entre de novo no SSH |
| `Defina NEXUS_DOMINIO…` ao rodar o compose | `.env` não configurado | `bash deploy/oracle/configurar.sh` |
| `nexus` fica `unhealthy` | erro na subida | `docker compose logs nexus` |
| Horários errados nos registros | fuso | o compose usa `NEXUS_FUSO` (padrão `America/Sao_Paulo`) |
| Máquina AMD de 1 GB (plano B) lenta ou travando | memória | suba só o essencial: `docker compose up -d --build nexus caddy` (sem Prometheus e Grafana); o `preparar-servidor.sh` já cria 2 GB de swap |
| "Não foi possível gerar o PDF" no servidor | Chromium sem memória ou travado | `docker compose logs nexus`; confira `shm_size` e `mem_limit` no compose; `docker compose restart nexus` |
| O IP do servidor mudou | IP público efêmero | atualize no DuckDNS; para não mudar mais, reserve um IP público no console |


## 14. Usar a estrutura real do sistema

Por padrão o servidor mostra o sistema de exemplo (um PDV fictício). Para a equipe trabalhar com as tabelas e os
menus de verdade, os arquivos do sistema real vão para uma pasta **fora do repositório**, no servidor:

| Arquivo no servidor | De onde vem |
|---|---|
| `~/nexus-real/modulos.json` | módulos e o banco de cada um (`"banco": "<nome do schema>"`), no formato de `backend/modulos.exemplo.json` |
| `~/nexus-real/saida/<banco>/catalogo.json` | o coletor (`coletor/`), rodado numa máquina que alcança o banco |
| `~/nexus-real/menus/menus_<módulo>.json` | os menus de cada módulo (`menus_pdv.json`, `menus_adm.json`…), no formato de `backend/seed/menus_pdv.json` |

Do seu computador (troque `IP`):

```powershell
ssh -i $chave ubuntu@IP "mkdir -p ~/nexus-real/saida/<banco> ~/nexus-real/menus"
scp -i $chave backend\modulos.json ubuntu@IP:nexus-real/
scp -i $chave coletor\saida\<banco>\catalogo.json ubuntu@IP:nexus-real/saida/<banco>/
scp -i $chave menus_pdv.json ubuntu@IP:nexus-real/menus/
```

No servidor, acrescente o complemento ao `COMPOSE_FILE` do `.env` e suba de novo:

```bash
cd ~/wiki-support-nexus
bash deploy/oracle/backup.sh
sed -i 's#^COMPOSE_FILE=.*#COMPOSE_FILE=docker-compose.yml:deploy/oracle/docker-compose.oracle.yml:deploy/oracle/docker-compose.dados-reais.yml#' .env
docker compose up -d nexus caddy        # o seed da subida importa o catálogo e os menus reais
```

O que muda na troca:
- os menus e o catálogo de exemplo dão lugar aos reais; o selo "Sistema de exemplo" some;
- os manuais de exemplo (`DEMO.*`) saem, porque descrevem tabelas que não existem no sistema real;
- os manuais da equipe ficam. O que estava numa tela que não existe no menu real fica **sem tela**, listado na
  tela inicial do mapa em "Manuais sem tela", até alguém escolher a tela;
- validações de relação e vínculos feitos sobre o exemplo deixam de aparecer (eram de tabelas fictícias).

> A estrutura do banco é interna da empresa: o servidor só a mostra para quem tem a senha da entrada. Para fechar
> mais, restrinja a porta 443 ao IP da empresa (passo 4).

## 15. Painel das branches do Git (Grafana em /grafana/)

O painel "Support Nexus · Branches do Git" mostra toda branch que subiu para o GitHub: se existe ainda, a situação do
PR mais recente (aberto, merge feito, fechado ou sem PR), quem enviou o último push e quando, e o histórico de pull
requests. Os dados vêm da API pública do GitHub (plugin Infinity); o painel se atualiza a cada 15 minutos.

Na máquina de 1 GB o Grafana sobe sozinho, sem o Prometheus, só com esse painel (limite de 256 MB). O processador
dela é pequeno: o painel leva de 10 a 20 segundos para carregar. Para ligar:

```bash
cd ~/wiki-support-nexus
sed -i 's#^COMPOSE_FILE=.*#&:deploy/oracle/docker-compose.grafana.yml#' .env
docker compose up -d grafana
docker compose restart caddy            # o Caddyfile passa a encaminhar /grafana/ para o Grafana
```

Sem token, o GitHub aceita 60 consultas por hora e cada abertura do painel faz 10: com a equipe usando, o painel
fica sem dados até a hora virar. Crie um token **fine-grained sem nenhuma permissão** (ele só lê o que já é público)
em <https://github.com/settings/personal-access-tokens>, ponha no `.env` do servidor e recrie o Grafana:

```bash
nano ~/wiki-support-nexus/.env           # GITHUB_TOKEN=github_pat_...
docker compose up -d grafana
```

Abra `https://<domínio>/grafana/`: pede a mesma senha da entrada e mostra o painel. Para editar, entre como `admin`
com a `GRAFANA_SENHA` do `.env`. O painel em si é gerado por `docker/grafana/gerar_painel.py`; mudanças feitas na
tela não ficam salvas (use "Save as" para uma cópia sua).
