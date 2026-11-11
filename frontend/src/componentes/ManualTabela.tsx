import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { api } from '../api';
import Documento from './Documento';
import type { Manual, MenuFicha, Relacao, TrechoManual } from '../tipos';

const LARGURA_DOC = 794; // 210 mm do .doc em px: o manual encolhe para caber no painel
const DESTAQUE = 'nexus-trecho';

type Props = {
  manuais: MenuFicha['manuais']; tabela: string; relacoes: Relacao[];
  onFicha: () => void; // alterna para a ficha técnica da tabela
};
// trecho selecionado no manual (rect: onde está na tela, para a pergunta abrir junto dele)
type Selecao = { secao: number; bloco: number; texto: string; rect: DOMRect } | { erro: string };

/** Acha `texto` (espaços normalizados) dentro de `raiz` e devolve o Range dele no DOM. */
function acharTrecho(raiz: Element, texto: string): Range | null {
  const nos: Text[] = [];
  const andar = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  for (let n = andar.nextNode(); n; n = andar.nextNode()) nos.push(n as Text);
  // texto corrido com os espaços juntados, e de onde veio cada caractere
  let corrido = '';
  const origem: { no: Text; i: number }[] = [];
  nos.forEach(no => {
    for (let i = 0; i < no.data.length; i++) {
      const c = /\s/.test(no.data[i]) ? ' ' : no.data[i];
      if (c === ' ' && corrido.endsWith(' ')) continue;
      corrido += c;
      origem.push({ no, i });
    }
  });
  const pos = corrido.indexOf(texto);
  if (pos < 0) return null;
  const ini = origem[pos], fim = origem[pos + texto.length - 1];
  const r = document.createRange();
  r.setStart(ini.no, ini.i);
  r.setEnd(fim.no, fim.i + 1);
  return r;
}

/** Balão da pergunta: logo abaixo do trecho selecionado (acima, se não couber), sempre dentro da janela. */
function PerguntaTrecho({ rect, children }: { rect: DOMRect; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: rect.left, top: rect.bottom + 10 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    const abaixo = rect.bottom + 10 + h <= window.innerHeight - 8;
    setPos({
      left: Math.max(8, Math.min(rect.left + rect.width / 2 - w / 2, window.innerWidth - w - 8)),
      top: abaixo ? rect.bottom + 10 : Math.max(8, rect.top - 10 - h),
    });
  }, [rect]);
  return (
    <div ref={ref} className="mt-pergunta" role="dialog" aria-labelledby="mt-pergunta-titulo" style={pos}>{children}</div>
  );
}

const blocoDe = (n: Node | null) => (n instanceof Element ? n : n?.parentElement)?.closest<HTMLElement>('[data-bloco]') ?? null;

/**
 * Manual da tela ao lado do diagrama: a pessoa seleciona o trecho em que a tabela age e valida; os trechos dessa
 * tabela ficam em destaque. Embaixo, os informativos de incidentes das ligações da tabela.
 */
