"""Gera o banco de EXEMPLO (demo_pdv) no mesmo formato que o coletor exporta de um MySQL real.

Serve para rodar o Support Nexus sem acesso a nenhum banco: um varejo fictício com ~30 tabelas,
poucas chaves estrangeiras declaradas (como em bancos legados) e o restante das ligações
deixado para a inferência.

Uso (dentro de coletor/):
    python exemplo/gerar_exemplo.py
    python inferir.py demo_pdv
"""
import csv
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "demo_pdv"

# tabela: (engine, linhas estimadas, colunas)   coluna: "nome tipo [*|>tabela.coluna]"
TABELAS = {
    "lojas": ("InnoDB", 6, ["id_loja int(4) *", "nome varchar(60)", "cnpj varchar(18)", "uf char(2)"]),
    "usuarios": ("InnoDB", 48, ["id_usuario int(6) *", "nome varchar(60)", "login varchar(20)", "perfil varchar(20)", "id_loja int(4)"]),
    "cidades": ("MyISAM", 5570, ["id_cidade int(6) *", "nome varchar(60)", "uf char(2)", "cod_ibge char(7)"]),
    "clientes": ("MyISAM", 18420, ["id_cliente int(10) *", "nome varchar(80)", "cpf_cnpj varchar(18)", "telefone varchar(15)", "limite_credito decimal(12,2)", "id_cidade int(6)", "ativo char(1)"]),
    "grupos": ("MyISAM", 32, ["id_grupo int(4) *", "descricao varchar(40)"]),
    "fabricantes": ("MyISAM", 610, ["id_fabricante int(6) *", "nome varchar(60)"]),
    "produtos": ("InnoDB", 21300, ["id_produto int(8) *", "descricao varchar(120)", "cod_barras varchar(14)", "ncm char(8)", "id_grupo int(4)", "id_fabricante int(6)", "preco_venda decimal(12,2)", "ativo char(1)"]),
    "estoque": ("InnoDB", 64200, ["id_loja int(4) *", "id_produto int(8) *", "saldo decimal(12,3)", "minimo decimal(12,3)"]),
    "mov_estoque": ("InnoDB", 812000, ["id_mov bigint(12) *", "id_loja int(4)", "id_produto int(8)", "tipo char(2)", "quantidade decimal(12,3)", "documento varchar(20)", "data_mov datetime", "id_usuario int(6)"]),
    "terminais": ("InnoDB", 22, ["id_terminal int(4) *", "id_loja int(4)", "descricao varchar(40)", "ultimo_sync datetime"]),
    "formas_pgto": ("MyISAM", 9, ["id_forma_pgto int(4) *", "descricao varchar(30)", "tipo char(2)", "gera_receber char(1)"]),
    "caixas": ("InnoDB", 9800, ["id_caixa int(10) *", "id_loja int(4)", "id_terminal int(4)", "id_usuario int(6)", "abertura datetime", "fechamento datetime", "valor_abertura decimal(12,2)", "valor_informado decimal(12,2)", "situacao char(2)"]),
    "caixa_mov": ("InnoDB", 286000, ["id_caixa_mov bigint(12) *", "id_caixa int(10) >caixas.id_caixa", "tipo char(1)", "valor decimal(12,2)", "id_forma_pgto int(4)", "historico varchar(60)"]),
    "vendas": ("InnoDB", 402000, ["id_venda bigint(12) *", "id_loja int(4)", "num_venda int(10)", "id_caixa int(10) >caixas.id_caixa", "id_cliente int(10)", "id_usuario int(6)", "data_venda datetime", "valor_total decimal(12,2)", "situacao char(2)"]),
    "venda_itens": ("InnoDB", 1150000, ["id_venda_item bigint(12) *", "id_venda bigint(12) >vendas.id_venda", "item int(4)", "id_produto int(8)", "quantidade decimal(12,3)", "valor_unitario decimal(12,2)", "desconto decimal(12,2)"]),
    "venda_pagamentos": ("InnoDB", 438000, ["id_venda_pgto bigint(12) *", "id_venda bigint(12) >vendas.id_venda", "id_forma_pgto int(4)", "valor decimal(12,2)", "nsu varchar(20)"]),
    "devolucoes": ("MyISAM", 3100, ["id_devolucao int(10) *", "id_venda bigint(12)", "id_cliente int(10)", "data_dev datetime", "valor decimal(12,2)", "credito decimal(12,2)", "situacao char(1)"]),
    "devolucao_itens": ("MyISAM", 5200, ["id_devolucao_item int(10) *", "id_devolucao int(10)", "id_produto int(8)", "quantidade decimal(12,3)", "valor decimal(12,2)"]),
    "nfce": ("InnoDB", 398000, ["id_loja int(4) *", "numero int(9) *", "serie int(3) *", "id_venda bigint(12)", "chave varchar(44)", "situacao char(1)", "protocolo varchar(20)", "contingencia char(1)"]),
    "nfce_itens": ("InnoDB", 1130000, ["id_loja int(4) *", "numero int(9) *", "serie int(3) *", "item int(4) *", "id_produto int(8)", "quantidade decimal(12,3)", "valor decimal(12,2)"]),
    "nfce_eventos": ("InnoDB", 4100, ["id_loja int(4) *", "numero int(9) *", "serie int(3) *", "seq_evento int(4) *", "tipo varchar(20)", "protocolo varchar(20)", "data_evento datetime"]),
    "fornecedores": ("MyISAM", 940, ["id_fornecedor int(6) *", "razao_social varchar(80)", "cnpj varchar(18)"]),
    "nf_entrada": ("InnoDB", 28400, ["id_nf_entrada int(10) *", "id_loja int(4)", "id_fornecedor int(6)", "numero int(9)", "serie int(3)", "chave varchar(44)", "data_entrada date", "situacao char(1)"]),
    "nf_entrada_itens": ("InnoDB", 151000, ["id_nf_entrada_item int(10) *", "id_nf_entrada int(10) >nf_entrada.id_nf_entrada", "id_produto int(8)", "quantidade decimal(12,3)", "custo decimal(12,4)"]),
    "contas_receber": ("MyISAM", 7800, ["id_titulo int(10) *", "id_loja int(4)", "id_cliente int(10)", "id_venda bigint(12)", "vencimento date", "valor decimal(12,2)", "situacao char(1)"]),
    "baixas_receber": ("MyISAM", 6900, ["id_baixa int(10) *", "id_titulo int(10)", "data_baixa date", "valor decimal(12,2)", "id_usuario int(6)"]),
    "transferencias": ("InnoDB", 5200, ["id_transf int(10) *", "loja_origem int(4)", "loja_destino int(4)", "data_envio datetime", "situacao char(1)", "em_uso char(1)"]),
    "transferencia_itens": ("InnoDB", 41000, ["id_transf_item int(10) *", "id_transf int(10)", "id_produto int(8)", "quantidade decimal(12,3)"]),
    "sync_fila": ("InnoDB", 120, ["id_sync bigint(12) *", "tabela varchar(40)", "id_registro bigint(12)", "operacao char(1)", "enviado char(1)", "criado_em datetime"]),
    "parametros": ("MyISAM", 340, ["id_loja int(4) *", "chave varchar(40) *", "valor varchar(255)"]),
}


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    tab, col, fks, idx = [], [], [], []
    for nome, (engine, linhas, colunas) in TABELAS.items():
        tab.append([nome, "BASE TABLE", engine, linhas, ""])
        pks = []
        for i, c in enumerate(colunas, 1):
            partes = c.split(" ")
            cnome, tipo, marca = partes[0], partes[1], (partes[2] if len(partes) > 2 else "")
            pk = marca == "*"
            col.append([nome, i, cnome, tipo, "NO" if pk else "YES", "PRI" if pk else "", "", "", ""])
            if pk:
                pks.append(cnome)
            if marca.startswith(">"):
                rt, rc = marca[1:].split(".")
                fks.append([f"fk_{nome}_{cnome}", nome, cnome, rt, rc])
        for seq, c in enumerate(pks, 1):
            idx.append([nome, "PRIMARY", 0, seq, c])
    escrever("tabelas", ["TABLE_NAME", "TABLE_TYPE", "ENGINE", "linhas_estimadas", "TABLE_COMMENT"], tab)
    escrever("colunas", ["TABLE_NAME", "ORDINAL_POSITION", "COLUMN_NAME", "COLUMN_TYPE", "IS_NULLABLE", "COLUMN_KEY", "COLUMN_DEFAULT", "EXTRA", "COLUMN_COMMENT"], col)
    escrever("fks", ["CONSTRAINT_NAME", "TABLE_NAME", "COLUMN_NAME", "REFERENCED_TABLE_NAME", "REFERENCED_COLUMN_NAME"], fks)
    escrever("indices", ["TABLE_NAME", "INDEX_NAME", "NON_UNIQUE", "SEQ_IN_INDEX", "COLUMN_NAME"], idx)
    print(f"{len(tab)} tabelas, {len(col)} colunas, {len(fks)} FKs declaradas em {DESTINO}")


def escrever(nome, cab, linhas):
    with open(DESTINO / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)


if __name__ == "__main__":
    main()
