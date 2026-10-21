export type Modulo = { id: string; nome: string; banco: string | null; catalogo_em: string | null; catalogo_resumo: string | null };

export type MenuNo = {
  id: string; titulo: string; atalho: string | null; tela_codigo: string | null;
  desabilitado: boolean; submenu: boolean; n_tabelas: number; n_manuais: number; itens: MenuNo[];
};

export type Passo = { id: string; titulo: string; atalho: string | null };

export type EstadoRelacao = 'confirmada' | 'documentada' | 'sugerida' | 'descartada';

export type Relacao = {
  id: string; origem: string; destino: string; colunas: [string, string][];
  estado: EstadoRelacao; regra: string | null; motivo: string | null;
  por: string | null; em: string | null; // quem validou/descartou e quando
};

export type MenuFicha = {
  id: string; modulo: string; titulo: string; atalho: string | null; tela_codigo: string | null; desabilitado: boolean;
  banco: string; caminho: Passo[];
  tabelas: { tabela: string; origem: 'sugerido' | 'equipe'; por: string; em: string | null; engine: string | null; linhas: number | null; existe: number }[];
  relacoes: Relacao[];
  manuais: { codigo: string; titulo: string; subtitulo: string; versao: string; atualizado_em: string }[];
  filhos: Passo[];
};

export type Bloco =
  | { tipo: 'passo'; texto: string; rotulo?: string }
  | { tipo: 'obs'; texto: string }
  | { tipo: 'nota'; texto: string }
  | { tipo: 'texto'; texto: string }
  | { tipo: 'subtitulo'; texto: string }
  | { tipo: 'sql'; texto: string }
  | { tipo: 'imagem'; arquivo: string; legenda: string };

export type Manual = {
  codigo: string; titulo: string; subtitulo: string; versao: string; modulo: string; modulo_nome: string;
  menu: string | null; caminho: Passo[]; tabelas: string[]; fontes: string[]; atualizado_em: string;
  secoes: { titulo: string; blocos: Bloco[] }[];
};

export type Catalogo = { banco: string; tabelas: { nome: string; engine: string; linhas: number | null }[]; relacoes: Relacao[] };
