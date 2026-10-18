import type { Catalogo, Manual, MenuFicha, MenuNo, Modulo } from './tipos';

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
const put = (body: unknown): RequestInit => ({ method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  modulos: () => json<Modulo[]>('/api/modulos'),
  menus: (modulo: string) => json<MenuNo[]>(`/api/modulos/${modulo}/menus`),
  menu: (id: string) => json<MenuFicha>(`/api/menus/${enc(id)}`),
  salvarTabelas: (id: string, tabelas: string[]) => json(`/api/menus/${enc(id)}/tabelas`, put({ tabelas })),
  catalogo: (modulo: string) => json<Catalogo>(`/api/modulos/${modulo}/catalogo`),
  statusRelacao: (modulo: string, id: string, status: 'documentada' | 'descartada' | 'sugerida') =>
    json(`/api/modulos/${modulo}/relacoes/status`, put({ id, status })),
  manual: (codigo: string) => json<Manual>(`/api/manuais/${enc(codigo)}`),
  async pdf(codigo: string): Promise<Blob> {
    const r = await fetch(`/api/manuais/${enc(codigo)}/pdf`);
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? 'Falha ao gerar o PDF');
    return r.blob();
  }
};

/** "PDV › Caixa › Fechamento de Caixa (F10)" */
export const caminhoTexto = (modulo: string, caminho: { titulo: string; atalho: string | null }[]) =>
  [modulo, ...caminho.map(p => (p.atalho ? `${p.titulo} (${p.atalho})` : p.titulo))].join(' › ');
