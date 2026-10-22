# Segurança

## Como avisar uma falha

**Não abra issue pública.** Use o aviso privado do GitHub:
[Security → Report a vulnerability](https://github.com/rodrigokojiro1996-bot/wiki-support-nexus/security/advisories/new).

Conte o que encontrou, como reproduzir e o impacto que imagina. A resposta vem em até 7 dias, e o aviso só fica
público depois da correção publicada.

## O que vale avisar

- Leitura ou escrita de arquivos fora de `backend/dados/` (por exemplo, pelo upload de imagens ou pela importação).
- Execução de código a partir de um documento importado (PDF, Word) ou de um manual.
- Senha, token ou string de conexão que apareça em manual, log, métrica ou resposta da API.
- Acesso ao banco do sistema mapeado além da leitura do `information_schema` pelo coletor.

## O que o projeto já faz

- O coletor lê só o `information_schema`: estrutura, nunca dados de clientes.
- Senhas são mascaradas no editor e na importação; autores são removidos dos documentos importados.
- O tipo de cada imagem é conferido pelos bytes, e nomes de arquivo com `..` são recusados.
- No Docker, a aplicação roda com usuário sem privilégios e as portas ficam só em `127.0.0.1`.
- Secret scanning e push protection ligados: o GitHub barra o push de um commit com credencial conhecida.

## Versões com suporte

Só a versão mais recente (a `main` e a última tag `v*`) recebe correções de segurança.
