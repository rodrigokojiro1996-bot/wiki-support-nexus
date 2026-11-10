"""Gera a planilha de RASCUNHO das descrições de tabelas e colunas (dicionário de dados) para a equipe conferir.

  python coletor/rascunho_descricoes.py            -> coletor/saida/dicionario-spa.xlsx

Lê os tabelas.csv/colunas.csv de cada pasta em coletor/saida (a mesma saída do coletar.py; o nome da pasta diz o
módulo: pdv, adm ou fin). As sugestões saem das abreviações do glossário abaixo e cada linha leva o grau de confiança:
  banco        comentário que já existe no MySQL (vai para a aba Exceções, por tabela)
  alta         todas as partes do nome são conhecidas e sem ambiguidade
  média        nome colado (codprod) ou com parte ambígua (ent = entrada/entrega)
  baixa        alguma parte desconhecida, que fica entre colchetes
  sem sugestão nenhuma parte conhecida: a descrição fica em branco, nada é inventado
Só entra na Wiki o que a equipe marcar como Conferido = S (backend/app/servicos/descricoes.py importa a planilha).
A planilha fica em coletor/saida, que não vai para o git: o catálogo do sistema mapeado não é público.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "saida"
MODULOS = {"pdv": "SPA PDV", "adm": "SPA ADM", "fin": "SPA FIN"}

# abreviação -> (texto, preposição quando a parte complementa a anterior). Preposição "" = adjetivo, entra direto.
G = {
    # núcleos mais comuns
    "cod": ("código", "do"), "codigo": ("código", "do"), "cd": ("código", "do"), "id": ("identificador", "do"),
    "num": ("número", "do"), "numero": ("número", "do"), "nro": ("número", "do"), "nr": ("número", "do"), "n": ("número", "do"),
    "seq": ("sequência", "da"), "sequenc": ("sequência", "da"), "sequencia": ("sequência", "da"),
    "vlr": ("valor", "do"), "valor": ("valor", "do"), "vl": ("valor", "do"), "val": ("valor", "do"),
    "qtd": ("quantidade", "da"), "qt": ("quantidade", "da"), "qtde": ("quantidade", "da"), "quant": ("quantidade", "da"),
    "quantid": ("quantidade", "da"), "perc": ("percentual", "do"), "per": ("percentual", "do"), "percent": ("percentual", "do"),
    "pc": ("percentual", "do"), "p": ("percentual", "do"),
    "data": ("data", "da"), "dta": ("data", "da"), "dt": ("data", "da"), "dat": ("data", "da"),
    "hora": ("hora", "da"), "hor": ("hora", "da"), "hr": ("hora", "da"),
    "tipo": ("tipo", "do"), "tp": ("tipo", "do"), "ind": ("indicador", "do"), "flag": ("indicador", "do"),
    "nome": ("nome", "do"), "nom": ("nome", "do"), "name": ("nome", "do"),
    "desc": ("desconto", "do"), "descr": ("descrição", "da"), "descri": ("descrição", "da"), "descricao": ("descrição", "da"),
    "description": ("descrição", "da"), "discrimin": ("discriminação", "da"), "discriminacao": ("discriminação", "da"),
    "obs": ("observação", "da"), "observ": ("observação", "da"), "inf": ("informação", "da"), "info": ("informação", "da"),
    "mens": ("mensagem", "da"), "mensag": ("mensagem", "da"), "mensagem": ("mensagem", "da"), "msg": ("mensagem", "da"),
    "status": ("situação", "da"), "stat": ("situação", "da"), "situacao": ("situação", "da"), "situac": ("situação", "da"),
    "sit": ("situação", "da"),
    "tot": ("total", "do"), "total": ("total", "do"), "base": ("base de cálculo", "da"), "bc": ("base de cálculo", "da"),
    "aliq": ("alíquota", "da"), "alq": ("alíquota", "da"), "taxa": ("taxa", "da"), "txa": ("taxa", "da"),
    "preco": ("preço", "do"), "prec": ("preço", "do"), "pr": ("preço", "do"), "custo": ("custo", "do"), "cust": ("custo", "do"),
    "saldo": ("saldo", "do"), "sld": ("saldo", "do"), "limite": ("limite", "do"), "lim": ("limite", "do"),
    "prazo": ("prazo", "do"), "prz": ("prazo", "do"), "dia": ("dia", "do"), "dias": ("dias", "dos"), "mes": ("mês", "do"),
    "ano": ("ano", "do"), "tempo": ("tempo", "do"), "periodo": ("período", "do"), "intervalo": ("intervalo", "do"),
    "chave": ("chave", "da"), "chv": ("chave", "da"), "senha": ("senha", "da"), "sen": ("senha", "da"),
    "token": ("token", "do"), "hash": ("hash", "do"), "md5": ("hash MD5", "do"),
    "versao": ("versão", "da"), "ver": ("versão", "da"), "ordem": ("ordem", "da"), "ord": ("ordem", "da"),
    "nivel": ("nível", "do"), "faixa": ("faixa", "da"), "fxa": ("faixa", "da"), "fator": ("fator", "do"),
    "indice": ("índice", "do"), "margem": ("margem", "da"), "marg": ("margem", "da"), "meta": ("meta", "da"),
    "regra": ("regra", "da"), "campo": ("campo", "do"), "texto": ("texto", "do"), "txt": ("texto", "do"),
    "conteudo": ("conteúdo", "do"), "opcao": ("opção", "da"), "motivo": ("motivo", "do"), "mot": ("motivo", "do"),
    "lote": ("lote", "do"), "serie": ("série", "da"), "ser": ("série", "da"), "modelo": ("modelo", "do"), "mod": ("modelo", "do"),
    "posicao": ("posição", "da"), "posic": ("posição", "da"), "pos": ("posição", "da"), "linha": ("linha", "da"), "lin": ("linha", "da"),
    "url": ("endereço web (URL)", "do"), "link": ("link", "do"), "ip": ("endereço IP", "do"), "host": ("servidor (host)", "do"),
    "porta": ("porta", "da"), "port": ("porta", "da"), "login": ("login", "do"), "email": ("e-mail", "do"),
    "arquivo": ("arquivo", "do"), "arq": ("arquivo", "do"), "pasta": ("pasta", "da"), "foto": ("foto", "da"),
    "img": ("imagem", "da"), "json": ("JSON", "do"), "xml": ("XML", "do"), "layout": ("leiaute", "do"), "leiaute": ("leiaute", "do"),
    "resultado": ("resultado", "do"), "result": ("resultado", "do"), "res": ("resultado", "do"), "erro": ("erro", "do"),
    "log": ("registro (log)", "do"), "hist": ("histórico", "do"), "histor": ("histórico", "do"), "historico": ("histórico", "do"),
    "sinal": ("sinal", "do"), "sin": ("sinal", "do"), "digito": ("dígito", "do"), "dig": ("dígito", "do"),
    "contador": ("contador", "do"), "cont": ("contador", "do"), "pontos": ("pontos", "dos"), "ponto": ("ponto", "do"),
    "peso": ("peso", "do"), "largura": ("largura", "da"), "comprimento": ("comprimento", "do"), "comprim": ("comprimento", "do"),
    "espessura": ("espessura", "da"), "tam": ("tamanho", "do"), "vol": ("volume", "do"), "decimais": ("casas decimais", "das"),
    "idade": ("idade", "da"), "sexo": ("sexo", "do"), "genero": ("gênero", "do"), "gen": ("genérico", ""),
    "prioridade": ("prioridade", "da"), "categoria": ("categoria", "da"), "categ": ("categoria", "da"), "cat": ("categoria", "da"),
    "classe": ("classe", "da"), "clas": ("classe", "da"), "cla": ("classe", "da"), "classif": ("classificação", "da"),
    "grupo": ("grupo", "do"), "grp": ("grupo", "do"), "sgrupo": ("subgrupo", "do"), "subgrp": ("subgrupo", "do"),
    "sub": ("sub", ""), "subclas": ("subclasse", "da"), "conj": ("conjunto", "do"), "lista": ("lista", "da"),
    "tabela": ("tabela", "da"), "menu": ("menu", "do"), "pagina": ("página", "da"), "titulo": ("título", "do"), "title": ("título", "do"),
    "tit": ("título", "do"), "termo": ("termo", "do"), "objeto": ("objeto", "do"), "tarefa": ("tarefa", "da"), "fase": ("fase", "da"),
    "processo": ("processo", "do"), "proc": ("processo", "do"), "evento": ("evento", "do"), "acao": ("ação", "da"),
    "funcao": ("função", "da"), "cargo": ("cargo", "do"), "setor": ("setor", "do"), "area": ("área", "da"), "segmento": ("segmento", "do"),
    "projeto": ("projeto", "do"), "plano": ("plano", "do"), "contrato": ("contrato", "do"), "documento": ("documento", "do"),
    "doc": ("documento", "do"), "docto": ("documento", "do"), "docmto": ("documento", "do"), "protocolo": ("protocolo", "do"),
    "prot": ("protocolo", "do"), "protoc": ("protocolo", "do"), "recibo": ("recibo", "do"), "registro": ("registro", "do"),
    "reg": ("registro", "do"), "referencia": ("referência", "da"), "referenc": ("referência", "da"), "ref": ("referência", "da"),
    # pessoas e cadastros
    "empresa": ("empresa", "da"), "emp": ("empresa", "da"), "empr": ("empresa", "da"), "filial": ("filial", "da"),
    "loja": ("loja", "da"), "matriz": ("matriz", "da"), "estab": ("estabelecimento", "do"),
    "cliente": ("cliente", "do"), "cli": ("cliente", "do"), "client": ("cliente", "do"),
    "fornec": ("fornecedor", "do"), "forn": ("fornecedor", "do"), "for": ("fornecedor", "do"),
    "usuario": ("usuário", "do"), "usu": ("usuário", "do"), "usua": ("usuário", "do"), "user": ("usuário", "do"),
    "operador": ("operador", "do"), "operad": ("operador", "do"), "atendente": ("atendente", "do"), "atend": ("atendente", "do"),
    "vendedor": ("vendedor", "do"), "vend": ("vendedor", "do"), "gerente": ("gerente", "do"), "colaborador": ("colaborador", "do"),
    "colab": ("colaborador", "do"), "entregador": ("entregador", "do"), "negociador": ("negociador", "do"), "tecnico": ("técnico", "do"),
    "contato": ("contato", "do"), "pessoa": ("pessoa", "da"), "pes": ("pessoa", "da"), "apelido": ("apelido", "do"),
    "conveniado": ("conveniado", "do"), "conv": ("convênio", "do"), "convenio": ("convênio", "do"), "credenciado": ("credenciado", ""),
    "fabricante": ("fabricante", "do"), "fabric": ("fabricante", "do"), "fabr": ("fabricante", "do"), "fab": ("fabricante", "do"),
    "fabrica": ("fábrica", "da"), "lab": ("laboratório", "do"), "transp": ("transportadora", "da"), "repres": ("representante", "do"),
    "rep": ("representante", "do"), "contado": ("contador", "do"), "medico": ("médico", "do"), "med": ("médico", "do"),
    "crm": ("CRM do médico", "do"), "crf": ("CRF do farmacêutico", "do"), "conselho": ("conselho profissional", "do"),
    "matricula": ("matrícula", "da"), "matric": ("matrícula", "da"), "salario": ("salário", "do"), "renda": ("renda", "da"),
    "ocupacao": ("ocupação", "da"), "atividade": ("atividade", "da"), "ativid": ("atividade", "da"), "atv": ("atividade", "da"),
    "nasc": ("nascimento", "do"), "rg": ("RG", "do"), "cpf": ("CPF", "do"), "cnpj": ("CNPJ", "do"), "ie": ("inscrição estadual", "da"),
    "im": ("inscrição municipal", "da"), "cnae": ("CNAE", "do"), "crc": ("CRC do contador", "do"),
    # endereço e contato
    "endereco": ("endereço", "do"), "ender": ("endereço", "do"), "end": ("endereço", "do"), "complemento": ("complemento", "do"),
    "compl": ("complemento", "do"), "cpl": ("complemento", "do"), "bairro": ("bairro", "do"), "cidade": ("cidade", "da"),
    "cid": ("cidade", "da"), "mun": ("município", "do"), "uf": ("UF (estado)", "da"), "estado": ("estado", "do"),
    "cep": ("CEP", "do"), "pais": ("país", "do"), "regiao": ("região", "da"), "rota": ("rota", "da"),
    "telefone": ("telefone", "do"), "fone": ("telefone", "do"), "tele": ("telefone", "do"), "celular": ("celular", "do"),
    "ddd": ("DDD", "do"), "ramal": ("ramal", "do"), "fax": ("fax", "do"), "whats": ("WhatsApp", "do"), "site": ("site", "do"),
    "web": ("web", ""), "smtp": ("servidor SMTP", "do"),
    # produto e estoque
    "produto": ("produto", "do"), "prod": ("produto", "do"), "prd": ("produto", "do"), "pro": ("produto", "do"),
    "item": ("item", "do"), "itens": ("itens", "dos"), "ite": ("item", "do"), "it": ("item", "do"),
    "insumo": ("insumo", "do"), "ins": ("insumo", "do"), "estoque": ("estoque", "do"), "estoq": ("estoque", "do"),
    "unid": ("unidade", "da"), "unidade": ("unidade", "da"), "und": ("unidade", "da"), "un": ("unidade", "da"), "uni": ("unidade", "da"),
    "marca": ("marca", "da"), "embalagem": ("embalagem", "da"), "emb": ("embalagem", "da"), "fracao": ("fração", "da"),
    "frac": ("fracionado", ""), "apresentacao": ("apresentação", "da"), "apresent": ("apresentação", "da"),
    "validade": ("validade", "da"), "valid": ("validade", "da"), "vct": ("vencimento", "do"), "venc": ("vencimento", "do"),
    "vencido": ("vencido", ""), "garantia": ("garantia", "da"), "garant": ("garantia", "da"),
    "ean": ("código de barras (EAN)", "do"), "gtin": ("código de barras (GTIN)", "do"), "bar": ("barras", "de"),
    "codbar": ("código de barras", "do"), "etiqueta": ("etiqueta", "da"), "etiq": ("etiqueta", "da"), "etq": ("etiqueta", "da"),
    "giro": ("giro", "do"), "inventario": ("inventário", "do"), "invent": ("inventário", "do"), "inv": ("inventário", "do"),
    "dcb": ("DCB (denominação comum brasileira)", "da"), "pmc": ("preço máximo ao consumidor (PMC)", "do"),
    "antibio": ("antibiótico", ""), "controlado": ("controlado", ""), "manip": ("manipulado", ""), "receita": ("receita", "da"),
    "presc": ("prescrição", "da"), "prescr": ("prescrição", "da"), "sngpc": ("SNGPC", "do"), "anv": ("Anvisa", "da"),
    "glp1": ("GLP-1", "do"), "formula": ("fórmula", "da"), "lacre": ("lacre", "do"), "placa": ("placa", "da"),
    "veiculo": ("veículo", "do"), "romaneio": ("romaneio", "do"), "promocao": ("promoção", "da"), "promo": ("promoção", "da"),
    "encarte": ("encarte", "do"), "premio": ("prêmio", "do"), "prem": ("prêmio", "do"), "bonus": ("bônus", "do"),
    "fidelidade": ("fidelidade", "da"), "fid": ("fidelidade", "da"), "clube": ("clube", "do"), "sorteio": ("sorteio", "do"),
    # venda, caixa e financeiro
    "venda": ("venda", "da"), "ven": ("venda", "da"), "vnd": ("venda", "da"), "vda": ("venda", "da"), "vd": ("venda", "da"),
    "compra": ("compra", "da"), "comp": ("compra", "da"), "compr": ("compra", "da"), "pedido": ("pedido", "do"), "ped": ("pedido", "do"),
    "orc": ("orçamento", "do"), "prevenda": ("pré-venda", "da"), "preven": ("pré-venda", "da"),
    "caixa": ("caixa", "do"), "cxa": ("caixa", "do"), "cx": ("caixa", "do"), "estacao": ("estação", "da"), "estac": ("estação", "da"),
    "terminal": ("terminal", "do"), "pdv": ("PDV", "do"), "ecf": ("ECF (impressora fiscal)", "do"), "impressora": ("impressora", "da"),
    "impr": ("impressão", "da"), "impresso": ("impresso", ""), "cupom": ("cupom", "do"), "cup": ("cupom", "do"),
    "coo": ("COO (contador de ordem de operação)", "do"), "ccf": ("CCF (contador de cupom fiscal)", "do"),
    "crz": ("CRZ (contador de redução Z)", "do"), "cro": ("CRO (contador de reinício de operação)", "do"),
    "gnf": ("GNF (contador geral não fiscal)", "do"), "mfd": ("MFD (memória de fita-detalhe)", "da"), "rz": ("redução Z", "da"),
    "moeda": ("moeda (forma de pagamento)", "da"), "forma": ("forma", "da"), "formapg": ("forma de pagamento", "da"),
    "fp": ("forma de pagamento", "da"), "fpg": ("forma de pagamento", "da"), "pgto": ("pagamento", "do"), "pagto": ("pagamento", "do"),
    "pag": ("pagamento", "do"), "pg": ("pagamento", "do"), "pgt": ("pagamento", "do"), "pago": ("pago", ""), "paga": ("paga", ""),
    "condpg": ("condição de pagamento", "da"), "condicao": ("condição", "da"), "parcela": ("parcela", "da"), "parc": ("parcela", "da"),
    "par": ("parcela", "da"), "parcial": ("parcial", ""), "troco": ("troco", "do"), "sangria": ("sangria", "da"),
    "cartao": ("cartão", "do"), "cart": ("cartão", "do"), "car": ("cartão", "do"), "bandeira": ("bandeira do cartão", "da"),
    "band": ("bandeira do cartão", "da"), "adminis": ("administradora", "da"), "adm": ("administradora", "da"),
    "adq": ("adquirente", "da"), "operadora": ("operadora", "da"), "tef": ("TEF", "do"), "nsu": ("NSU da transação", "do"),
    "transacao": ("transação", "da"), "transac": ("transação", "da"), "trans": ("transação", "da"), "tran": ("transação", "da"),
    "trn": ("transação", "da"), "aut": ("autorização", "da"), "autorizacao": ("autorização", "da"), "pix": ("Pix", "do"),
    "cheque": ("cheque", "do"), "cheq": ("cheque", "do"), "chq": ("cheque", "do"), "cmc7": ("código CMC-7 do cheque", "do"),
    "boleto": ("boleto", "do"), "bol": ("boleto", "do"), "banco": ("banco", "do"), "bco": ("banco", "do"), "banc": ("bancário", ""),
    "agencia": ("agência", "da"), "agenc": ("agência", "da"), "ag": ("agência", "da"), "conta": ("conta", "da"), "cta": ("conta", "da"),
    "ctabco": ("conta bancária", "da"), "ispb": ("ISPB do banco", "do"), "deposito": ("depósito", "do"),
    "carteira": ("carteira", "da"), "credito": ("crédito", "do"), "cred": ("crédito", "do"), "cre": ("crédito", "do"),
    "debito": ("débito", "do"), "deb": ("débito", "do"), "dpl": ("duplicata", "da"), "dup": ("duplicata", "da"),
    "juros": ("juros", "dos"), "juro": ("juros", "dos"), "jur": ("juros", "dos"), "multa": ("multa", "da"),
    "desconto": ("desconto", "do"), "acr": ("acréscimo", "do"), "acrescimo": ("acréscimo", "do"), "abat": ("abatimento", "do"),
    "comissao": ("comissão", "da"), "comis": ("comissão", "da"), "com": ("comissão", "da"), "repasse": ("repasse", "do"),
    "lucro": ("lucro", "do"), "receb": ("recebimento", "do"), "rec": ("recebimento", "do"), "recebido": ("recebido", ""),
    "estorno": ("estorno", "do"), "devol": ("devolução", "da"), "dev": ("devolução", "da"), "troca": ("troca", "da"),
    "vale": ("vale", "do"), "recarga": ("recarga", "da"), "bordero": ("borderô", "do"), "carne": ("carnê", "do"),
    "financ": ("financeiro", ""), "fin": ("financeiro", ""), "fat": ("faturamento", "do"), "faturamento": ("faturamento", "do"),
    "lcto": ("lançamento", "do"), "lct": ("lançamento", "do"), "centro": ("centro de custo", "do"), "ctb": ("contábil", ""),
    "dre": ("DRE", "do"), "conc": ("conciliação", "da"), "conci": ("conciliação", "da"), "conciliado": ("conciliado", ""),
    "concilia": ("conciliação", "da"), "acerto": ("acerto", "do"), "ajuste": ("ajuste", "do"), "aju": ("ajuste", "do"),
    "aj": ("ajuste", "do"), "pbm": ("PBM (programa de benefício em medicamentos)", "do"), "epharma": ("ePharma", "da"),
    "ifood": ("iFood", "do"), "entrega": ("entrega", "da"), "frete": ("frete", "do"), "fre": ("frete", "do"),
    "remessa": ("remessa", "da"), "rem": ("remessa", "da"), "retorno": ("retorno", "do"),
    # fiscal
    "nf": ("nota fiscal", "da"), "nfe": ("NF-e", "da"), "nfce": ("NFC-e", "da"), "nfs": ("nota fiscal de serviço", "da"),
    "nfse": ("NFS-e", "da"), "nfisc": ("nota fiscal", "da"), "fisc": ("fiscal", ""), "fiscal": ("fiscal", ""),
    "mdfe": ("MDF-e", "do"), "dfe": ("documento fiscal eletrônico", "do"), "rps": ("RPS", "do"), "paf": ("PAF-ECF", "do"),
    "icms": ("ICMS", "do"), "ipi": ("IPI", "do"), "pis": ("PIS", "do"), "cofins": ("COFINS", "do"), "cof": ("COFINS", "do"),
    "iss": ("ISS", "do"), "irrf": ("IRRF", "do"), "csll": ("CSLL", "da"), "inss": ("INSS", "do"), "ii": ("imposto de importação", "do"),
    "ibs": ("IBS", "do"), "cbs": ("CBS", "da"), "ibscbs": ("IBS/CBS", "do"), "fcp": ("FCP (fundo de combate à pobreza)", "do"),
    "fcpst": ("FCP da substituição tributária", "do"), "mva": ("MVA (margem de valor agregado)", "da"),
    "cst": ("CST (situação tributária)", "do"), "csosn": ("CSOSN", "do"), "cfop": ("CFOP", "do"), "cfopst": ("CFOP da substituição tributária", "do"),
    "ncm": ("NCM", "do"), "cest": ("CEST", "do"), "tipi": ("TIPI", "da"), "trib": ("tributação", "da"), "trb": ("tributação", "da"),
    "tributacao": ("tributação", "da"), "imposto": ("imposto", "do"), "impostos": ("impostos", "dos"), "imp": ("imposto", "do"),
    "substrib": ("substituição tributária", "da"), "red": ("redução", "da"), "redbase": ("redução da base de cálculo", "da"),
    "redutor": ("redutor", "do"), "isento": ("isento", ""), "ise": ("isento", ""), "difer": ("diferimento", "do"),
    "dif": ("diferencial", "do"), "deson": ("desoneração", "da"), "monofasica": ("monofásica", ""), "regime": ("regime tributário", "do"),
    "simples": ("Simples Nacional", "do"), "sn": ("Simples Nacional", "do"), "natureza": ("natureza da operação", "da"),
    "natur": ("natureza da operação", "da"), "nat": ("natureza", "da"), "operacao": ("operação", "da"), "operac": ("operação", "da"),
    "oper": ("operação", "da"), "op": ("operação", "da"), "ope": ("operação", "da"), "amparo": ("amparo legal", "do"),
    "benef": ("benefício fiscal", "do"), "csc": ("CSC (código de segurança do contribuinte)", "do"), "cert": ("certificado digital", "do"),
    "pfx": ("certificado PFX", "do"), "amb": ("ambiente", "do"), "emit": ("emitente", "do"), "emi": ("emissão", "da"),
    "emite": ("emite", ""), "dest": ("destinatário", "do"), "destinat": ("destinatário", "do"), "destino": ("destino", "do"),
    "orig": ("origem", "da"), "origem": ("origem", "da"), "ori": ("origem", "da"), "rej": ("rejeição", "da"), "canc": ("cancelamento", "do"),
    "ciencia": ("ciência", "da"), "autxml": ("autorizados a baixar o XML", "dos"), "tom": ("tomador", "do"), "serv": ("serviço", "do"),
    "servico": ("serviço", "do"), "fci": ("FCI (ficha de conteúdo de importação)", "da"), "anp": ("ANP", "da"),
    "codidnac": ("código de identificação nacional", "do"), "clasfisc": ("classificação fiscal", "da"), "tpnf": ("tipo da nota fiscal", "do"),
    # tempo e controle
    "ini": ("inicial", ""), "inicio": ("início", "do"), "fim": ("final", ""), "final": ("final", ""), "ult": ("último(a)", ""),
    "ant": ("anterior", ""), "atu": ("atual", ""), "atual": ("atual", ""), "prox": ("próximo(a)", ""), "pri": ("primeiro(a)", ""),
    "max": ("máximo", ""), "min": ("mínimo", ""), "pad": ("padrão", ""), "padrao": ("padrão", ""), "def": ("padrão", ""),
    "inc": ("inclusão", "da"), "alt": ("alteração", "da"), "exc": ("exclusão", "da"), "cad": ("cadastro", "do"),
    "cadastro": ("cadastro", "do"), "atualiz": ("atualização", "da"), "modif": ("modificação", "da"), "editado": ("editado", ""),
    "sinc": ("sincronização", "da"), "envio": ("envio", "do"), "env": ("envio", "do"), "receb2": ("recebimento", "do"),
    "conf": ("conferência", "da"), "confer": ("conferência", "da"), "conferido": ("conferido", ""), "lib": ("liberação", "da"),
    "liberada": ("liberada", ""), "blq": ("bloqueio", "do"), "bloq": ("bloqueio", "do"), "bl": ("bloqueio", "do"),
    "apr": ("aprovação", "da"), "aprov": ("aprovação", "da"), "apro": ("aprovação", "da"), "sol": ("solicitação", "da"),
    "solic": ("solicitação", "da"), "req": ("requisição", "da"), "prev": ("previsão", "da"), "previs": ("previsão", "da"),
    "pend": ("pendente", ""), "ativo": ("ativo", ""), "ativa": ("ativa", ""), "visivel": ("visível", ""), "obrig": ("obrigatório", ""),
    "exige": ("exige", ""), "permite": ("permite", ""), "usa": ("usa", ""), "gera": ("gera", ""), "mostra": ("mostra", ""),
    "abre": ("abre", ""), "fecha": ("fecha", ""), "fec": ("fechamento", "do"), "fechamento": ("fechamento", "do"),
    "abertura": ("abertura", "da"), "ab": ("abertura", "da"), "reabr": ("reabertura", "da"), "zera": ("zera", ""),
    "calc": ("cálculo", "do"), "arred": ("arredondamento", "do"), "arredond": ("arredondamento", "do"), "trunca": ("trunca", ""),
    "controle": ("controle", "do"), "ctrl": ("controle", "do"), "contr": ("controle", "do"), "ctr": ("controle", "do"),
    "sistema": ("sistema", "do"), "sist": ("sistema", "do"), "sis": ("sistema", "do"), "backup": ("backup", "do"),
    "bd": ("banco de dados", "do"), "db": ("banco de dados", "do"), "fila": ("fila", "da"), "app": ("aplicativo", "do"),
    "aplic": ("aplicação", "da"), "aplicacao": ("aplicação", "da"), "impressao": ("impressão", "da"), "via": ("via", "da"),
    "vias": ("vias", "das"), "qrcode": ("QR Code", "do"), "lgpd": ("LGPD", "da"), "digest": ("resumo (digest)", "do"),
    "payload": ("conteúdo (payload)", "do"), "edi": ("EDI", "do"), "scan": ("leitura (scanner)", "da"),
    "entr": ("entrada", "da"), "entrada": ("entrada", "da"), "saida": ("saída", "da"), "sai": ("saída", "da"),
    "transf": ("transferência", "da"), "mov": ("movimento", "do"), "movto": ("movimento", "do"), "perda": ("perda", "da"),
    "local": ("local", "do"), "loc": ("local", "do"), "rede": ("rede", "da"), "grau": ("grau", "do"), "perfil": ("perfil", "do"),
    "perf": ("perfil", "do"), "todos": ("todos", ""), "novo": ("novo", ""), "nov": ("novo", ""), "principal": ("principal", ""),
    "pai": ("pai", ""), "filtro": ("filtro", "do"), "rank": ("ranking", "do"), "ranking": ("ranking", "do"), "selo": ("selo", "do"),
    "vinculo": ("vínculo", "do"), "vinc": ("vínculo", "do"), "lig": ("ligação", "da"), "assoc": ("associação", "da"),
    "indicacao": ("indicação", "da"), "pesq": ("pesquisa", "da"), "consulta": ("consulta", "da"), "cons": ("consulta", "da"),
    "agenda": ("agenda", "da"), "tarifa": ("tarifa", "da"), "tar": ("tarifa", "da"), "folha": ("folha", "da"), "livro": ("livro", "do"),
    "pagina2": ("página", "da"), "gov": ("governo", "do"), "orgao": ("órgão", "do"), "cobr": ("cobrança", "da"), "cob": ("cobrança", "da"),
    "negoc": ("negociação", "da"), "acessa": ("acessa", ""), "acesso": ("acesso", "do"), "ace": ("acesso", "do"), "sel": ("seleção", "da"),
    "tecla": ("tecla", "da"), "atalho": ("atalho", "do"), "sim": ("sim/não", ""), "m3": ("m³", ""),
    "fornecedor": ("fornecedor", "do"), "pen": ("pendente", ""), "ajus": ("ajuste", "do"), "chav": ("chave", "da"), "original": ("original", ""),
    "direto": ("direto", ""), "justif": ("justificativa", "da"), "bxa": ("baixa", "da"), "baixa": ("baixa", "da"),
    "ccusto": ("centro de custo", "do"), "minu": ("minuto", "do"), "teto": ("teto", "do"), "corresp": ("correspondência", "da"),
    "secret": ("segredo", "do"), "ban": ("bandeira", "da"), "bin": ("BIN do cartão", "do"), "capital": ("capital", "do"),
    "avisos": ("avisos", "dos"), "aviso": ("aviso", "do"), "sep": ("separação", "da"), "antecipacao": ("antecipação", "da"),
    "atualiza": ("atualização", "da"), "emitente": ("emitente", "do"), "estorna": ("estorna", ""), "permite2": ("permite", ""),
    "pdif": ("percentual do diferimento", "do"), "vdif": ("valor do diferimento", "do"),
}

# siglas ambíguas: a primeira leitura vai na sugestão e a observação avisa a outra possibilidade
AMBIGUAS = {
    "ent": (("entrada", "da"), "ent pode ser entrada ou entrega"),
    "ret": (("retenção", "da"), "ret pode ser retenção, retorno ou retirada"),
    "est": (("estoque", "do"), "est pode ser estoque, estado ou estorno"),
    "des": (("desconto", "do"), "des pode ser desconto, destino ou descrição"),
    "st": (("situação", "da"), "st pode ser situação (status) ou substituição tributária"),
    "at": (("atualização", "da"), "at pode ser atualização ou atendimento"),
    "conv": (("convênio", "do"), "conv pode ser convênio ou conversão"),
    "exp": (("exportação", "da"), "exp pode ser exportação ou expedição"),
    "exi": (("exibição", "da"), "exi pode ser exibição ou exigência"),
    "efe": (("efetivo", ""), "efe pode ser efetivo ou efetivação"),
    "sug": (("sugestão", "da"), "sug pode ser sugestão ou sugerido"),
    "rev": (("revenda", "da"), "rev pode ser revenda ou revisão"),
    "pres": (("presumido", ""), "pres pode ser presumido ou presente"),
    "out": (("outros", ""), "out pode ser outros ou saída"),
    "int": (("integração", "da"), "int pode ser integração, interno ou inteiro"),
    "ext": (("externo", ""), "ext pode ser externo ou extrato"),
    "tr": (("transação", "da"), "tr pode ser transação, transferência ou tributação"),
    "cv": (("comprovante de venda", "do"), "cv pode ser comprovante de venda ou conversão"),
    "cf": (("cupom fiscal", "do"), "cf pode ser cupom fiscal ou confirmação"),
    "cc": (("cartão de crédito", "do"), "cc pode ser cartão de crédito, conta corrente ou centro de custo"),
    "liq": (("líquido", ""), "liq pode ser líquido ou liquidação"),
    "bru": (("bruto", ""), "bru = bruto"), "bruto": (("bruto", ""), ""),
    "seg": (("seguro", "do"), "seg pode ser seguro ou segundo"),
    "exige2": (("exige", ""), ""),
    "tp2": (("tipo", "do"), ""),
    "re": (("registro de exportação", "do"), "re é incerto"),
    "dep": (("dependente", "do"), "dep pode ser dependente, depósito ou departamento"),
    "rv": (("resumo de vendas", "do"), "rv pode ser resumo de vendas"),
    "qb": (("quebra", "da"), "qb pode ser quebra"),
    "dlo": (("DLO", "do"), "dlo é incerto"),
    "atc": (("ATC (classificação de medicamento)", "do"), "atc é incerto"),
    "con": (("consulta", "da"), "con pode ser consulta, conta ou convênio"),
    "mat": (("material", "do"), "mat pode ser material ou matriz"),
    "ue": (("unidade de entrada", "da"), "ue é incerto"),
    "rn": (("regra de negócio", "da"), "rn é incerto"),
    "sb": (("subgrupo", "do"), "sb é incerto"),
    "co": (("código", "do"), "co é incerto"),
    "fe": (("fidelidade", "da"), "fe é incerto"),
}

# nomes inteiros conhecidos (ganham de qualquer montagem pelas partes): {"nome_da_coluna": "Descrição"}.
# Ficam em coletor/saida/nomes-conhecidos.json, fora do git: são nomes reais do banco do sistema mapeado.
_NOMES_ARQ = Path(__file__).resolve().parent / "saida" / "nomes-conhecidos.json"
NOMES: dict[str, str] = json.loads(_NOMES_ARQ.read_text(encoding="utf-8")) if _NOMES_ARQ.exists() else {}

ROTULO = {"banco": "banco", "alta": "alta", "media": "média", "baixa": "baixa", "": "sem sugestão"}


def parte(tok: str):
    """(texto, preposição, observação, conhecida, ambígua) de uma parte do nome."""
    if tok in G:
        return (*G[tok], "", True, False)
    if tok in AMBIGUAS:
        (txt, prep), obs = AMBIGUAS[tok]
        return txt, prep, obs, True, bool(obs)
    for corte in (2, 1):  # plural: produtos -> produto, fornecedores -> fornecedor
        if len(tok) > 4 and tok.endswith("es"[-corte:]) and tok[:-corte] in G and G[tok[:-corte]][1]:
            txt, prep = G[tok[:-corte]]
            return plural(txt), prep.replace("do", "dos").replace("da", "das") if prep in ("do", "da") else prep, "", True, False
    m = re.fullmatch(r"([a-z]+?)(\d+)", tok)  # fone2, prazo3, campo10, pes1
    if m and (m.group(1) in G or m.group(1) in AMBIGUAS):
        txt, prep, obs, _, amb = parte(m.group(1))
        return f"{txt} {m.group(2)}", prep, obs, True, amb
    return f"[{tok}]", "de", "", False, False


def plural(txt: str) -> str:
    """Plural simples para o texto do glossário (só a primeira palavra: código do produto -> códigos do produto)."""
    p, _, resto = txt.partition(" ")
    if p.endswith("ão"):
        p = p[:-2] + "ões"
    elif p.endswith(("r", "z")):
        p += "es"
    elif p.endswith("l"):
        p = p[:-1] + "is"
    elif not p.endswith("s"):
        p += "s"
    return f"{p} {resto}".strip()


def segmentar(nome: str) -> list[str] | None:
    """Quebra um nome colado (qtdmax -> qtd max) pelas abreviações conhecidas; None se não fechar."""
    conhecidas = set(G) | set(AMBIGUAS)
    melhor: dict[int, list[str]] = {0: []}
    for i in range(1, len(nome) + 1):
        for j in range(max(0, i - 14), i):
            pedaco = nome[j:i]
            if j in melhor and pedaco in conhecidas and len(pedaco) >= 2:
                cand = melhor[j] + [pedaco]
                if i not in melhor or len(cand) < len(melhor[i]):
                    melhor[i] = cand
    return melhor.get(len(nome))


VERBOS = {"usa", "gera", "exige", "mostra", "abre", "fecha", "zera", "emite", "permite", "acessa", "trunca", "estorna"}
FISCAIS = {"icms", "pis", "cofins", "cof", "ipi", "fcp", "base", "bc", "aliq", "alq", "mva", "cfop", "red", "cst"}
LUGARES = {"bairro", "cidade", "cid", "uf", "mun", "cep", "end", "endereco", "pais", "loja", "empresa", "emp"}
NUCLEOS_NO_FIM = {"id", "cod", "codigo", "num", "nro", "seq"}


def contexto(partes: list[str]) -> list[tuple]:
    """Lê cada parte usando as vizinhas: st perto de imposto = substituição tributária, des perto de endereço = destino."""
    if len(partes) > 1 and partes[-1] in NUCLEOS_NO_FIM and partes[0] not in NUCLEOS_NO_FIM:
        partes = [partes[-1]] + partes[:-1]  # user_id -> identificador do usuário
    fiscal, lugar = bool(FISCAIS & set(partes)), bool(LUGARES & set(partes))
    lidas = []
    for p in partes:
        if p == "st" and fiscal:
            lidas.append(("substituição tributária", "da", "", True, False))
        elif p == "des" and lugar:
            lidas.append(("destino", "do", "", True, False))
        else:
            lidas.append(parte(p))
    return lidas


def montar(partes: list[str]) -> tuple[str, str, str]:
    """(descrição, confiança, observação) montada a partir das partes."""
    partes = [p for p in partes if p]
    lidas = contexto(partes)
    if not lidas:
        return "", "", ""
    conhecidas = sum(1 for x in lidas if x[3])
    if conhecidas == 0:
        return "", "", ""
    verbo = partes[0] in VERBOS
    txt = f"indica se {lidas[0][0]}" if verbo else lidas[0][0]
    for i, (t, prep, *_) in enumerate(lidas[1:]):
        # depois de verbo ou de adjetivo no começo (último, máximo...) o complemento entra direto
        direto = i == 0 and (verbo or not lidas[0][1])
        txt += f" {t}" if direto or not prep else f" {prep} {t}"
    obs = "; ".join(dict.fromkeys(x[2] for x in lidas if x[2]))
    if conhecidas < len(lidas):
        conf = "baixa"
    elif any(x[4] for x in lidas) or len(lidas) > 3:
        conf = "media"
    else:
        conf = "alta"
    return txt[:1].upper() + txt[1:], conf, obs


def sugerir_coluna(nome: str) -> tuple[str, str, str]:
    n = nome.lower()
    if n in NOMES:
        return NOMES[n], ("alta" if NOMES[n] else ""), ""
    partes = [p for p in n.split("_") if p]
    if len(partes) == 1 and n not in G and n not in AMBIGUAS and not re.fullmatch(r"[a-z]+\d+", n):
        seg = segmentar(n)
        if seg and len(seg) > 1:
            desc, conf, obs = montar(seg)
            return desc, ("baixa" if conf == "baixa" else "media"), ("; ".join(x for x in (f"lido como {' + '.join(seg)}", obs) if x))
    return montar(partes)


SUFIXOS = {"cab": "o cabeçalho de", "item": "os itens de", "itens": "os itens de", "mov": "os movimentos de",
           "log": "o registro (log) de", "tmp": "os dados temporários de", "temp": "os dados temporários de",
           "hist": "o histórico de", "ctrl": "o controle de", "config": "a configuração de", "cfg": "a configuração de",
           "param": "os parâmetros de", "det": "os detalhes de", "bkp": "a cópia de segurança de", "backup": "a cópia de segurança de"}


def sugerir_tabela(nome: str, sistema: str) -> tuple[str, str, str]:
    n = nome.lower()
    partes = [p for p in n.split("_") if p]
    abertura = "os dados de"
    if len(partes) > 1 and partes[-1] in SUFIXOS:
        abertura, partes = SUFIXOS[partes[-1]], partes[:-1]
    elif len(partes) > 1 and partes[0] in ("log", "hist"):
        abertura, partes = SUFIXOS[partes[0]], partes[1:]
    if len(partes) == 1 and partes[0] not in G and partes[0] not in AMBIGUAS:
        seg = segmentar(partes[0])
        if seg and len(seg) > 1:
            partes = seg
    desc, conf, obs = montar(partes)
    if not desc:
        return "", "", ""
    if len(partes) == 1 and abertura == "os dados de" and conf != "baixa":
        desc = plural(desc)
    if conf == "alta" and len(partes) > 2:
        conf = "media"
    return f"Armazena {abertura} {desc[:1].lower() + desc[1:]} do {sistema}", conf, obs


def ler_modulos() -> dict[str, dict]:
    modulos = {}
    pastas = [p for p in SAIDA.iterdir() if p.is_dir() and (p / "colunas.csv").exists()]
    ordem = list(MODULOS)
    for pasta in sorted(pastas, key=lambda p: next((ordem.index(m) for m in ordem if m in p.name.lower()), 9)):
        mod = next((m for m in MODULOS if m in pasta.name.lower()), None)
        if not mod:
            print(f"pulando {pasta.name}: o nome da pasta não diz o módulo (pdv, adm ou fin)")
            continue
        tabelas = list(csv.DictReader(open(pasta / "tabelas.csv", encoding="utf-8-sig")))
        colunas = list(csv.DictReader(open(pasta / "colunas.csv", encoding="utf-8-sig")))
        modulos[mod] = {"tabelas": tabelas, "colunas": colunas}
    return modulos


VERDE, AMARELO, LARANJA, CINZA, AZUL = "E2F0D9", "FFF2CC", "FCE4D6", "EDEDED", "DDEBF7"


def formatar(ws, larguras: list[int], col_desc: int, col_conf: int, col_ok: int, linhas: int):
    cab = Font(bold=True, color="FFFFFF")
    for c in ws[1]:
        c.font, c.fill = cab, PatternFill("solid", fgColor="00857F")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    letra_desc = ws.cell(1, col_desc).column_letter
    letra_conf = ws.cell(1, col_conf).column_letter
    letra_ok = ws.cell(1, col_ok).column_letter
    for row in ws.iter_rows(min_row=2, min_col=col_desc, max_col=col_desc):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    fim = linhas + 1
    for valor, cor in (("banco", AZUL), ("alta", VERDE), ("média", AMARELO), ("baixa", LARANJA), ("sem sugestão", CINZA)):
        ws.conditional_formatting.add(f"{letra_conf}2:{letra_conf}{fim}",
                                      FormulaRule(formula=[f'${letra_conf}2="{valor}"'], fill=PatternFill("solid", fgColor=cor)))
    ws.conditional_formatting.add(f"{letra_ok}2:{letra_ok}{fim}",
                                  FormulaRule(formula=[f'UPPER(${letra_ok}2)="S"'], fill=PatternFill("solid", fgColor=VERDE)))
    dv = DataValidation(type="list", formula1='"S,N"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{letra_ok}2:{letra_ok}{fim}")
    ws.column_dimensions[letra_desc].width = larguras[col_desc - 1]


def main(destino: Path):
    modulos = ler_modulos()
    if not modulos:
        sys.exit("nenhum catálogo em coletor/saida (rode o coletar.py antes)")
    wb = Workbook()
    leia = wb.active
    leia.title = "Leia-me"

    # tabelas
    wt = wb.create_sheet("Tabelas")
    wt.append(["Módulo", "Tabela", "Descrição (edite aqui)", "Conferido (S/N)", "Confiança da sugestão", "Observação",
               "Linhas (aprox.)", "Colunas"])
    qt_colunas = defaultdict(int)
    for mod, d in modulos.items():
        for c in d["colunas"]:
            qt_colunas[(mod, c["TABLE_NAME"])] += 1
    n_tab = 0
    resumo = defaultdict(lambda: defaultdict(int))
    for mod, d in modulos.items():
        for t in sorted(d["tabelas"], key=lambda r: r["TABLE_NAME"].lower()):
            coment = (t.get("TABLE_COMMENT") or "").strip()
            if coment:
                desc, conf, obs = coment[:1].upper() + coment[1:].lower(), "banco", "comentário que já existe no banco"
            else:
                desc, conf, obs = sugerir_tabela(t["TABLE_NAME"], MODULOS[mod])
            resumo["Tabelas"][ROTULO[conf]] += 1
            linhas = t.get("linhas_estimadas") or ""
            wt.append([mod.upper(), t["TABLE_NAME"], desc, "", ROTULO[conf], obs, int(linhas) if linhas.isdigit() else linhas,
                       qt_colunas[(mod, t["TABLE_NAME"])]])
            n_tab += 1
    formatar(wt, [8, 30, 70, 11, 13, 40, 12, 9], 3, 5, 4, n_tab)

    # colunas: um nome, uma descrição (vale para todas as tabelas em que o nome aparece)
    wc = wb.create_sheet("Colunas")
    wc.append(["Coluna", "Descrição (edite aqui)", "Conferido (S/N)", "Confiança da sugestão", "Observação",
               "Aparece em (tabelas)", "Módulos", "Exemplos de tabelas", "Tipos"])
    usos: dict[str, dict] = defaultdict(lambda: {"tabelas": [], "modulos": set(), "tipos": set()})
    excecoes = []
    for mod, d in modulos.items():
        for c in d["colunas"]:
            u = usos[c["COLUMN_NAME"].lower()]
            u["tabelas"].append(c["TABLE_NAME"])
            u["modulos"].add(mod.upper())
            u["tipos"].add(c["COLUMN_TYPE"])
            coment = (c.get("COLUMN_COMMENT") or "").strip()
            if coment:
                excecoes.append([mod.upper(), c["TABLE_NAME"], c["COLUMN_NAME"], coment[:1].upper() + coment[1:].lower(), "", "banco"])
    ordem = sorted(usos.items(), key=lambda kv: (-len(kv[1]["tabelas"]), kv[0]))
    for nome, u in ordem:
        desc, conf, obs = sugerir_coluna(nome)
        resumo["Colunas"][ROTULO[conf]] += 1
        exemplos = ", ".join(sorted(set(u["tabelas"]))[:6]) + (" …" if len(set(u["tabelas"])) > 6 else "")
        wc.append([nome, desc, "", ROTULO[conf], obs, len(u["tabelas"]), ", ".join(sorted(u["modulos"])), exemplos,
                   ", ".join(sorted(u["tipos"]))[:120]])
    formatar(wc, [22, 60, 11, 13, 40, 11, 10, 50, 26], 2, 4, 3, len(ordem))

    # exceções: quando o mesmo nome quer dizer outra coisa numa tabela específica
    we = wb.create_sheet("Exceções")
    we.append(["Módulo", "Tabela", "Coluna", "Descrição (edite aqui)", "Conferido (S/N)", "Confiança da sugestão"])
    for linha in excecoes:
        we.append(linha)
    resumo["Exceções"]["banco"] = len(excecoes)
    formatar(we, [8, 28, 22, 70, 11, 13], 4, 6, 5, max(len(excecoes), 200))

    # leia-me
    linhas = [
        ("Dicionário de dados do SPA · rascunho para conferência", True),
        ("", False),
        ("O que é: a descrição de cada tabela e de cada coluna, que aparece num balão ao passar o cursor no diagrama do Support Nexus.", False),
        ("As descrições foram SUGERIDAS a partir das abreviações dos nomes. Elas precisam ser conferidas por quem conhece o sistema.", False),
        ("", False),
        ("Como preencher", True),
        ("1. Corrija ou complete a coluna \"Descrição (edite aqui)\". Pode apagar o texto sugerido e escrever do zero.", False),
        ("2. Marque \"Conferido\" = S nas linhas que estão certas. SÓ entra na Wiki o que estiver com S.", False),
        ("   Dica: filtre por Confiança = alta, confira rapidamente e preencha S em todas de uma vez (arrastando a alça da célula).", False),
        ("3. Deixe em branco (ou N) o que você ainda não sabe. Dá para mandar a planilha por partes, quantas vezes quiser.", False),
        ("", False),
        ("Abas", True),
        ("Tabelas: uma linha por tabela de cada módulo. Modelo da frase: \"Armazena os dados de produtos do SPA PDV\".", False),
        ("Colunas: uma linha por NOME de coluna. A descrição vale para todas as tabelas em que o nome aparece (cod_prod = Código do produto).", False),
        ("   Ordenadas da mais usada para a menos usada: conferindo o começo da lista você já cobre a maior parte do diagrama.", False),
        ("Exceções: quando um nome significa outra coisa numa tabela específica. Já vem com os comentários que existem no banco.", False),
        ("   Para criar uma exceção, acrescente uma linha com Módulo, Tabela, Coluna e a descrição.", False),
        ("", False),
        ("Confiança da sugestão", True),
        ("banco: comentário que já está no banco de dados (azul)", False),
        ("alta: todas as partes do nome são conhecidas (verde)", False),
        ("média: nome colado ou com abreviação de duplo sentido; veja a Observação (amarelo)", False),
        ("baixa: tem parte desconhecida, mostrada entre colchetes [assim] (laranja)", False),
        ("sem sugestão: não deu para deduzir; preencha ou deixe em branco (cinza)", False),
        ("", False),
        ("Resumo das sugestões", True),
    ]
    for aba, contagem in resumo.items():
        linhas.append((f"{aba}: " + ", ".join(f"{k} {v}" for k, v in sorted(contagem.items(), key=lambda kv: -kv[1])), False))
    linhas += [("", False), ("Arquivo interno: contém a estrutura do banco do ERP. Não publicar e não enviar ao GitHub.", True)]
    for texto, negrito in linhas:
        leia.append([texto])
        if negrito:
            leia.cell(leia.max_row, 1).font = Font(bold=True, size=12 if leia.max_row == 1 else 11)
    leia.column_dimensions["A"].width = 130
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    print(f"gravado {destino}")
    for aba, contagem in resumo.items():
        print(f"  {aba}: " + ", ".join(f"{k} {v}" for k, v in sorted(contagem.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else SAIDA / "dicionario-spa.xlsx")