export default function ManualTabela({ manuais, tabela, relacoes, onFicha }: Props) {
  // o manual da tela (processo) primeiro; os chamados frequentes da tela ficam na lista
  const opcoes = useMemo(() => [...manuais].sort((a, b) =>
    (a.tipo === b.tipo ? a.codigo.localeCompare(b.codigo) : a.tipo === 'processo' ? -1 : 1)), [manuais]);
  const [codigo, setCodigo] = useState(opcoes[0]?.codigo ?? '');
  useEffect(() => { if (!opcoes.some(m => m.codigo === codigo)) setCodigo(opcoes[0]?.codigo ?? ''); }, [opcoes, codigo]);
  const [manual, setManual] = useState<Manual | null>(null);
  const [trechos, setTrechos] = useState<TrechoManual[]>([]);
  const [selecao, setSelecao] = useState<Selecao | null>(null);
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [perdidos, setPerdidos] = useState<Set<number>>(new Set()); // trechos que o manual editado não tem mais
  // a pergunta só abre quando a pessoa solta o mouse (não pisca enquanto ela ainda está arrastando a seleção)
  const [pressionando, setPressionando] = useState(false);
  const [aviso, setAviso] = useState('');
  const doc = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(0.6);

  useEffect(() => {
    if (!codigo) return;
    setManual(null);
    api.manual(codigo).then(setManual).catch(e => setErro((e as Error).message));
  }, [codigo]);
  const recarregar = useCallback(() => {
    if (codigo) api.trechos(codigo, tabela).then(setTrechos).catch(e => setErro((e as Error).message));
  }, [codigo, tabela]);
  useEffect(() => { setSelecao(null); setErro(''); recarregar(); }, [recarregar]);

  // o manual (A4) encolhe para a largura do painel
  useEffect(() => {
    const el = doc.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setZoom(Math.min(1, Math.max(0.35, (el.clientWidth - 4) / LARGURA_DOC))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // seleção dentro do manual: precisa ficar num bloco só (um passo, um parágrafo, uma observação)
  useEffect(() => {
    const solto = () => setPressionando(false);
    window.addEventListener('pointerup', solto);
    return () => window.removeEventListener('pointerup', solto);
  }, []);
  useEffect(() => {
    const mudou = () => {
      const s = window.getSelection();
      // clicou em outro lugar (seleção vazia): a pergunta fecha; seleção fora do manual não mexe na dele
      if (!s || !s.rangeCount || s.isCollapsed) { setSelecao(null); return; }
      if (!doc.current?.contains(s.anchorNode)) return;
      const a = blocoDe(s.anchorNode), b = blocoDe(s.focusNode);
      const texto = s.toString().replace(/\s+/g, ' ').trim();
      if (!texto) { setSelecao(null); return; }
      if (!a || a !== b) { setSelecao({ erro: 'Selecione dentro de um mesmo passo ou parágrafo do manual.' }); return; }
      setSelecao({ secao: Number(a.dataset.secao), bloco: Number(a.dataset.bloco), texto, rect: s.getRangeAt(0).getBoundingClientRect() });
    };
    document.addEventListener('selectionchange', mudou);
    // rolar o painel ou a página: a pergunta acompanha o trecho
    window.addEventListener('scroll', mudou, true);
    window.addEventListener('resize', mudou);
    return () => {
      document.removeEventListener('selectionchange', mudou);
      window.removeEventListener('scroll', mudou, true);
      window.removeEventListener('resize', mudou);
    };
  }, []);

  // destaque dos trechos desta tabela (CSS Custom Highlight: não mexe no HTML do manual)
  useLayoutEffect(() => {
    const raiz = doc.current;
    const destaques = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
    if (!raiz || !manual) return;
    const faltam = new Set<number>();
    const ranges: Range[] = [];
    trechos.forEach(t => {
      const bloco = raiz.querySelector(`[data-secao="${t.secao}"][data-bloco="${t.bloco}"]`);
      const r = (bloco && acharTrecho(bloco, t.texto)) || acharTrecho(raiz, t.texto); // o bloco pode ter mudado de lugar
      if (r) ranges.push(r); else faltam.add(t.id);
    });
    setPerdidos(faltam);
    const Highlight = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight;
    if (destaques && Highlight) destaques.set(DESTAQUE, new Highlight(...ranges));
    return () => { destaques?.delete(DESTAQUE); };
  }, [manual, trechos]);

  const validar = async () => {
    if (!selecao || 'erro' in selecao) return;
    setEnviando(true); setErro('');
    try {
      const { secao, bloco, texto } = selecao;
      await api.ligarTrecho(codigo, { tabela, secao, bloco, texto });
      window.getSelection()?.removeAllRanges();
      setSelecao(null);
      setAviso(`Trecho validado: fica em destaque sempre que alguém abrir ${tabela}.`);
      recarregar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };
  // descartar: nada é gravado e a seleção some
  const descartar = useCallback(() => {
    window.getSelection()?.removeAllRanges();
    setSelecao(null);
    setErro('');
  }, []);
  const perguntando = !!selecao && !('erro' in selecao) && !pressionando;
  useEffect(() => {
    if (!perguntando) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') descartar(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [perguntando, descartar]);
  useEffect(() => { if (!aviso) return; const t = window.setTimeout(() => setAviso(''), 4000); return () => clearTimeout(t); }, [aviso]);

  const desligar = async (t: TrechoManual) => {
    try { await api.desligarTrecho(codigo, t.id); recarregar(); } catch (e) { setErro((e as Error).message); }
  };
  const irPara = (t: TrechoManual) => {
    const raiz = doc.current;
    const bloco = raiz?.querySelector(`[data-secao="${t.secao}"][data-bloco="${t.bloco}"]`);
    bloco?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const comNota = relacoes.filter(r => r.nota && r.estado !== 'descartada');
  const atual = opcoes.find(m => m.codigo === codigo);

  return (
    <div className="painel-corpo mt">
      <div className="mt-topo">
        {opcoes.length > 1 ? (
          <select value={codigo} onChange={e => setCodigo(e.target.value)} aria-label="Manual da tela">
            {opcoes.map(m => <option key={m.codigo} value={m.codigo}>{m.codigo} · {m.titulo}</option>)}
          </select>
        ) : <span className="mt-manual">{atual?.codigo} · {atual?.titulo}</span>}
        <span className="mt-links">
          <Link to={`/manuais/${encodeURIComponent(codigo)}/editar`}>Editar manual</Link>
          <button type="button" className="link" onClick={onFicha}>Ficha técnica</button>
        </span>
      </div>

      {/* barra fixa: a dica, o aviso de seleção em dois blocos e a confirmação depois de validar */}
      <div className="mt-acao" role="status">
        {selecao && 'erro' in selecao ? <span className="mt-aviso">{selecao.erro}</span>
          : aviso ? <span className="mt-ok">{aviso}</span>
          : <span className="mt-dica">Selecione no manual o trecho em que <code>{tabela}</code> age: o Support Nexus pergunta se ele corresponde à tabela.</span>}
        {erro && !perguntando && <p className="erro" role="alert">{erro}</p>}
      </div>

      {/* a pergunta abre junto do trecho; os botões não tiram a seleção do texto (onMouseDown) */}
      {perguntando && selecao && !('erro' in selecao) && createPortal(
        <PerguntaTrecho rect={selecao.rect}>
          <h3 id="mt-pergunta-titulo">Este trecho do material é correspondente à tabela <code>{tabela}</code>?</h3>
          <blockquote>“{selecao.texto.length > 220 ? `${selecao.texto.slice(0, 220)}…` : selecao.texto}”</blockquote>
          <p className="ajuda">Validando, o trecho fica em destaque sempre que alguém abrir esta tabela, com o seu nome.</p>
          {erro && <p className="erro" role="alert">{erro}</p>}
          <div className="acoes">
            <button type="button" className="btn" onMouseDown={e => e.preventDefault()} onClick={descartar} disabled={enviando}>Descartar</button>
            <button type="button" className="btn btn-primario" onMouseDown={e => e.preventDefault()} onClick={validar} disabled={enviando}>
              {enviando ? 'Validando…' : 'Validar'}</button>
          </div>
        </PerguntaTrecho>,
        document.body
      )}

      <div className="mt-doc" ref={doc} onPointerDown={() => { setPressionando(true); setAviso(''); }}>
        {manual ? <div style={{ zoom }}><Documento manual={manual} /></div> : <p className="vazio">Carregando o manual…</p>}
      </div>

      <div className="secao">
        <h3>Trechos ligados a <code>{tabela}</code> ({trechos.length})</h3>
        {trechos.length ? (
          <ul className="mt-trechos">{trechos.map(t => (
            <li key={t.id} className={perdidos.has(t.id) ? 'perdido' : ''}>
              <button type="button" className="link mt-trecho" onClick={() => irPara(t)}>“{t.texto}”</button>
              <small>
                seção {t.secao}{t.por ? ` · ${t.por}` : ''}{t.versao ? ` · versão ${t.versao}` : ''}
                {perdidos.has(t.id) && ' · não encontrado nesta versão do manual'}
              </small>
              <button type="button" className="fechar" aria-label="Desligar este trecho" title="Desligar este trecho" onClick={() => desligar(t)}>×</button>
            </li>
          ))}</ul>
        ) : <p className="vazio">Nenhum trecho ligado ainda.</p>}
      </div>

      <div className="secao">
        <h3>Informativos das ligações ({comNota.length})</h3>
        {comNota.length ? (
          <ul className="mt-notas">{comNota.map(r => (
            <li key={r.id}>
              <code>{r.colunas.map(([a, b]) => `${r.origem}.${a} → ${r.destino}.${b}`).join(', ')}</code>
              <p>{r.nota!.texto}</p>
              {r.nota!.por && <small>{r.nota!.por}</small>}
            </li>
          ))}</ul>
        ) : <p className="vazio">Nenhuma ligação desta tabela tem informativo de incidentes. Clique numa ligação no diagrama para incluir.</p>}
      </div>
    </div>
  );
}
