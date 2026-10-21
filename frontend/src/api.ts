import type { Catalogo, Manual, ManualEntrada, MenuFicha, MenuNo, Modulo } from './tipos';

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { msg = (await r.json()).detail ?? msg; } catch { /* resposta sem JSON */ }
    throw new Error(msg);
  }
  return r.json();
}
const enc = encodeURIComponent;

// autoria das alterações até ter login: o nome que a pessoa informa no topo, guardado só neste navegador
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

/** 422 do FastAPI vem como lista de erros; vira uma frase só */
async function erroDe(r: Response): Promise<Error> {
  const corpo = await r.json().catch(() => null);
  const d = corpo?.detail;
  if (Array.isArray(d)) return new Error(d.map((x: { msg: string }) => x.msg.replace(/^Value error, /, '')).join('; '));
  return new Error(d ?? `${r.status} ${r.statusText}`);
}

export const api = {
  modulos: () => json<Modulo[]>('/api/modulos'),
  menus: (modulo: string) => json<MenuNo[]>(`/api/modulos/${modulo}/menus`),
  menu: (id: string) => json<MenuFicha>(`/api/menus/${enc(id)}`),
  salvarTabelas: (id: string, tabelas: string[]) => json(`/api/menus/${enc(id)}/tabelas`, put({ tabelas })),
  catalogo: (modulo: string) => json<Catalogo>(`/api/modulos/${modulo}/catalogo`),
  statusRelacao: (modulo: string, id: string, status: 'documentada' | 'descartada' | 'sugerida') =>
    json(`/api/modulos/${modulo}/relacoes/status`, put({ id, status })),
  manual: (codigo: string) => json<Manual>(`/api/manuais/${enc(codigo)}`),
  async salvarManual(corpo: ManualEntrada, codigo?: string): Promise<{ codigo: string; versao: string }> {
    const r = await fetch(codigo ? `/api/manuais/${enc(codigo)}` : '/api/manuais', enviar(codigo ? 'PUT' : 'POST', corpo));
    if (!r.ok) throw await erroDe(r);
    return r.json();
  },
  /** print colado ou arquivo: fica em rascunho no servidor até o manual ser salvo */
  async enviarImagem(arquivo: Blob): Promise<string> {
    const r = await fetch('/api/imagens', { method: 'POST', headers: { 'Content-Type': arquivo.type || 'application/octet-stream' }, body: arquivo });
    if (!r.ok) throw await erroDe(r);
    return (await r.json()).arquivo;
  },
  async pdf(codigo: string): Promise<Blob> {
    const r = await fetch(`/api/manuais/${enc(codigo)}/pdf`);
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? 'Falha ao gerar o PDF');
    return r.blob();
  }
};

/** "PDV › Caixa › Fechamento de Caixa (F10)" */
export const caminhoTexto = (modulo: string, caminho: { titulo: string; atalho: string | null }[]) =>
  [modulo, ...caminho.map(p => (p.atalho ? `${p.titulo} (${p.atalho})` : p.titulo))].join(' › ');
