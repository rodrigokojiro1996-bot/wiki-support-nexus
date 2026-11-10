# Dicionário de dados (balão do diagrama)

Ao parar o cursor numa tabela ou numa coluna do diagrama, um balão mostra o que ela guarda. As descrições são
escritas pela equipe: o sistema só sugere um rascunho a partir das abreviações dos nomes.

## 1. Gerar o rascunho

```bash
pip install -r coletor/requirements.txt
python coletor/rascunho_descricoes.py      # -> coletor/saida/dicionario-spa.xlsx
```

Lê os `tabelas.csv`/`colunas.csv` de cada pasta em `coletor/saida` (o nome da pasta diz o módulo: pdv, adm, fin).
A planilha fica em `coletor/saida`, que não vai para o git: ela tem a estrutura do banco do ERP.

| Aba | Uma linha por | Observação |
|---|---|---|
| Tabelas | tabela de cada módulo | "Armazena os dados de produtos do SPA PDV" |
| Colunas | **nome** de coluna | a descrição vale para todas as tabelas em que o nome aparece |
| Exceções | tabela + coluna | quando o nome quer dizer outra coisa naquela tabela; já vem com os comentários do banco |

Cada sugestão traz a confiança: `banco` (comentário que já existe no MySQL), `alta`, `média` (nome colado ou
abreviação de duplo sentido, explicada na Observação), `baixa` (parte desconhecida entre colchetes) e
`sem sugestão` (nada é inventado).

## 2. Conferir

Quem conhece o sistema corrige a coluna "Descrição (edite aqui)" e marca **Conferido = S**. Só entra na Wiki o
que estiver com S; o resto é ignorado. Dá para mandar a planilha por partes, quantas vezes quiser: mandar de novo
atualiza o texto.

## 3. Importar

```bash
curl -u USUARIO:SENHA -X POST https://SEU_DOMINIO/api/descricoes/importar \
     -H "X-Usuario: Nome de quem conferiu" --data-binary @coletor/saida/dicionario-spa.xlsx
```

Com o login Microsoft ligado ([login-microsoft.md](login-microsoft.md)), a API pede a sessão de quem entrou e o
`curl` acima não passa. Nesse caso, importe de dentro do servidor:

```bash
docker compose cp coletor/saida/dicionario-spa.xlsx nexus:/tmp/dicionario.xlsx
docker compose exec nexus python -m app.servicos.descricoes /tmp/dicionario.xlsx "Nome de quem conferiu"
```

A resposta conta o que entrou (`tabelas`, `colunas`, `excecoes`), o que não estava conferido (`nao_conferidas`) e
as linhas recusadas (`fora`, por exemplo um módulo que não existe). As descrições ficam na tabela `descricoes`
(migração 009), por módulo, e não se perdem quando o catálogo é importado de novo. Um módulo ainda sem banco
ligado já guarda as suas.
