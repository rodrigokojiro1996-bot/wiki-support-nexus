-- login com a conta Microsoft (Entra ID): sessões de quem entrou e tentativas de login em andamento.
-- Os tokens dos cookies nunca são gravados, só o SHA-256 deles. Datas em segundos desde 1970 (UTC).
CREATE TABLE sessoes (
    token_hash TEXT PRIMARY KEY,
    oid        TEXT NOT NULL,      -- identificador estável da pessoa no tenant
    email      TEXT NOT NULL,
    nome       TEXT NOT NULL,
    criada_em  INTEGER NOT NULL,
    expira_em  INTEGER NOT NULL
);
CREATE INDEX sessoes_expira ON sessoes (expira_em);

-- entre a ida ao Entra e a volta: state, nonce e o verificador do PKCE (vida de 10 minutos, uso único)
CREATE TABLE logins_pendentes (
    chave_hash  TEXT PRIMARY KEY,
    state       TEXT NOT NULL,
    nonce       TEXT NOT NULL,
    verificador TEXT NOT NULL,
    voltar      TEXT NOT NULL DEFAULT '/',
    criado_em   INTEGER NOT NULL
);
