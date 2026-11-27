import { useEffect, useState } from 'react';

/**
 * Tema da interface: claro (padrão, o de sempre) ou escuro, escolhido no botão do topo e lembrado neste navegador.
 * Fica em <html data-tema="…">; as cores estão em estilo/app.css. O manual continua "papel branco" nos dois temas,
 * e o PDF sai sempre claro (o gerador abre a página num navegador sem a preferência guardada).
 */
export type Tema = 'claro' | 'escuro';

const CHAVE = 'nexus.tema';
const EVENTO = 'nexus-tema';

export function lerTema(): Tema {
  try { return localStorage.getItem(CHAVE) === 'escuro' ? 'escuro' : 'claro'; } catch { return 'claro'; }
}

function trocar(tema: Tema) {
  document.documentElement.dataset.tema = tema;
  try { localStorage.setItem(CHAVE, tema); } catch { /* navegador sem storage: vale só nesta aba */ }
  window.dispatchEvent(new CustomEvent<Tema>(EVENTO, { detail: tema }));
}

/**
 * Troca o tema. Com `origem` (o ponto do clique) e um navegador com View Transitions, o novo tema se abre num círculo
 * a partir dali (o desenho está em estilo/fluido.css). Sem suporte, ou com "reduzir movimento", troca na hora.
 */
export function aplicarTema(tema: Tema, origem?: { x: number; y: number }) {
  const doc = document as Document & { startViewTransition?: (f: () => void) => unknown };
  const calmo = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (!origem || !doc.startViewTransition || calmo) { trocar(tema); return; }
  const raiz = document.documentElement.style;
  const raio = Math.hypot(Math.max(origem.x, innerWidth - origem.x), Math.max(origem.y, innerHeight - origem.y));
  raiz.setProperty('--tema-x', `${origem.x}px`);
  raiz.setProperty('--tema-y', `${origem.y}px`);
  raiz.setProperty('--tema-r', `${raio}px`);
  doc.startViewTransition(() => trocar(tema));
}

/** Tema atual, atualizado quando o botão do topo troca (o diagrama usa para as cores do React Flow) */
export function useTema(): Tema {
  const [tema, setTema] = useState<Tema>(() => (document.documentElement.dataset.tema === 'escuro' ? 'escuro' : 'claro'));
  useEffect(() => {
    const ouvir = (e: Event) => setTema((e as CustomEvent<Tema>).detail);
    window.addEventListener(EVENTO, ouvir);
    return () => window.removeEventListener(EVENTO, ouvir);
  }, []);
  return tema;
}
