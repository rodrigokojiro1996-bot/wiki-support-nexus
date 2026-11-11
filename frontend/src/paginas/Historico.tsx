import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, type ItemRegistro } from '../api';
import Topo from '../componentes/Topo';

const ROTULO_ACAO: Record<string, string> = {
  criou: 'Criou', alterou: 'Alterou', excluiu: 'Excluiu', validou: 'Validou', descartou: 'Descartou', importou: 'Importou', moveu: 'Moveu',
};

/** "10/11/2026 às 23:15" (a data já vem na hora de Brasília: só troca o formato) */
function quando(em: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(em);
  return m ? `${m[3]}/${m[2]}/${m[1]} às ${m[4]}:${m[5]}` : em;
}

// nomes dos campos do detalhe como a pessoa lê
const ROTULO_CAMPO: Record<string, string> = {
  secao: 'seção', bloco: 'bloco', versao: 'versão do manual', por: 'validado por', em: 'em', texto: 'trecho', tabela: 'tabela',
  manual: 'manual', observacao: 'observação', origem: 'lado N', destino: 'lado 1', informativo: 'informativo excluído junto',
  incluidas: 'incluídas', tiradas: 'tiradas',
};
const rotulo = (k: string) => ROTULO_CAMPO[k] ?? k;

const valor = (v: unknown): string =>
  v === null || v === undefined ? '(nada)' : typeof v === 'string' ? v : typeof v === 'number' ? String(v)
    : Array.isArray(v) ? (v.length ? v.map(valor).join(', ') : '(nenhuma)')
    : typeof v === 'object' && 'x' in v && 'y' in v ? `x ${Math.round(Number((v as Ponto).x))}, y ${Math.round(Number((v as Ponto).y))}`
    : JSON.stringify(v);
type Ponto = { x: number; y: number };

