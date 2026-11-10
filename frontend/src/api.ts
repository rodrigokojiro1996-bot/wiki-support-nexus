import type { Catalogo, Manual, NotaRelacao, NovaRelacao, Relacao, ManualEntrada, ManualResumo, MenuFicha, MenuNo, Modulo, Rascunho } from './tipos';

// login Microsoft: com ele ligado, a API responde 401 quando a sessão termina e quem estiver ouvindo é avisado
// (a interface mostra "Sua sessão terminou" sem apagar o que está aberto, como um manual em edição)
const ouvintes = new Set<() => void>();
async function buscar(url: string, init?: RequestInit): Promise<Response> {
  const r = await fetch(url, init);
  if (r.status === 401) ouvintes.forEach(avisar => avisar());
  return r;
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await buscar(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { msg = (await r.json()).detail ?? msg; } catch { /* resposta sem JSON */ }
    throw new Error(msg);
  }
  return r.json();
}
const enc = encodeURIComponent;

export type Usuario = { nome: string; email: string };
/** login: o servidor exige a conta Microsoft; usuario: quem entrou (null = ainda não entrou) */
export type Acesso = { login: boolean; usuario: Usuario | null };

export const sessao = {
  eu: () => json<Acesso>('/api/auth/eu'),
  /** endereço do botão "Entrar": vai à Microsoft e volta para `voltar` */
  urlEntrar: (voltar: string) => `/api/auth/entrar?voltar=${enc(voltar)}`,
  async sair() { await fetch('/api/auth/sair', { method: 'POST' }); },
  /** avisa quando a API recusar por sessão terminada; devolve a função que para de avisar */
  aoExpirar(avisar: () => void): () => void {
    ouvintes.add(avisar);
    return () => { ouvintes.delete(avisar); };
  }
};

// autoria das alterações com o login desligado: o nome que a pessoa informa no topo, guardado só neste navegador
// (com o login ligado o servidor ignora este cabeçalho e usa quem entrou)
const CHAVE_USUARIO = 'nexus.usuario';
export const usuario = {
  ler(): string { try { return localStorage.getItem(CHAVE_USUARIO) ?? ''; } catch { return ''; } },
  gravar(nome: string) { try { localStorage.setItem(CHAVE_USUARIO, nome.trim()); } catch { /* navegador sem storage */ } }
};

const enviar = (method: 'PUT' | 'POST', body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json', 'X-Usuario': enc(usuario.ler()) },
  body: JSON.stringify(body)
});
const put = (body: unknown) => enviar('PUT', body);

/** frase para quando a resposta não traz o motivo (ex.: o proxy cortou um arquivo grande) */
const SEM_DETALHE: Record<number, string> = {
  413: 'Arquivo grande demais.',
  415: 'Tipo de arquivo não suportado.',
  422: 'Não foi possível ler o arquivo.'
};

/** 422 do FastAPI vem como lista de erros; vira uma frase só */
async function erroDe(r: Response): Promise<Error> {
  const corpo = await r.json().catch(() => null);
  const d = corpo?.detail;
  if (Array.isArray(d)) return new Error(d.map((x: { msg: string }) => x.msg.replace(/^Value error, /, '')).join('; '));
  return new Error(d ?? SEM_DETALHE[r.status] ?? `${r.status} ${r.statusText}`);
}

/** mesmo limite da API (servicos/importacao.py): recusa antes de enviar */
export const IMPORTACAO_MAXIMO_MB = 20;
export const IMPORTACAO_ACEITA = '.pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown';

/** NEXUS_AMBIENTE do servidor ("homologacao" liga a faixa no topo); lido uma vez por carga da página */
let ambiente: Promise<string> | null = null;
export const ambienteDoServidor = () =>
  (ambiente ??= json<{ ambiente?: string }>('/api/saude').then(s => s.ambiente ?? '').catch(() => ''));

