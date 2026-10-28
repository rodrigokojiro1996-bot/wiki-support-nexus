import { useEffect, useState } from 'react';
import type { MenuNo } from '../tipos';

type Props = { itens: MenuNo[]; selecionado: string | null; filtro: string; onEscolher: (id: string) => void };

const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const combina = (no: MenuNo, f: string): boolean => !f || norm(no.titulo).includes(f) || no.itens.some(x => combina(x, f));

type NoProps = {
  no: MenuNo; nivel: number; selecionado: string | null; filtro: string; onEscolher: (id: string) => void;
  // só no primeiro nível: a árvore controla qual menu principal está aberto (um por vez)
  abertoControlado?: boolean; onAlternar?: (abrir: boolean) => void;
};

function No({ no, nivel, selecionado, filtro, onEscolher, abertoControlado, onAlternar }: NoProps) {
  const temFilhos = no.itens.length > 0;
  const aDetalhar = no.submenu && !temFilhos; // tem opções no sistema, ainda não transcritas
  const contemSelecao = !!selecionado && selecionado.startsWith(no.id + '.');
  const [abertoLocal, setAbertoLocal] = useState(contemSelecao);
  const controlado = onAlternar !== undefined;
  const aberto = controlado ? !!abertoControlado : abertoLocal || contemSelecao;
  const expandido = aberto || (!!filtro && temFilhos);
  const alternar = (abrir: boolean) => (controlado ? onAlternar!(abrir) : setAbertoLocal(abrir));
  if (!combina(no, filtro)) return null;
  return (
    <li className={`arv-no nivel-${nivel}`}>
      <div className="arv-linha">
        {temFilhos
          ? <button type="button" className="arv-seta" aria-expanded={expandido} aria-label={expandido ? 'Recolher' : 'Expandir'} onClick={() => alternar(!expandido)}>▸</button>
          : <span className="arv-seta-vazia" />}
        {/* só a tela final (sem opções depois dela) abre a ficha com manuais e tabelas; menu só abre e fecha */}
        <button type="button" className="arv-item" aria-current={selecionado === no.id ? 'true' : undefined}
          aria-expanded={temFilhos ? expandido : undefined} aria-disabled={aDetalhar || undefined}
          title={aDetalhar ? 'Submenu ainda não detalhado: as opções dele ainda não foram mapeadas' : undefined}
          data-desabilitado={no.desabilitado || undefined} data-menu={temFilhos || aDetalhar || undefined}
          onClick={() => { if (temFilhos) alternar(!expandido); else if (!aDetalhar) onEscolher(no.id); }}>
          <span className="arv-titulo">{no.titulo}</span>
          {aDetalhar && <span className="arv-pendente">a detalhar</span>}
          {no.n_manuais > 0 && <span className="arv-badge manual" title={`${no.n_manuais} manual(is)`}>{no.n_manuais}</span>}
          {no.atalho && <kbd>{no.atalho}</kbd>}
        </button>
      </div>
      {temFilhos && expandido && (
        <ul className="arv-lista">
          {no.itens.map(f => <No key={f.id} no={f} nivel={nivel + 1} selecionado={selecionado} filtro={filtro} onEscolher={onEscolher} />)}
        </ul>
      )}
    </li>
  );
}

/** Menus do sistema na mesma ordem da barra do sistema (Cadastros, Estoque, …). Só um menu principal fica aberto por vez. */
export default function MenuArvore({ itens, selecionado, filtro, onEscolher }: Props) {
  const f = norm(filtro.trim());
  const raizDaSelecao = itens.find(no => selecionado === no.id || selecionado?.startsWith(no.id + '.'))?.id ?? null;
  const [abertoRaiz, setAbertoRaiz] = useState<string | null>(raizDaSelecao);

  // ao chegar numa tela por link ou pela URL, abre o menu principal dela e fecha os outros
  useEffect(() => { if (raizDaSelecao) setAbertoRaiz(raizDaSelecao); }, [raizDaSelecao]);

  return (
    <ul className="arv-lista raiz">
      {itens.map(no => (
        <No key={no.id} no={no} nivel={0} selecionado={selecionado} filtro={f} onEscolher={onEscolher}
          abertoControlado={abertoRaiz === no.id}
          onAlternar={abrir => setAbertoRaiz(abrir ? no.id : (abertoRaiz === no.id ? null : abertoRaiz))} />
      ))}
    </ul>
  );
}