/** O antes e o depois da alteração, ou a lista do que mudou (manual, dicionário de dados). */
function Detalhe({ d }: { d: ItemRegistro['detalhe'] }) {
  if (!d || typeof d !== 'object') return null;
  const o = d as Record<string, unknown>;
  const listas = (['mudancas', 'novas', 'alteradas'] as const).filter(k => Array.isArray(o[k]) && (o[k] as unknown[]).length);
  if (listas.length) {
    const nome = { mudancas: 'O que mudou', novas: 'Descrições novas', alteradas: 'Descrições alteradas' };
    return (<>{listas.map(k => (
      <div key={k} className="hist-lista">
        <b>{nome[k]} ({(o[k] as string[]).length})</b>
        <ul>{(o[k] as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul>
      </div>
    ))}</>);
  }
  if ('antes' in o || 'depois' in o) {
    return (
      <div className="hist-antes-depois">
        <div><small>Antes</small><p>{valor(o.antes)}</p></div>
        <div><small>Depois</small><p>{valor(o.depois)}</p></div>
        {Object.entries(o).filter(([k, v]) => k !== 'antes' && k !== 'depois' && v !== '' && v != null).map(([k, v]) => (
          <div key={k}><small>{rotulo(k)}</small><p>{valor(v)}</p></div>
        ))}
      </div>
    );
  }
  // posições do diagrama e outros: uma linha por item
  return (
    <ul className="hist-itens">{Object.entries(o).map(([k, v]) => {
      const par = v as { antes?: unknown; depois?: unknown } | null;
      return <li key={k}><b>{rotulo(k)}</b>: {par && typeof par === 'object' && ('antes' in par || 'depois' in par)
        ? <>{valor(par.antes)} → {valor(par.depois)}</> : valor(v)}</li>;
    })}</ul>
  );
}

/** Histórico de alterações: quem validou, alterou, salvou ou excluiu o quê no Support Nexus, e quando. */
export default function Historico() {
  const [params, setParams] = useSearchParams();
  const filtro = { por: params.get('por') ?? '', area: params.get('area') ?? '', acao: params.get('acao') ?? '', busca: params.get('busca') ?? '' };
  const [busca, setBusca] = useState(filtro.busca);
  const [opcoes, setOpcoes] = useState<{ pessoas: string[]; areas: Record<string, string>; acoes: string[] } | null>(null);
  const [itens, setItens] = useState<ItemRegistro[]>([]);
  const [mais, setMais] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const [abertos, setAbertos] = useState<Set<number>>(new Set());
  const chave = `${filtro.por}|${filtro.area}|${filtro.acao}|${filtro.busca}`;

  useEffect(() => { api.filtrosRegistro().then(setOpcoes).catch(() => {}); }, []);
  const { por, area, acao } = filtro, termo = filtro.busca;
  const carregar = useCallback((antes?: number) => {
    setCarregando(true); setErro('');
    api.registro({ por, area, acao, busca: termo, antes })
      .then(r => { setItens(atual => (antes ? [...atual, ...r.itens] : r.itens)); setMais(r.mais); })
      .catch(e => setErro((e as Error).message))
      .finally(() => setCarregando(false));
  }, [por, area, acao, termo]);
  useEffect(() => { carregar(); }, [carregar]);

  const mudar = (campo: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(campo, v); else p.delete(campo);
    setParams(p, { replace: true });
  };
  const alternar = (id: number) => setAbertos(a => { const n = new Set(a); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <>
      <Topo />
      <main className="historico">
        <header className="hist-topo">
          <h1>Histórico de alterações</h1>
          <p>Tudo o que foi validado, alterado, salvo ou excluído no Support Nexus, com o nome de quem fez.</p>
        </header>
        <form className="hist-filtros" onSubmit={e => { e.preventDefault(); mudar('busca', busca.trim()); }}>
          <select value={filtro.por} onChange={e => mudar('por', e.target.value)} aria-label="Pessoa">
            <option value="">Todas as pessoas</option>
            {opcoes?.pessoas.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <select value={filtro.area} onChange={e => mudar('area', e.target.value)} aria-label="Área">
            <option value="">Todas as áreas</option>
            {opcoes && Object.entries(opcoes.areas).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={filtro.acao} onChange={e => mudar('acao', e.target.value)} aria-label="Ação">
            <option value="">Todas as ações</option>
            {opcoes?.acoes.map(a => <option key={a} value={a}>{ROTULO_ACAO[a] ?? a}</option>)}
          </select>
          <input type="search" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar: manual, tabela, texto… (Enter)" aria-label="Buscar no histórico" />
        </form>
        {erro && <p className="erro" role="alert">{erro}</p>}
        {!itens.length && !carregando && !erro && <p className="vazio">Nada registrado{chave !== '|||' ? ' com esses filtros' : ' ainda'}.</p>}
        <ol className="hist-lista-itens">
          {itens.map(i => (
            <li key={i.id} className={`hist-item acao-${i.acao}`}>
              <div className="hist-linha">
                <span className="hist-acao">{ROTULO_ACAO[i.acao] ?? i.acao}</span>
                <div className="hist-texto">
                  <p>{i.resumo}</p>
                  <small>
                    <b>{i.por || 'sem nome'}</b> · {quando(i.em)} · {opcoes?.areas[i.area] ?? i.area}{i.modulo ? ` · ${i.modulo.toUpperCase()}` : ''}
                  </small>
                </div>
                {i.detalhe != null && (
                  <button type="button" className="link" aria-expanded={abertos.has(i.id)} onClick={() => alternar(i.id)}>
                    {abertos.has(i.id) ? 'Ocultar detalhes' : 'Ver detalhes'}</button>
                )}
              </div>
              {abertos.has(i.id) && <div className="hist-detalhe"><Detalhe d={i.detalhe} /></div>}
            </li>
          ))}
        </ol>
        {mais && (
          <button type="button" className="btn hist-mais" disabled={carregando} onClick={() => carregar(itens[itens.length - 1]?.id)}>
            {carregando ? 'Carregando…' : 'Carregar mais'}</button>
        )}
      </main>
    </>
  );
}