export const api = {
  modulos: () => json<Modulo[]>('/api/modulos'),
  menus: (modulo: string) => json<MenuNo[]>(`/api/modulos/${modulo}/menus`),
  menu: (id: string) => json<MenuFicha>(`/api/menus/${enc(id)}`),
  salvarTabelas: (id: string, tabelas: string[]) => json(`/api/menus/${enc(id)}/tabelas`, put({ tabelas })),
  catalogo: (modulo: string) => json<Catalogo>(`/api/modulos/${modulo}/catalogo`),
  statusRelacao: (modulo: string, id: string, status: 'documentada' | 'descartada' | 'sugerida') =>
    json(`/api/modulos/${modulo}/relacoes/status`, put({ id, status })),
  async ligarColunas(modulo: string, corpo: NovaRelacao): Promise<Relacao> {
    const r = await fetch(`/api/modulos/${modulo}/relacoes`, enviar('POST', corpo));
    if (!r.ok) throw await erroDe(r);
    return r.json();
  },
  /** informativo de incidentes da ligação; sem texto, só move o post-it */
  async notaRelacao(modulo: string, id: string, nota: { texto?: string; posicao?: number }): Promise<NotaRelacao> {
    const r = await fetch(`/api/modulos/${modulo}/relacoes/nota`, put({ id, ...nota }));
    if (!r.ok) throw await erroDe(r);
    return r.json();
  },
  async apagarNota(modulo: string, id: string) {
    const r = await fetch(`/api/modulos/${modulo}/relacoes/nota?id=${enc(id)}`, { method: 'DELETE' });
    if (!r.ok) throw await erroDe(r);
  },
  /** tabelas arrastadas: valem para todos que abrirem a tela (chave = tabelas da tela) */
  async salvarPosicoes(modulo: string, chave: string, posicoes: { tabela: string; x: number; y: number }[]) {
    const r = await fetch(`/api/modulos/${modulo}/diagrama/posicoes`, put({ chave, posicoes }));
    if (!r.ok) throw await erroDe(r);
  },
  async reorganizar(modulo: string, chave: string) {
    const r = await fetch(`/api/modulos/${modulo}/diagrama/posicoes?chave=${enc(chave)}`, { method: 'DELETE' });
    if (!r.ok) throw await erroDe(r);
  },
  manual: (codigo: string) => json<Manual>(`/api/manuais/${enc(codigo)}`),
  manuais: (modulo: string) => json<ManualResumo[]>(`/api/manuais?modulo=${enc(modulo)}`),
  async salvarManual(corpo: ManualEntrada, codigo?: string): Promise<{ codigo: string; versao: string }> {
    const r = await buscar(codigo ? `/api/manuais/${enc(codigo)}` : '/api/manuais', enviar(codigo ? 'PUT' : 'POST', corpo));
    if (!r.ok) throw await erroDe(r);
    return r.json();
  },
  /** print colado ou arquivo: fica em rascunho no servidor até o manual ser salvo */
  async enviarImagem(arquivo: Blob): Promise<string> {
    const r = await buscar('/api/imagens', { method: 'POST', headers: { 'Content-Type': arquivo.type || 'application/octet-stream' }, body: arquivo });
    if (!r.ok) throw await erroDe(r);
    return (await r.json()).arquivo;
  },
  /** documento (PDF, Word, .txt, .md) → rascunho para revisar no editor; nada é salvo */
  async importarManual(modulo: string, arquivo: File): Promise<Rascunho> {
    if (arquivo.size > IMPORTACAO_MAXIMO_MB * 1024 * 1024) throw new Error(`Arquivo maior que ${IMPORTACAO_MAXIMO_MB} MB.`);
    const r = await buscar(`/api/manuais/importar?modulo=${enc(modulo)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Arquivo': enc(arquivo.name) }, body: arquivo
    });
    if (!r.ok) throw await erroDe(r);
    return r.json();
  },
  async pdf(codigo: string): Promise<Blob> {
    const r = await buscar(`/api/manuais/${enc(codigo)}/pdf`);
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? 'Falha ao gerar o PDF');
    return r.blob();
  }
};

/** "PDV › Caixa › Fechamento de Caixa (F10)" */
export const caminhoTexto = (modulo: string, caminho: { titulo: string; atalho: string | null }[]) =>
  [modulo, ...caminho.map(p => (p.atalho ? `${p.titulo} (${p.atalho})` : p.titulo))].join(' › ');
