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

export function aplicarTema(tema: Tema) {
  document.documentElement.dataset.tema = tema;
  try { localStorage.setItem(CHAVE, tema); } catch { /* navegador sem storage: vale só nesta aba */ }
  window.dispatchEvent(new CustomEvent<Tema>(EVENTO, { detail: tema }));
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
