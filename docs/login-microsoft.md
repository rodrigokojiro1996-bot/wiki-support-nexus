# Login com a conta Microsoft (Entra ID)

O Support Nexus pode exigir a conta Microsoft da empresa para abrir. Só entram contas
**@farmaciasassociadas.com.br** do tenant da empresa. Com o login ligado, a autoria (quem validou uma relação,
vinculou uma tabela ou salvou um manual) passa a ser a pessoa que entrou, e não mais o nome digitado no topo.

Desligado (o padrão), tudo funciona como antes.

1. [Como funciona](#1-como-funciona)
2. [Registrar o aplicativo no Entra](#2-registrar-o-aplicativo-no-entra)
3. [Ligar no servidor](#3-ligar-no-servidor)
4. [Testar nesta máquina](#4-testar-nesta-máquina)
5. [Desligar (volta rápida)](#5-desligar-volta-rápida)
6. [Problemas comuns](#6-problemas-comuns)

## 1. Como funciona

```
 navegador                         Support Nexus (API)                       Microsoft (Entra)
    │  clica em "Entrar"  ───────►  /api/auth/entrar
    │                               guarda state, nonce e PKCE  ──────────►  tela de login da Microsoft
    │                                                                              │
    │  ◄──────────────────────────────────────────────────────────────────────────┘ volta com um código
    │  ───────────────────────────► /api/auth/retorno
    │                               troca o código pelo ID token  ◄────────►  (servidor a servidor)
    │                               confere assinatura, tenant, nonce e domínio
    │  ◄───────────────────────────  abre a sessão (cookie HttpOnly, 12 h)
```

Regras (em `backend/app/servicos/entra.py`):

- **Tenant da empresa.** `MICROSOFT_TENANT_ID` precisa ser o GUID do diretório. `common` e `organizations` são
  recusados, porque aceitariam conta de qualquer empresa. O token também precisa declarar esse tenant.
- **Só @farmaciasassociadas.com.br**, conferido no login da conta (UPN). O tenant tem outros domínios
  verificados, e quem faz login por eles **não entra**, mesmo que a caixa de e-mail seja @farmaciasassociadas. Convidados de fora também ficam de fora. O domínio é uma constante
  no código (`DOMINIO_PERMITIDO`): mudar exige commit e deploy, de propósito.
- **Assinatura conferida** contra as chaves públicas do tenant (só RS256), com emissor, aplicativo, validade e
  nonce. A criptografia é do PyJWT.
- **Sessão de 12 horas** guardada no banco (só o hash do token). Depois disso, um clique em "Entrar": a Microsoft
  já lembra a conta. "Sair" encerra a sessão na hora.
- **Toda a API pede sessão**, menos `/api/saude` e as rotas do próprio login. As páginas do app abrem sem sessão
  porque não trazem dados: elas mostram a tela de entrar.
- **PDF**: o navegador sem tela que gera o PDF recebe uma sessão só dele, de 2 minutos, apagada assim que o
  arquivo fica pronto.
- **Sessão que termina com a tela aberta** (um manual em edição, por exemplo): aparece um aviso com "Entrar de
  novo", que abre o login numa nova aba. O que está na tela continua lá; depois é só salvar.

## 2. Registrar o aplicativo no Entra

No [centro de administração do Microsoft Entra](https://entra.microsoft.com), com uma conta que pode registrar
aplicativos:

1. **Aplicativos → Registros de aplicativo → Novo registro**
   - Nome: `Support Nexus`
   - Tipos de conta: **Somente contas deste diretório organizacional** (locatário único)
   - URI de redirecionamento: plataforma **Web**, `https://<domínio>/api/auth/retorno`
2. Na **Visão geral**, copie:
   - **ID do aplicativo (cliente)** → `MICROSOFT_CLIENT_ID`
   - **ID do diretório (locatário)** → `MICROSOFT_TENANT_ID`
3. **Certificados e segredos → Novo segredo do cliente.** Escolha a validade e copie o **Valor** na hora (ele só
   aparece uma vez; o "ID do segredo" não serve) → `MICROSOFT_CLIENT_SECRET`. Anote a data de vencimento: quando o
   segredo vence, ninguém entra até trocar.
4. **Autenticação**: para testar na própria máquina, acrescente também
   `http://localhost:5173/api/auth/retorno` (modo de desenvolvimento, com o Vite) e
   `http://localhost:8010/api/auth/retorno` (modo de produção ou Docker local). O Entra só aceita `http` em
   `localhost`.
5. **Permissões de API**: as que já vêm (`User.Read`, do Microsoft Graph) bastam. O app pede só `openid`,
   `profile` e `email`. Se quiser evitar a tela de consentimento no primeiro acesso de cada pessoa, use
   **Conceder consentimento do administrador**.

Opcional, para limitar a um grupo dentro da empresa: **Aplicativos empresariais → Support Nexus → Propriedades →
Atribuição obrigatória = Sim**, e adicione as pessoas ou grupos em **Usuários e grupos**. Vale junto com a regra
do domínio.

## 3. Ligar no servidor

No `.env` do servidor (ao lado do `docker-compose.yml`), **sem aspas**:

```
MICROSOFT_AUTH_ENABLED=true
MICROSOFT_TENANT_ID=<ID do diretório>
MICROSOFT_CLIENT_ID=<ID do aplicativo>
MICROSOFT_CLIENT_SECRET=<Valor do segredo>
MICROSOFT_REDIRECT_URI=https://<domínio>/api/auth/retorno
```

```bash
docker compose up -d        # recria o nexus (lê as variáveis) e o Caddy (troca o bloco de acesso)
docker compose logs nexus --tail 20
```

`MICROSOFT_AUTH_ENABLED=true` faz duas coisas: liga o login no app e, no Caddy, tira a senha única da frente do
app. A senha continua só em `/grafana/`, porque o Grafana mostra os painéis para quem passar dela. Use
exatamente `true` ou `false`: com outro valor o Caddy não sobe (falha fechada, nunca aberta).

Com o login ligado e alguma variável faltando, o Support Nexus **não sobe** e o log diz o que falta.

Conferir:
- `https://<domínio>/` mostra a tela "Entrar com a conta Microsoft", sem a janela de senha;
- `curl -s -o /dev/null -w "%{http_code}" https://<domínio>/api/modulos` devolve `401`;
- entrar com uma conta @farmaciasassociadas.com.br abre o mapa, com o seu nome no topo.

## 4. Testar nesta máquina

Cadastre `http://localhost:5173/api/auth/retorno` no Entra (passo 2.4) e, no PowerShell, antes do
`.\iniciar.ps1`:

```powershell
$env:MICROSOFT_AUTH_ENABLED = 'true'
$env:MICROSOFT_TENANT_ID = '<ID do diretório>'
$env:MICROSOFT_CLIENT_ID = '<ID do aplicativo>'
$env:MICROSOFT_CLIENT_SECRET = '<Valor do segredo>'
$env:MICROSOFT_REDIRECT_URI = 'http://localhost:5173/api/auth/retorno'
.\iniciar.ps1
```

No modo de produção (`.\iniciar-producao.ps1`) ou no Docker local, use `http://localhost:8010/api/auth/retorno`.
Os testes automáticos não falam com a Microsoft: um Entra falso assina os tokens (`backend/tests/conftest.py`).

## 5. Desligar (volta rápida)

```
MICROSOFT_AUTH_ENABLED=false
```

e `docker compose up -d`. Volta a senha única na entrada (Caddy) e o campo "Seu nome" no topo. As sessões ficam
no banco e vencem sozinhas.

## 6. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| A Microsoft mostra `AADSTS50011` (redirect URI) | O endereço de retorno não está cadastrado no Entra, ou difere em algum detalhe (`www`, porta, barra no fim) | Cadastrar em **Autenticação** exatamente o valor de `MICROSOFT_REDIRECT_URI` |
| "Não foi possível falar com a Microsoft" e o log diz `invalid_client` | Segredo errado, vencido ou colado com aspas | Gerar um segredo novo, colar sem aspas e `docker compose up -d` |
| "Esta conta não tem acesso" para alguém da empresa | O login (UPN) da pessoa é de outro domínio do tenant | É a regra combinada: só @farmaciasassociadas.com.br. Ajustar o UPN da pessoa no Entra, ou mudar `DOMINIO_PERMITIDO` no código |
| O Support Nexus não sobe e o log diz "configuração está incompleta" | Variável faltando ou inválida (o log lista quais) | Corrigir o `.env` |
| O Caddy não sobe e o log fala de `snippet` | `MICROSOFT_AUTH_ENABLED` com valor diferente de `true`/`false` | Corrigir o valor |
| "A tentativa de entrar expirou" | Mais de 10 minutos na tela da Microsoft, ou o login começou em outro navegador | Clicar em "Entrar" de novo |

Os motivos detalhados de cada recusa ficam no log do contêiner (`docker compose logs nexus | grep login`); a tela
mostra só uma mensagem genérica, de propósito.
