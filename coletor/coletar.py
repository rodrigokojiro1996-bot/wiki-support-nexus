"""Support Nexus · coletor de metadados (MySQL / MariaDB).

Lê somente o information_schema do schema informado e grava CSVs no formato
que o Mapa Vivo importa. Nenhum dado de cliente é lido.

Uso:
    python coletar.py meu_banco

Credenciais em coletor/.env (veja .env.example). O arquivo .env não deve ir para o git.
"""
import csv
import sys
from pathlib import Path

import pymysql

AQUI = Path(__file__).resolve().parent

CONSULTAS = {
    "tabelas": """
        SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS AS linhas_estimadas, TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME""",
    "colunas": """
        SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION""",
    "fks": """
        SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME, COLUMN_NAME""",
    "indices": """
        SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX""",
}


def ler_env():
    env = {}
    arq = AQUI / ".env"
    if not arq.exists():
        sys.exit("Crie coletor/.env a partir de coletor/.env.example com usuário e senha.")
    for linha in arq.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main():
    if len(sys.argv) < 2:
        sys.exit("Informe o schema: python coletar.py meu_banco")
    schema = sys.argv[1]
    env = ler_env()
    con = pymysql.connect(
        host=env.get("MYSQL_HOST", "localhost"),
        port=int(env.get("MYSQL_PORT", "3306")),
        user=env["MYSQL_USER"],
        password=env.get("MYSQL_PASSWORD", ""),
        database="information_schema",
        charset="utf8mb4",
        read_timeout=60,
    )
    saida = AQUI / "saida" / schema
    saida.mkdir(parents=True, exist_ok=True)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT VERSION()")
            print("Servidor:", cur.fetchone()[0])
            for nome, sql in CONSULTAS.items():
                cur.execute(sql, (schema,))
                cab = [d[0] for d in cur.description]
                linhas = cur.fetchall()
                with open(saida / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(cab)
                    w.writerows(["" if v is None else v for v in l] for l in linhas)
                print(f"{nome}: {len(linhas)} linhas")
    finally:
        con.close()
    print("Arquivos em", saida)


if __name__ == "__main__":
    main()
