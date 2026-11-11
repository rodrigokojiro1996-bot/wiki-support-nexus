import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Background, BaseEdge, EdgeLabelRenderer, Handle, Panel, Position, ReactFlow, ReactFlowProvider, getSmoothStepPath, useReactFlow,
  type Edge, type EdgeProps, type Node, type NodeChange, type NodeProps
} from '@xyflow/react';
import { api } from '../api';
import { useTema } from '../tema';
import '@xyflow/react/dist/style.css';
import ELK from 'elkjs/lib/elk.bundled.js';
import type { ElkNode } from 'elkjs/lib/elk-api';
import type { NotaRelacao, NovaRelacao, Relacao } from '../tipos';
import { afastar, type Ponto } from './afastar';
import { atravessa, criarRoteador } from './rotear';

const elk = new ELK();

type Coluna = { nome: string; tipo: string; pk: boolean; descricao?: string };
type TabelaDiag = {
  nome: string; engine: string; linhas: number | null; foco: boolean; apoio: boolean; colunas: Coluna[];
  adicionada?: boolean; // posta à mão neste diagrama (botão direito no fundo › Adicionar tabela)
  telas?: string[][]; // caminho de cada tela que usa a tabela (menu › submenu › tela)
};
type RespostaDiagrama = {
  foco: string[]; tabelas: TabelaDiag[]; relacoes: Relacao[]; apoio_ocultas: string[];
  posicoes?: Record<string, Ponto>; // tabelas que a equipe arrastou nesta tela
};
/** balão do cursor: na coluna, o que ela guarda (dicionário de dados); na tabela, as telas que a usam */
type Balao = { titulo: string; detalhe: string; texto?: string; lista?: { rotulo: string; itens: string[]; vazio: string }; dica?: string; rect: DOMRect };

type DadosTabela = {
  nome: string; engine: string; foco: boolean; apoio: boolean; adicionada: boolean; colunas: Coluna[]; ocultas: number;
  chaves: Set<string>; acesas: Set<string>; estado: 'normal' | 'ativo' | 'apagado'; selecionada: boolean; busca: string;
  marcadas: Set<string>; onColuna: (tabela: string, coluna: string) => void; // colunas escolhidas para ligar
  expandida: boolean; onExpandir: (tabela: string) => void; // todas as colunas só desta tabela
  telas: string[][]; onBalao: (b: Balao | null) => void;
  // arrastar uma coluna até a coluna de outra tabela; alvo = coluna desta tabela sob o cursor durante o arraste
  onArrastarColuna: (tabela: string, coluna: string, e: React.PointerEvent<HTMLElement>) => void; alvo: string | null;
};
type Ponta = { tabela: string; coluna: string; pk: boolean };
// uma aresta por par de colunas; "primeira" leva as marcas N/1 da relação e o post-it
type DadosRelacao = {
  estado: Relacao['estado']; destaque: boolean; apagada: boolean; juncao: string; primeira: boolean; colOrigem: string; colDestino: string;
  pontos?: Ponto[]; // trajeto calculado pelo ELK (contorna os cartões); some quando uma das tabelas foi arrastada
  relId: string; nota?: NotaRelacao; // informativo de incidentes: a linha fica turquesa e o post-it vai na primeira
  onMoverNota?: (relId: string, posicao: number) => void; onEditarNota?: (relId: string) => void;
};

// medidas fixas do cartão (iguais ao CSS .tb / .tb-cab / .tb-col / .tb-mais)
const LARGURA = 290, BORDA = 1, CAB = 38, LINHA = 25, RODAPE = 24;
const yColuna = (i: number) => BORDA + CAB + i * LINHA + LINHA / 2;

/** Caminho ortogonal com cantos arredondados passando pelos pontos de dobra. */
function caminhoArredondado(p: Ponto[], raio = 7): string {
  let d = `M ${p[0].x} ${p[0].y}`;
  for (let i = 1; i < p.length - 1; i++) {
    const a = p[i - 1], b = p[i], c = p[i + 1];
    const r = Math.min(raio, Math.hypot(b.x - a.x, b.y - a.y) / 2, Math.hypot(c.x - b.x, c.y - b.y) / 2);
    const e = { x: b.x - Math.sign(b.x - a.x) * r, y: b.y - Math.sign(b.y - a.y) * r };
    const s = { x: b.x + Math.sign(c.x - b.x) * r, y: b.y + Math.sign(c.y - b.y) * r };
    d += ` L ${e.x} ${e.y} Q ${b.x} ${b.y} ${s.x} ${s.y}`;
  }
  const f = p[p.length - 1];
  return d + ` L ${f.x} ${f.y}`;
}

function icone(tipo: string) {
  const t = tipo.toLowerCase();
  if (/int|decimal|numeric|float|double|bit/.test(t)) return '#';
  if (/date|time|year/.test(t)) return '◷';
  if (/blob|binary/.test(t)) return '▤';
  return 'abc';
}

/* ---------- cartão da tabela ---------- */
function TabelaNo({ data }: NodeProps<Node<DadosTabela>>) {
  const b = data.busca;
  const balao = (e: React.MouseEvent<HTMLElement>, x: Omit<Balao, 'rect'>) => data.onBalao({ ...x, rect: e.currentTarget.getBoundingClientRect() });
  const sair = () => data.onBalao(null);
  return (
    <div className={`tb ${data.foco ? 'tb-foco' : ''} ${data.selecionada ? 'tb-sel' : ''} tb-${data.estado}`}>
      <div className="tb-cab" title="Arraste para organizar o diagrama"
        onMouseEnter={e => balao(e, { titulo: data.nome, detalhe: `tabela · ${data.engine}`,
          lista: { rotulo: `Telas que usam (${data.telas.length})`, itens: data.telas.map(t => t.join(' › ')), vazio: 'Nenhuma tela usa esta tabela ainda.' } })}
        onMouseLeave={sair}>
        <span className={b && data.nome.toLowerCase().includes(b) ? 'achou' : undefined}>{data.nome}</span>
        {data.apoio && <em title="Tabela de apoio: muitas outras tabelas apontam para ela">apoio</em>}
        {data.adicionada && <em className="tb-adicionada" title="Adicionada à mão neste diagrama (botão direito para remover)">adicionada</em>}
        <small>{data.engine}</small>
      </div>
      {data.colunas.map(c => (
        // nodrag/nopan: arrastar a coluna liga colunas (não move a tabela nem o diagrama)
        <div key={c.nome} data-tabela={data.nome} data-coluna={c.nome}
          className={`tb-col nodrag nopan ${c.pk ? 'pk' : ''} ${data.chaves.has(c.nome) ? 'fk' : ''} ${data.acesas.has(c.nome) ? 'ligada' : ''} ${b && c.nome.toLowerCase().includes(b) ? 'achou' : ''} ${data.marcadas.has(c.nome) ? 'marcada' : ''} ${data.alvo === c.nome ? 'alvo' : ''}`}
          onMouseEnter={e => balao(e, { titulo: c.nome, detalhe: `${c.tipo}${c.pk ? ' · chave primária' : ''}`, texto: c.descricao ?? '',
                                        dica: 'Arraste até a coluna de outra tabela (ou clique numa e depois na outra) para ligar' })}
          onMouseLeave={sair}
          onPointerDown={e => { if (e.button === 0) { sair(); data.onArrastarColuna(data.nome, c.nome, e); } }}
          onClick={e => { e.stopPropagation(); sair(); data.onColuna(data.nome, c.nome); }}>
          <Handle type="target" position={Position.Left} id={`${c.nome}-t`} className="tb-alca" isConnectable={false} />
          <i className="tb-ic">{icone(c.tipo)}</i>
          <b>{c.nome}</b>
          <span>{c.tipo}</span>
          <Handle type="source" position={Position.Right} id={`${c.nome}-s`} className="tb-alca" isConnectable={false} />
        </div>
      ))}
      {data.ocultas > 0 && (
        <button type="button" className="tb-mais" title="Mostrar todas as colunas desta tabela para ligar a outra"
          onClick={e => { e.stopPropagation(); data.onExpandir(data.nome); }}>+ {data.ocultas} colunas · mostrar todas</button>
      )}
      {data.expandida && (
        <button type="button" className="tb-mais" onClick={e => { e.stopPropagation(); data.onExpandir(data.nome); }}>− recolher colunas</button>
      )}
    </div>
  );
}

/** Fica ao lado do elemento (à direita; à esquerda se não couber), fora do canvas para não ser cortado nem escalado pelo zoom. */
function BalaoFlutuante({ b }: { b: Balao }) {
  const LARG = 320;
  const cabeDireita = b.rect.right + 10 + LARG <= window.innerWidth;
  const style = { top: Math.max(8, Math.min(b.rect.top, window.innerHeight - 150)), left: cabeDireita ? b.rect.right + 10 : Math.max(8, b.rect.left - 10 - LARG) };
  return createPortal(
    <div className="diag-balao" role="tooltip" style={style}>
      <div className="diag-balao-cab"><b>{b.titulo}</b><small>{b.detalhe}</small></div>
      {b.lista ? (<>
        <small className="rotulo">{b.lista.rotulo}</small>
        {b.lista.itens.length ? (
          <ul>{b.lista.itens.slice(0, 8).map(i => <li key={i}>{i}</li>)}
            {b.lista.itens.length > 8 && <li className="mais">+ {b.lista.itens.length - 8} outras</li>}</ul>
        ) : <p className="sem">{b.lista.vazio}</p>}
      </>) : b.texto ? <p>{b.texto}</p> : <p className="sem">Descrição ainda não cadastrada.</p>}
      {b.dica && <small className="dica">{b.dica}</small>}
    </div>,
    document.body
  );
}

/* ---------- ligação com marcas N (lado da chave estrangeira) e 1 (lado referenciado) ---------- */
/** Post-it do informativo de incidentes: fica sobre a linha e desliza ao longo dela (posição de 0 a 1). */
function PostIt({ caminho, d }: { caminho: string; d: DadosRelacao }) {
  const ref = useRef<SVGPathElement>(null);
  const nota = d.nota!;
  const [t, setT] = useState(nota.posicao);
  useEffect(() => { setT(nota.posicao); }, [nota.posicao]);
  const [pt, setPt] = useState<Ponto | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const p = el.getPointAtLength(el.getTotalLength() * t);
    setPt({ x: p.x, y: p.y });
  }, [caminho, t]);
  const { screenToFlowPosition } = useReactFlow();

  // arrastar: o post-it vai para o ponto da linha mais perto do cursor; clique sem arrastar abre para editar
  const arrastar = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0 || !ref.current) return;
    e.stopPropagation();
    const el = ref.current, total = el.getTotalLength();
    const amostras = Array.from({ length: 121 }, (_, i) => { const p = el.getPointAtLength((total * i) / 120); return { t: i / 120, x: p.x, y: p.y }; });
    const x0 = e.clientX, y0 = e.clientY;
    let moveu = false, ultimo = t;
    const mover = (ev: PointerEvent) => {
      if (!moveu && Math.hypot(ev.clientX - x0, ev.clientY - y0) < 4) return;
      moveu = true;
      const f = screenToFlowPosition({ x: ev.clientX, y: ev.clientY });
      ultimo = amostras.reduce((m, a) => ((a.x - f.x) ** 2 + (a.y - f.y) ** 2 < (m.x - f.x) ** 2 + (m.y - f.y) ** 2 ? a : m)).t;
      setT(ultimo);
    };
    const soltar = () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
      if (moveu) d.onMoverNota?.(d.relId, ultimo); else d.onEditarNota?.(d.relId);
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
  };

  return (
    <>
      <path ref={ref} d={caminho} fill="none" stroke="none" />
      {pt && (
        <EdgeLabelRenderer>
          {/* o corpo do post-it deixa o clique passar (a tabela embaixo continua arrastável); só a alça pega o mouse */}
          <div className={`rel-postit-caixa ${d.apagada ? 'apagada' : ''}`}
            style={{ transform: `translate(-50%, -50%) translate(${pt.x}px, ${pt.y}px)` }}>
            <button type="button" className="rel-postit-alca nodrag nopan"
              title={`Informativo de incidentes${nota.por ? ` · ${nota.por}` : ''}\nArraste para mover ao longo da linha · clique para editar`}
              aria-label="Informativo de incidentes: arraste para mover, clique para editar"
              onPointerDown={arrastar} onKeyDown={e => { if (e.key === 'Enter') d.onEditarNota?.(d.relId); }}>⠿ informativo</button>
            <div className="rel-postit">{nota.texto}</div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

function RelacaoAresta({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<Edge<DadosRelacao>>) {
  const d = data!;
  // trajeto do ELK quando existe; senão, o traçado padrão do React Flow
  const p = d.pontos;
  const caminho = p && p.length > 1 ? caminhoArredondado(p)
    : getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 8, offset: 22 })[0];
  if (p && p.length > 1) { sourceX = p[0].x; sourceY = p[0].y; targetX = p[p.length - 1].x; targetY = p[p.length - 1].y; }
  const est = `${d.destaque ? 'destaque' : ''} ${d.apagada ? 'apagada' : ''} ${d.nota ? 'com-nota' : ''}`;
  return (
    <>
      <BaseEdge id={id} path={caminho} className={`rel-aresta ${est} rel-${d.estado}`} interactionWidth={14} />
      {d.primeira && d.nota && <PostIt caminho={caminho} d={d} />}
      <EdgeLabelRenderer>
        {/* pontos de encaixe exatamente na linha de cada coluna */}
        <div className={`rel-ponto ${est}`} style={{ transform: `translate(-50%, -50%) translate(${sourceX}px, ${sourceY}px)` }} title={d.juncao} />
        <div className={`rel-ponto ${est}`} style={{ transform: `translate(-50%, -50%) translate(${targetX}px, ${targetY}px)` }} title={d.juncao} />
        {d.primeira && <>
          <div className={`rel-marca ${est}`} style={{ transform: `translate(-50%, -50%) translate(${sourceX + 14}px, ${sourceY - 10}px)` }} title={d.juncao}>N</div>
          <div className={`rel-marca ${est}`} style={{ transform: `translate(-50%, -50%) translate(${targetX - 14}px, ${targetY - 10}px)` }} title={d.juncao}>1</div>
        </>}
      </EdgeLabelRenderer>
    </>
  );
}

const tiposNo = { tabela: TabelaNo };
const tiposAresta = { relacao: RelacaoAresta };

type Props = {
  modulo: string; tabelas: string[]; onAbrirTabela: (nome: string) => void; onLigou?: () => void;
  onClicarTabela?: (nome: string) => void; // clique simples: abre o painel ao lado (manual da tela ou ficha)
};

type MenuDiagrama = { x: number; y: number; flow: Ponto; tabela?: string; buscando: boolean };

/** Menu do botão direito: fica onde o cursor estava (dentro da janela); fecha com Esc ou clicando fora. */
function MenuContexto({ m, onFechar, children }: { m: MenuDiagrama; onFechar: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: m.x, top: m.y });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setPos({ left: Math.max(8, Math.min(m.x, window.innerWidth - r.width - 8)), top: Math.max(8, Math.min(m.y, window.innerHeight - r.height - 8)) });
  }, [m.x, m.y, m.buscando]);
  useEffect(() => {
    const fora = (e: PointerEvent) => { if (!ref.current?.contains(e.target as HTMLElement)) onFechar(); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onFechar(); };
    window.addEventListener('pointerdown', fora, true);
    window.addEventListener('keydown', esc);
    return () => { window.removeEventListener('pointerdown', fora, true); window.removeEventListener('keydown', esc); };
  }, [onFechar]);
  return createPortal(
    <div ref={ref} className={`diag-menu ${m.buscando ? 'buscando' : ''}`} role="menu" style={pos} onContextMenu={e => e.preventDefault()}>
      {children}
    </div>,
    document.body
  );
}

/** Busca de tabela do módulo para pôr no diagrama: por nome ou descrição; Enter escolhe a primeira. */
function BuscaTabela({ lista, naTela, onEscolher }: {
  lista: { nome: string; descricao: string }[] | null; naTela: Set<string>; onEscolher: (nome: string) => void;
}) {
  const [termo, setTermo] = useState('');
  const t = termo.trim().toLowerCase();
  const achadas = useMemo(() => (lista ?? [])
    .filter(x => !naTela.has(x.nome) && (!t || x.nome.toLowerCase().includes(t) || x.descricao.toLowerCase().includes(t)))
    // quem começa com o termo vem antes
    .sort((a, b) => Number(!a.nome.toLowerCase().startsWith(t)) - Number(!b.nome.toLowerCase().startsWith(t)))
    .slice(0, 60), [lista, naTela, t]);
  return (
    <div className="dm-busca">
      <input autoFocus type="search" value={termo} onChange={e => setTermo(e.target.value)} placeholder="Nome ou descrição da tabela"
        aria-label="Buscar tabela para adicionar" onKeyDown={e => { if (e.key === 'Enter' && achadas[0]) onEscolher(achadas[0].nome); }} />
      {!lista ? <p className="dm-nota">Carregando as tabelas…</p>
        : achadas.length ? (
          <ul>{achadas.map(x => (
            <li key={x.nome}>
              <button type="button" role="menuitem" onClick={() => onEscolher(x.nome)}>
                <code>{x.nome}</code>{x.descricao && <small>{x.descricao}</small>}
              </button>
            </li>
          ))}</ul>
        ) : <p className="dm-nota">Nenhuma tabela {t ? `com “${termo}”` : ''} fora do diagrama.</p>}
    </div>
  );
}

/**
 * Onde cada tabela precisa ir para nenhuma ficar por cima de outra. As que estão sendo arrastadas ficam firmes;
 * as que a equipe posicionou cedem menos que as do layout automático.
 */
function ajustar(nos: Node<DadosTabela>[], movidas: Record<string, Ponto>, fixas: Set<string> | null): Map<string, Ponto> {
  if (nos.length < 2) return new Map();
  const caixas = nos.map(n => {
    const p = movidas[n.id] ?? n.position;
    return { id: n.id, x: p.x, y: p.y, w: LARGURA, h: n.height ?? 0 };
  });
  const firmes = caixas.filter(c => fixas?.has(c.id));
  const ancora = firmes.length
    ? { x: firmes.reduce((t, c) => t + c.x + c.w / 2, 0) / firmes.length, y: firmes.reduce((t, c) => t + c.y + c.h / 2, 0) / firmes.length }
    : undefined;
  return afastar(caixas, id => (fixas?.has(id) ? 0 : movidas[id] ? 1 : 2), ancora);
}

/** Quem é o lado N (chave estrangeira) e quem é o lado 1: a chave primária fica no destino; sem pista, vale a ordem dos cliques. */
function orientar(a: Ponta, b: Ponta): NovaRelacao {
  const [o, d] = a.pk && !b.pk ? [b, a] : [a, b];
  return { origem: o.tabela, coluna_origem: o.coluna, destino: d.tabela, coluna_destino: d.coluna };
}

function Interno({ modulo, tabelas, onAbrirTabela, onLigou, onClicarTabela }: Props) {
  const [resp, setResp] = useState<RespostaDiagrama | null>(null);
  const [erro, setErro] = useState('');
  const [nivel, setNivel] = useState(1);
  const [apoio, setApoio] = useState(false);
  const [todas, setTodas] = useState(false);
  const [busca, setBusca] = useState('');
  const [sel, setSel] = useState<string | null>(null);
  // ligar colunas: primeira coluna escolhida, depois a pergunta com as duas
  const [ponta, setPonta] = useState<Ponta | null>(null);
  const [proposta, setProposta] = useState<NovaRelacao | null>(null);
  const [obs, setObs] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erroLigar, setErroLigar] = useState('');
  const [aviso, setAviso] = useState('');
  const [recarga, setRecarga] = useState(0);
  const botaoValidar = useRef<HTMLButtonElement>(null);
  // tabelas com todas as colunas à mostra (rodapé "+ N colunas"); depois de abrir, o diagrama centraliza nela
  const [expandidas, setExpandidas] = useState<Set<string>>(new Set());
  const centralizar = useRef<string | null>(null);
  // balão do cursor: aparece depois de uma pausa curta, para não piscar enquanto o mouse atravessa o diagrama
  const [balao, setBalao] = useState<Balao | null>(null);
  const esperaBalao = useRef(0);
  const mostrarBalao = useCallback((b: Balao | null) => {
    clearTimeout(esperaBalao.current);
    if (b) esperaBalao.current = window.setTimeout(() => setBalao(b), 300);
    else setBalao(null);
  }, []);
  useEffect(() => () => clearTimeout(esperaBalao.current), []);
  // tabelas arrastadas pela equipe nesta tela (salvas no servidor; valem para todos). O ref acompanha cada passo do
  // arraste, para o soltar salvar a posição que está na tela (o nó que o React Flow entrega no fim vem sem posição)
  const [movidas, setMovidasEstado] = useState<Record<string, Ponto>>({});
  const movidasRef = useRef<Record<string, Ponto>>({});
  const setMovidas = useCallback((m: Record<string, Ponto>) => { movidasRef.current = m; setMovidasEstado(m); }, []);
  // tabelas sendo arrastadas agora: ficam firmes; as outras saem da frente e voltam quando ela passa
  const [arrastando, setArrastando] = useState<Set<string> | null>(null);
  // recarregar depois de validar uma ligação ou salvar um informativo não reenquadra o diagrama
  const manterVista = useRef(false);
  const nosRef = useRef<Node<DadosTabela>[]>([]); // cartões do layout, para o soltar calcular os afastamentos
  // botão direito: no fundo, adicionar tabela (no ponto clicado); numa tabela, ficha, colunas e remover
  const [menu, setMenu] = useState<MenuDiagrama | null>(null);
  const fecharMenu = useCallback(() => setMenu(null), []);
  const [todasTabelas, setTodasTabelas] = useState<{ modulo: string; lista: { nome: string; descricao: string }[] } | null>(null);
  // arrastar uma coluna até outra: a linha segue o cursor; soltar numa coluna de outra tabela abre a pergunta
  type Arrasto = { de: Ponta; ox: number; oy: number; x0: number; y0: number; x: number; y: number; ativo: boolean; alvo: { tabela: string; coluna: string } | null };
  const [arrasto, setArrasto] = useState<Arrasto | null>(null);
  const arrastoRef = useRef<Arrasto | null>(null);
  const arrastou = useRef(false); // o clique que vem logo depois de um arraste não conta como clique
  // informativo de incidentes (post-it): a pergunta depois de validar e o editor ao clicar numa ligação
  const [nota, setNota] = useState<{ relId: string; juncao: string; texto: string; existe: boolean; nova: boolean } | null>(null);
  const [salvandoNota, setSalvandoNota] = useState(false);
  const [erroNota, setErroNota] = useState('');
  const { fitView, zoomIn, zoomOut, setCenter, getZoom, screenToFlowPosition } = useReactFlow();
  const tema = useTema();

  const chave = tabelas.join(',');
  useEffect(() => { setExpandidas(new Set()); }, [modulo, chave]);
  useEffect(() => {
    if (!chave) { setResp(null); return; }
    setErro('');
    fetch(`/api/modulos/${modulo}/diagrama?tabelas=${encodeURIComponent(chave)}&nivel=${nivel}&apoio=${apoio}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then((d: RespostaDiagrama) => { setResp(d); setMovidas(d.posicoes ?? {}); if (!recarga) setSel(null); })
      .catch(e => setErro(`Não foi possível carregar o diagrama (${e.message}).`));
    // recarga só pede os dados de novo (depois de ligar colunas), sem perder a tabela selecionada
  }, [modulo, chave, nivel, apoio, recarga]);

  const ehPk = useCallback((tabela: string, coluna: string) =>
    !!resp?.tabelas.find(t => t.nome === tabela)?.colunas.find(c => c.nome === coluna)?.pk, [resp]);

  const cancelarLigacao = useCallback(() => { setPonta(null); setProposta(null); setObs(''); setErroLigar(''); }, []);

  // 1º clique marca a coluna; clique na mesma desmarca; na mesma tabela troca; na coluna de outra tabela pergunta
  const escolherColuna = useCallback((tabela: string, coluna: string) => {
    if (proposta || nota) return;
    if (arrastou.current) { arrastou.current = false; return; }
    const nova = { tabela, coluna, pk: ehPk(tabela, coluna) };
    if (!ponta || ponta.tabela === tabela) { setPonta(ponta?.tabela === tabela && ponta.coluna === coluna ? null : nova); return; }
    setProposta(orientar(ponta, nova));
  }, [ponta, proposta, nota, ehPk]);

  const iniciarArrasto = useCallback((tabela: string, coluna: string, e: React.PointerEvent<HTMLElement>) => {
    if (proposta || nota) return;
    const r = e.currentTarget.getBoundingClientRect();
    const a: Arrasto = { de: { tabela, coluna, pk: ehPk(tabela, coluna) }, ox: r.right, oy: r.top + r.height / 2,
                         x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, ativo: false, alvo: null };
    arrastoRef.current = a;
    setArrasto(a);
  }, [proposta, nota, ehPk]);
  const emArrasto = !!arrasto;
  useEffect(() => {
    if (!emArrasto) return;
    const mover = (e: PointerEvent) => {
      const a = arrastoRef.current;
      if (!a) return;
      const ativo = a.ativo || Math.hypot(e.clientX - a.x0, e.clientY - a.y0) > 6;
      let alvo: Arrasto['alvo'] = null;
      if (ativo) {
        const el = (document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null)?.closest<HTMLElement>('.tb-col[data-tabela]');
        if (el && el.dataset.tabela !== a.de.tabela) alvo = { tabela: el.dataset.tabela!, coluna: el.dataset.coluna! };
      }
      arrastoRef.current = { ...a, x: e.clientX, y: e.clientY, ativo, alvo };
      setArrasto(arrastoRef.current);
    };
    const soltar = () => {
      const a = arrastoRef.current;
      arrastoRef.current = null;
      setArrasto(null);
      if (!a?.ativo) return;
      arrastou.current = true;
      window.setTimeout(() => { arrastou.current = false; }, 0); // o click (se vier) chega antes disso
      if (a.alvo) { setPonta(null); setProposta(orientar(a.de, { ...a.alvo, pk: ehPk(a.alvo.tabela, a.alvo.coluna) })); }
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
    return () => { window.removeEventListener('pointermove', mover); window.removeEventListener('pointerup', soltar); };
  }, [emArrasto, ehPk]);

  // foco no Validar ao abrir a pergunta, sem rolar o diagrama (autoFocus rola o canvas e corta o topo)
  const abriu = !!proposta;
  useEffect(() => { if (abriu) botaoValidar.current?.focus({ preventScroll: true }); }, [abriu]);

  useEffect(() => {
    if (!ponta && !proposta && !nota) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { cancelarLigacao(); setNota(null); setErroNota(''); } };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [ponta, proposta, nota, cancelarLigacao]);

  const validar = async () => {
    if (!proposta) return;
    setEnviando(true); setErroLigar('');
    try {
      const rel = await api.ligarColunas(modulo, { ...proposta, observacao: obs });
      cancelarLigacao();
      const juncao = rel.colunas.map(([a, b]) => `${rel.origem}.${a} → ${rel.destino}.${b}`).join(', ');
      setAviso(`Ligação validada: ${juncao}`);
      setNota({ relId: rel.id, juncao, texto: rel.nota?.texto ?? '', existe: !!rel.nota, nova: true });
      manterVista.current = true;
      setRecarga(n => n + 1);
      onLigou?.();
    } catch (e) {
      setErroLigar((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };
  useEffect(() => { if (!aviso) return; const t = window.setTimeout(() => setAviso(''), 4000); return () => clearTimeout(t); }, [aviso]);

  const editarNota = useCallback((relId: string) => {
    const r = resp?.relacoes.find(x => x.id === relId);
    if (!r || proposta) return;
    setErroNota('');
    setNota({ relId, juncao: r.colunas.map(([a, b]) => `${r.origem}.${a} → ${r.destino}.${b}`).join(', '),
              texto: r.nota?.texto ?? '', existe: !!r.nota, nova: false });
  }, [resp, proposta]);
  const moverNota = useCallback((relId: string, posicao: number) => {
    api.notaRelacao(modulo, relId, { posicao }).catch(e => setErro(`Não foi possível mover o informativo (${(e as Error).message}).`));
  }, [modulo]);
  const salvarNota = async () => {
    if (!nota) return;
    setSalvandoNota(true); setErroNota('');
    try {
      await api.notaRelacao(modulo, nota.relId, { texto: nota.texto });
      setNota(null);
      setAviso('Informativo de incidentes salvo: arraste o post-it ao longo da linha para posicionar.');
      manterVista.current = true;
      setRecarga(n => n + 1);
    } catch (e) {
      setErroNota((e as Error).message);
    } finally {
      setSalvandoNota(false);
    }
  };
  const apagarNota = async () => {
    if (!nota) return;
    setSalvandoNota(true); setErroNota('');
    try {
      await api.apagarNota(modulo, nota.relId);
      setNota(null);
      manterVista.current = true;
      setRecarga(n => n + 1);
    } catch (e) {
      setErroNota((e as Error).message);
    } finally {
      setSalvandoNota(false);
    }
  };
  const abriuNota = !!nota;
  const campoNota = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (abriuNota) campoNota.current?.focus({ preventScroll: true }); }, [abriuNota]);

  // mover tabelas: a posição acompanha o arraste; as vizinhas no caminho se afastam; ao soltar, salva a arrastada
  // e as que precisaram sair do lugar
  const onNodesChange = useCallback((mudancas: NodeChange<Node<DadosTabela>>[]) => {
    const novas: Record<string, Ponto> = {};
    mudancas.forEach(m => {
      if (m.type === 'position' && m.position && Number.isFinite(m.position.x) && Number.isFinite(m.position.y)) novas[m.id] = m.position;
    });
    if (Object.keys(novas).length) setMovidas({ ...movidasRef.current, ...novas });
  }, [setMovidas]);
  const pegarTabela = useCallback((_: unknown, __: Node, arrastados: Node[]) => {
    mostrarBalao(null);
    setArrastando(new Set(arrastados.map(n => n.id)));
  }, [mostrarBalao]);
  const soltarTabela = useCallback((_: unknown, __: Node, arrastados: Node[]) => {
    const fixas = new Set(arrastados.map(n => n.id));
    setArrastando(null);
    const atuais = movidasRef.current;
    const novas: Record<string, Ponto> = {};
    fixas.forEach(id => { if (atuais[id]) novas[id] = atuais[id]; });
    ajustar(nosRef.current, atuais, fixas).forEach((p, id) => { novas[id] = p; });
    if (!Object.keys(novas).length) return;
    setMovidas({ ...atuais, ...novas });
    api.salvarPosicoes(modulo, chave, Object.entries(novas).map(([tabela, p]) => ({ tabela, x: Math.round(p.x), y: Math.round(p.y) })))
      .catch(e => setErro(`Não foi possível salvar a posição (${(e as Error).message}).`));
  }, [modulo, chave, setMovidas]);
  const reorganizar = async () => {
    try {
      await api.reorganizar(modulo, chave);
      setMovidas({});
      requestAnimationFrame(() => fitView({ padding: 0.12, duration: 300 }));
    } catch (e) {
      setErro(`Não foi possível reorganizar (${(e as Error).message}).`);
    }
  };

  // colunas que participam de ligações (lado de cada tabela)
  const chavesPorTabela = useMemo(() => {
    const m = new Map<string, Set<string>>();
    resp?.relacoes.forEach(r => r.colunas.forEach(([a, b]) => {
      (m.get(r.origem) ?? m.set(r.origem, new Set()).get(r.origem)!).add(a);
      (m.get(r.destino) ?? m.set(r.destino, new Set()).get(r.destino)!).add(b);
    }));
    return m;
  }, [resp]);

  // posições e trajetos: ELK (layered, roteamento ortogonal). Cada coluna é uma porta do cartão, na altura exata
  // da linha; o ELK posiciona as tabelas e desvia as ligações dos cartões. Só recalcula quando muda o conjunto
  // de tabelas ou o modo de colunas.
  const [base, setBase] = useState<{ nos: Node<DadosTabela>[]; arestas: Edge<DadosRelacao>[] }>({ nos: [], arestas: [] });
  useEffect(() => {
    if (!resp) { setBase({ nos: [], arestas: [] }); return; }
    let cancelado = false;
    const nos = resp.tabelas.map(t => {
      const chaves = chavesPorTabela.get(t.nome) ?? new Set<string>();
      let resumidas = t.colunas.filter(c => c.pk || chaves.has(c.nome));
      if (!resumidas.length) resumidas = t.colunas.slice(0, 3);
      const expandida = !todas && expandidas.has(t.nome) && resumidas.length < t.colunas.length;
      const visiveis = todas || expandida ? t.colunas : resumidas;
      const altura = BORDA * 2 + CAB + visiveis.length * LINHA + (t.colunas.length > visiveis.length || expandida ? RODAPE : 0);
      return {
        id: t.nome, type: 'tabela', position: { x: 0, y: 0 }, width: LARGURA, height: altura,
        data: { nome: t.nome, engine: t.engine, foco: t.foco, apoio: t.apoio, adicionada: !!t.adicionada, colunas: visiveis, ocultas: t.colunas.length - visiveis.length,
                chaves, acesas: new Set<string>(), estado: 'normal', selecionada: false, busca: '',
                marcadas: new Set<string>(), onColuna: () => {}, expandida, onExpandir: () => {},
                telas: t.telas ?? [], onBalao: () => {}, onArrastarColuna: () => {}, alvo: null }
      } as Node<DadosTabela>;
    });
    const linhaDe = new Map(nos.map(n => [n.id, new Map(n.data.colunas.map((c, i) => [c.nome, i]))]));

    // uma linha por par de colunas: relação composta (loja + número + série) liga cada coluna à sua correspondente
    const arestas = resp.relacoes.flatMap(r => {
      const juncao = r.colunas.map(([a, b]) => `${r.origem}.${a} = ${r.destino}.${b}`).join(' e ');
      return r.colunas
        .filter(([a, b]) => linhaDe.get(r.origem)?.has(a) && linhaDe.get(r.destino)?.has(b))
        .map(([a, b], i) => ({
          id: `${r.id}#${i}`, source: r.origem, target: r.destino, type: 'relacao',
          sourceHandle: `${a}-s`, targetHandle: `${b}-t`,
          data: { estado: r.estado, destaque: false, apagada: false, juncao, primeira: i === 0, colOrigem: a, colDestino: b,
                  relId: r.id, nota: r.nota }
        } as Edge<DadosRelacao>));
    });

    // tabela adicionada à mão que já tem lugar salvo fica fora do layout automático: assim, pôr (ou expandir) uma
    // tabela no diagrama não faz as outras mudarem de lugar
    const foraDoLayout = new Set(resp.tabelas.filter(t => t.adicionada && resp.posicoes?.[t.nome]).map(t => t.nome));

    // portas: saída à direita na coluna de origem (FK), entrada à esquerda na coluna de destino (PK)
    const portas = new Map<string, { id: string; x: number; y: number; width: number; height: number; layoutOptions: Record<string, string> }[]>();
    const porta = (no: string, col: string, lado: 'E' | 'W') => {
      const id = `${no}::${col}::${lado}`;
      const lista = portas.get(no) ?? portas.set(no, []).get(no)!;
      if (!lista.some(p => p.id === id)) {
        lista.push({ id, x: lado === 'E' ? LARGURA : 0, y: yColuna(linhaDe.get(no)!.get(col)!), width: 0, height: 0,
                     layoutOptions: { 'elk.port.side': lado === 'E' ? 'EAST' : 'WEST' } });
      }
      return id;
    };
    const grafo: ElkNode = {
      id: 'raiz',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.layered.spacing.nodeNodeBetweenLayers': '120',
        'elk.spacing.nodeNode': '44',
        'elk.layered.spacing.edgeNodeBetweenLayers': '24',
        'elk.spacing.edgeNode': '18',
        'elk.spacing.edgeEdge': '9',
        'elk.layered.spacing.edgeEdgeBetweenLayers': '9',
        'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
        'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES'
      },
      edges: arestas.filter(e => !foraDoLayout.has(e.source) && !foraDoLayout.has(e.target))
        .map(e => ({ id: e.id, sources: [porta(e.source, e.data!.colOrigem, 'E')], targets: [porta(e.target, e.data!.colDestino, 'W')] })),
      children: []
    };
    grafo.children = nos.filter(n => !foraDoLayout.has(n.id)).map(n => ({ id: n.id, width: LARGURA, height: n.height!, ports: portas.get(n.id) ?? [],
                                     layoutOptions: { 'elk.portConstraints': 'FIXED_POS' } }));

    elk.layout(grafo).then(res => {
      if (cancelado) return;
      const pos = new Map((res.children ?? []).map(c => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));
      const trajetos = new Map((res.edges ?? []).map(e => {
        const s = e.sections?.[0];
        return [e.id, s ? [s.startPoint, ...(s.bendPoints ?? []), s.endPoint] : undefined] as const;
      }));
      setBase({
        nos: nos.map(n => ({ ...n, position: pos.get(n.id) ?? n.position })),
        arestas: arestas.map(e => ({ ...e, data: { ...e.data!, pontos: trajetos.get(e.id) } }))
      });
    }).catch(() => {
      // sem o ELK, cai no traçado padrão do React Flow (empilha as tabelas em coluna)
      if (!cancelado) setBase({ nos: nos.map((n, i) => ({ ...n, position: { x: (i % 4) * (LARGURA + 120), y: Math.floor(i / 4) * 260 } })), arestas });
    });
    return () => { cancelado = true; };
  }, [resp, todas, chavesPorTabela, expandidas]);

  // destaque: sem seleção, ilumina as tabelas da tela e as ligações delas; com seleção, só a tabela escolhida e vizinhas
  const termo = busca.trim().toLowerCase();
  const expandir = useCallback((tabela: string) => {
    setSel(tabela);
    setExpandidas(atual => {
      const novo = new Set(atual);
      if (novo.has(tabela)) novo.delete(tabela); else { novo.add(tabela); centralizar.current = tabela; }
      return novo;
    });
  }, []);
  // posições na tela: as salvas/arrastadas e, por cima, os afastamentos para nenhuma tabela ficar sobre outra
  useLayoutEffect(() => { nosRef.current = base.nos; }, [base.nos]);
  const ajustes = useMemo(() => ajustar(base.nos, movidas, arrastando), [base.nos, movidas, arrastando]);
  // tabelas movidas (pela equipe ou para abrir espaço): as ligações delas, e as do layout automático que uma tabela
  // movida passou a cobrir, ganham um trajeto novo que contorna todos os cartões (recalculado a cada passo do arraste)
  const rotas = useMemo(() => {
    const saiu = new Set([...Object.keys(movidas), ...ajustes.keys()]);
    const rotas = new Map<string, Ponto[]>();
    if (!saiu.size) return rotas;
    const pos = new Map(base.nos.map(n => [n.id, ajustes.get(n.id) ?? movidas[n.id] ?? n.position]));
    const caixas = base.nos.map(n => ({ id: n.id, ...pos.get(n.id)!, w: LARGURA, h: n.height ?? 0 }));
    const cobertas = caixas.filter(c => saiu.has(c.id));
    const linha = new Map(base.nos.map(n => [n.id, new Map(n.data.colunas.map((c, i) => [c.nome, i]))]));
    const alvo = base.arestas.filter(e => saiu.has(e.source) || saiu.has(e.target) || (e.data!.pontos && atravessa(e.data!.pontos, cobertas)));
    const ligs = alvo.map(e => {
      const a = pos.get(e.source)!, b = pos.get(e.target)!;
      return { de: { x: a.x + LARGURA, y: a.y + yColuna(linha.get(e.source)!.get(e.data!.colOrigem)!) },
               para: { x: b.x, y: b.y + yColuna(linha.get(e.target)!.get(e.data!.colDestino)!) } };
    });
    const rotear = criarRoteador(caixas, ligs);
    alvo.forEach((e, k) => { const r = rotear(ligs[k]); if (r) rotas.set(e.id, r); });
    return rotas;
  }, [base, movidas, ajustes]);
  const { nos, arestas } = useMemo(() => {
    const marcadas = new Map<string, Set<string>>();
    const marcar = (t: string, c: string) => (marcadas.get(t) ?? marcadas.set(t, new Set()).get(t)!).add(c);
    if (proposta) { marcar(proposta.origem, proposta.coluna_origem); marcar(proposta.destino, proposta.coluna_destino); }
    else if (ponta) marcar(ponta.tabela, ponta.coluna);
    const foco = new Set(resp?.foco ?? []);
    // escolhendo colunas para ligar: nada fica apagado, para a segunda tabela estar à vista
    const ligando = !!ponta || !!proposta;
    // arrastando uma tabela, nada fica apagado: as ligações dela (e das outras) continuam à vista
    const apagar = !!sel && !ligando && !arrastando;
    const centro = sel ? new Set([sel]) : foco;
    const vizinhas = new Set<string>(centro);
    base.arestas.forEach(e => { if (centro.has(e.source)) vizinhas.add(e.target); if (centro.has(e.target)) vizinhas.add(e.source); });
    // colunas nas pontas das linhas acesas ficam marcadas nos dois cartões
    const acesas = new Map<string, Set<string>>();
    const acender = (t: string, c: string) => (acesas.get(t) ?? acesas.set(t, new Set()).get(t)!).add(c);
    base.arestas.forEach(e => {
      if (centro.has(e.source) || centro.has(e.target)) { acender(e.source, e.data!.colOrigem); acender(e.target, e.data!.colDestino); }
    });
    const alvo = arrasto?.alvo;
    return {
      nos: base.nos.map(n => ({
        ...n,
        position: ajustes.get(n.id) ?? movidas[n.id] ?? n.position,
        data: { ...n.data, selecionada: n.id === sel, busca: termo, acesas: acesas.get(n.id) ?? new Set<string>(),
                estado: apagar ? (vizinhas.has(n.id) ? 'ativo' : 'apagado') : 'normal',
                marcadas: marcadas.get(n.id) ?? new Set<string>(), onColuna: escolherColuna, onExpandir: expandir, onBalao: mostrarBalao,
                onArrastarColuna: iniciarArrasto, alvo: alvo?.tabela === n.id ? alvo.coluna : null }
      })) as Node<DadosTabela>[],
      arestas: base.arestas.map(e => {
        const toca = centro.has(e.source) || centro.has(e.target);
        // tabela arrastada ou afastada: trajeto novo que contorna os cartões; sem caminho, o traçado simples
        const saiu = (id: string) => !!movidas[id] || ajustes.has(id);
        const pontos = rotas.get(e.id) ?? (saiu(e.source) || saiu(e.target) ? undefined : e.data!.pontos);
        return { ...e, zIndex: toca ? 2 : 0, data: { ...e.data!, pontos, destaque: toca, apagada: apagar && !toca,
                                                     onMoverNota: moverNota, onEditarNota: editarNota } };
      }) as Edge<DadosRelacao>[]
    };
  }, [base, sel, resp, termo, ponta, proposta, escolherColuna, expandir, mostrarBalao, movidas, ajustes, rotas, arrastando, arrasto?.alvo, iniciarArrasto, moverNota, editarNota]);

  useEffect(() => {
    if (!base.nos.length) return;
    if (manterVista.current) { manterVista.current = false; return; }
    const alvo = centralizar.current;
    centralizar.current = null;
    const no = alvo ? base.nos.find(n => n.id === alvo) : undefined;
    // tabela expandida: centraliza nela pela posição do layout (fitView com nós ainda não medidos não faz nada)
    if (no) setCenter(no.position.x + LARGURA / 2, no.position.y + (no.height ?? 0) / 2, { zoom: Math.max(getZoom(), 0.85), duration: 400 });
    else requestAnimationFrame(() => fitView({ padding: 0.12, duration: 300 }));
  }, [base, fitView, setCenter, getZoom]);

  // reenquadra quando o painel muda de tamanho (abrir a ficha da tabela, redimensionar a janela)
  const [canvas, setCanvas] = useState<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!canvas) return;
    let t = 0;
    const ro = new ResizeObserver(() => { clearTimeout(t); t = window.setTimeout(() => fitView({ padding: 0.12, duration: 200 }), 120); });
    ro.observe(canvas);
    return () => { clearTimeout(t); ro.disconnect(); };
  }, [canvas, fitView]);

  const buscar = useCallback(() => {
    if (!termo) return;
    const achados = base.nos.filter(n => n.id.includes(termo) || n.data.colunas.some(c => c.nome.toLowerCase().includes(termo)));
    if (achados.length) fitView({ nodes: achados.map(n => ({ id: n.id })), padding: 0.3, duration: 400 });
  }, [termo, base, fitView]);

  // botão direito no fundo: adicionar tabela no ponto clicado; numa tabela: ações dela
  const abrirMenu = (e: React.MouseEvent | MouseEvent, tabela?: string) => {
    e.preventDefault();
    if (proposta || nota) return;
    mostrarBalao(null);
    const flow = screenToFlowPosition({ x: e.clientX, y: e.clientY });
    setMenu({ x: e.clientX, y: e.clientY, flow, tabela, buscando: false });
  };
  const buscarParaAdicionar = () => {
    setMenu(m => (m ? { ...m, buscando: true } : m));
    if (todasTabelas?.modulo !== modulo) {
      api.tabelasDoModulo(modulo).then(lista => setTodasTabelas({ modulo, lista }))
        .catch(e => setErro(`Não foi possível listar as tabelas (${(e as Error).message}).`));
    }
  };
  const adicionarTabela = async (nome: string) => {
    if (!menu) return;
    const { flow } = menu;
    setMenu(null);
    try {
      // o cartão fica com o cabeçalho no ponto clicado
      await api.adicionarTabela(modulo, chave, nome, flow.x - LARGURA / 2, flow.y - CAB / 2);
      setExpandidas(atual => new Set(atual).add(nome)); // todas as colunas à mostra, para escolher qual ligar
      manterVista.current = true;
      setRecarga(n => n + 1);
      setAviso(`${nome} adicionada: arraste uma coluna dela até a coluna de outra tabela para ligar.`);
    } catch (e) {
      setErro(`Não foi possível adicionar ${nome} (${(e as Error).message}).`);
    }
  };
  const removerTabela = async (nome: string) => {
    setMenu(null);
    try {
      await api.removerTabela(modulo, chave, nome);
      if (sel === nome) setSel(null);
      manterVista.current = true;
      setRecarga(n => n + 1);
    } catch (e) {
      setErro(`Não foi possível remover ${nome} (${(e as Error).message}).`);
    }
  };
  const naTela = new Set(resp?.tabelas.map(t => t.nome) ?? []);
  const tabelaDoMenu = menu?.tabela ? resp?.tabelas.find(t => t.nome === menu.tabela) : undefined;

  if (!tabelas.length) return <div className="diag-vazio">Nenhuma tabela vinculada a esta tela. Vincule a primeira no campo acima do diagrama.</div>;

  return (
    <div className="diag-wrap">
      <div className="diag-barra">
        <button type="button" onClick={() => zoomOut({ duration: 200 })} aria-label="Afastar">−</button>
        <button type="button" onClick={() => zoomIn({ duration: 200 })} aria-label="Aproximar">+</button>
        <button type="button" onClick={() => fitView({ padding: 0.12, duration: 300 })} aria-label="Enquadrar" title="Enquadrar tudo">⤢</button>
        <span className="diag-sep" />
        <select id="diag-colunas" value={todas ? 'todas' : 'chaves'} onChange={e => setTodas(e.target.value === 'todas')} aria-label="Colunas exibidas">
          <option value="chaves">Chaves e ligações</option>
          <option value="todas">Todas as colunas</option>
        </select>
        <select id="diag-nivel" value={nivel} onChange={e => setNivel(+e.target.value)} aria-label="Níveis de ligação">
          <option value={0}>Só a tela</option>
          <option value={1}>+ 1 nível</option>
          <option value={2}>+ 2 níveis</option>
        </select>
        <label className="diag-check"><input id="diag-apoio" type="checkbox" checked={apoio} onChange={e => setApoio(e.target.checked)} /> Tabelas de apoio</label>
        <input id="diag-busca" type="search" placeholder="Buscar tabela ou coluna (Enter)" value={busca}
          onChange={e => setBusca(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') buscar(); }} />
        {Object.keys(movidas).length > 0 && (
          <button type="button" className="diag-reorganizar" onClick={reorganizar} title="Desfaz as posições arrastadas desta tela (para todos)">Reorganizar</button>
        )}
        <span className="diag-dica">Botão direito no fundo para adicionar uma tabela · arraste a tabela pelo nome para organizar (as outras abrem espaço) · arraste uma coluna até a de outra tabela para ligar · clique numa ligação para o informativo de incidentes</span>
      </div>
      <div className="diag-canvas" ref={setCanvas}>
      <ReactFlow
        nodes={nos} edges={arestas} nodeTypes={tiposNo} edgeTypes={tiposAresta}
        nodesConnectable={false} edgesFocusable={false} minZoom={0.15} maxZoom={1.6} colorMode={tema === 'escuro' ? 'dark' : 'light'}
        onNodesChange={onNodesChange} onNodeDragStart={pegarTabela} onNodeDragStop={soltarTabela} nodeDragThreshold={4}
        onEdgeClick={(_, e) => editarNota(e.data!.relId)}
        fitView fitViewOptions={{ padding: 0.12 }}
        onNodeClick={(_, n) => { setSel(n.id === sel ? null : n.id); onClicarTabela?.(n.id); }}
        onNodeDoubleClick={(_, n) => onAbrirTabela(n.id)}
        onPaneClick={() => { if (arrastou.current) return; setSel(null); if (!proposta) setPonta(null); }}
        onMoveStart={() => { mostrarBalao(null); setMenu(null); }}
        onPaneContextMenu={e => abrirMenu(e)}
        onNodeContextMenu={(e, n) => abrirMenu(e, n.id)}
        proOptions={{ hideAttribution: true }}
      >
      <Background gap={22} size={1.2} />
      <Panel position="bottom-left" className="diag-legenda">
        <span><i className="lg-foco" />Tabela da tela</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" className="lg-linha" /></svg>Confirmada / documentada</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" className="lg-linha sug" /></svg>Sugerida</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" className="lg-linha nota" /></svg>Com informativo de incidentes</span>
        <span><b className="rel-marca estatica">N</b>→<b className="rel-marca estatica">1</b> muitas para uma</span>
        {resp && resp.apoio_ocultas.length > 0 && !apoio && <span className="lg-ocultas">Ocultas: {resp.apoio_ocultas.join(', ')}</span>}
      </Panel>
      {ponta && !proposta && (
        <Panel position="top-left" className="diag-ligando" role="status">
          <span><b>{ponta.tabela}.{ponta.coluna}</b> selecionada · clique na coluna de outra tabela
            {!todas && <> (coluna escondida? clique em “+ N colunas” no rodapé da tabela)</>}</span>
          <button type="button" className="link" onClick={cancelarLigacao}>Cancelar</button>
        </Panel>
      )}
      {proposta && (
        <Panel position="top-center" className="diag-pergunta" role="dialog" aria-labelledby="diag-pergunta-titulo">
          <h3 id="diag-pergunta-titulo">Estas colunas estão relacionadas?</h3>
          <p className="juncao">
            <code>{proposta.origem}.{proposta.coluna_origem}</code><span>N → 1</span><code>{proposta.destino}.{proposta.coluna_destino}</code>
          </p>
          <p className="ajuda">Cada registro de <b>{proposta.origem}</b> aponta para um de <b>{proposta.destino}</b>.{' '}
            <button type="button" className="link" onClick={() => setProposta({ origem: proposta.destino, coluna_origem: proposta.coluna_destino,
              destino: proposta.origem, coluna_destino: proposta.coluna_origem })}>Inverter o sentido</button></p>
          <input type="text" value={obs} maxLength={500} onChange={e => setObs(e.target.value)}
            placeholder="Observação (opcional): ex. conferido no fechamento de caixa" aria-label="Observação" />
          {erroLigar && <p className="erro" role="alert">{erroLigar}</p>}
          <div className="acoes">
            <button type="button" className="btn" onClick={cancelarLigacao} disabled={enviando}>Descartar</button>
            <button type="button" className="btn btn-primario" onClick={validar} disabled={enviando}
              ref={botaoValidar}>
              {enviando ? 'Validando…' : 'Validar'}</button>
          </div>
        </Panel>
      )}
      {nota && (
        <Panel position="top-center" className="diag-pergunta diag-nota" role="dialog" aria-labelledby="diag-nota-titulo">
          <h3 id="diag-nota-titulo">{nota.nova ? 'Adicionar um informativo de incidentes?' : 'Informativo de incidentes'}</h3>
          <p className="juncao"><code>{nota.juncao}</code></p>
          <p className="ajuda">O que acontece com as tabelas ligadas se, num atendimento, o valor desta coluna for apagado ou alterado?
            Fica como um post-it em cima da linha.</p>
          <textarea ref={campoNota} value={nota.texto} maxLength={1000} rows={4} aria-label="Informativo de incidentes"
            onChange={e => setNota({ ...nota, texto: e.target.value })}
            placeholder="Ex.: se o código do cliente for apagado na venda, o crediário perde a ligação com o cadastro e a venda some do extrato." />
          {erroNota && <p className="erro" role="alert">{erroNota}</p>}
          <div className="acoes">
            {nota.existe && <button type="button" className="btn btn-perigo" onClick={apagarNota} disabled={salvandoNota}>Apagar</button>}
            <button type="button" className="btn" onClick={() => { setNota(null); setErroNota(''); }} disabled={salvandoNota}>
              {nota.nova ? 'Agora não' : 'Fechar'}</button>
            <button type="button" className="btn btn-primario" onClick={salvarNota} disabled={salvandoNota || !nota.texto.trim()}>
              {salvandoNota ? 'Salvando…' : nota.existe ? 'Salvar' : 'Adicionar informativo'}</button>
          </div>
        </Panel>
      )}
      {aviso && !nota && <Panel position="top-center" className="diag-ligando" role="status">{aviso}</Panel>}
      {sel && !ponta && !proposta && !nota && (
        <Panel position="top-left" className="diag-sel">
          <b>{sel}</b> · {arestas.filter(e => e.data!.destaque).length} ligações
          <button type="button" className="link" onClick={() => onAbrirTabela(sel)}>Abrir ficha</button>
        </Panel>
      )}
      {erro && <Panel position="top-center" className="diag-erro">{erro}</Panel>}
      </ReactFlow>
      </div>
      {balao && !arrasto?.ativo && !menu && <BalaoFlutuante b={balao} />}
      {menu && (
        <MenuContexto m={menu} onFechar={fecharMenu}>
          {menu.buscando ? (
            <BuscaTabela lista={todasTabelas?.modulo === modulo ? todasTabelas.lista : null} naTela={naTela} onEscolher={adicionarTabela} />
          ) : menu.tabela ? (<>
            <div className="dm-titulo"><code>{menu.tabela}</code></div>
            <button type="button" role="menuitem" onClick={() => { setMenu(null); onAbrirTabela(menu.tabela!); }}>Abrir ficha</button>
            {!todas && (
              <button type="button" role="menuitem" onClick={() => { setMenu(null); expandir(menu.tabela!); }}>
                {expandidas.has(menu.tabela) ? 'Recolher colunas' : 'Mostrar todas as colunas'}</button>
            )}
            {tabelaDoMenu?.adicionada
              ? <button type="button" role="menuitem" className="perigo" onClick={() => removerTabela(menu.tabela!)}>Remover do diagrama</button>
              : <small className="dm-nota">{tabelaDoMenu?.foco ? 'Tabela da tela' : 'Veio pelas ligações'}: não sai do diagrama.</small>}
          </>) : (<>
            <button type="button" role="menuitem" onClick={buscarParaAdicionar}>Adicionar tabela…</button>
            <button type="button" role="menuitem" onClick={() => { setMenu(null); fitView({ padding: 0.12, duration: 300 }); }}>Enquadrar tudo</button>
            {Object.keys(movidas).length > 0 && (
              <button type="button" role="menuitem" onClick={() => { setMenu(null); reorganizar(); }}>Reorganizar</button>
            )}
          </>)}
        </MenuContexto>
      )}
      {arrasto?.ativo && createPortal(
        <svg className="diag-arrasto" aria-hidden="true">
          <line x1={arrasto.ox} y1={arrasto.oy} x2={arrasto.x} y2={arrasto.y} className={arrasto.alvo ? 'no-alvo' : ''} />
          <circle cx={arrasto.x} cy={arrasto.y} r={5} className={arrasto.alvo ? 'no-alvo' : ''} />
        </svg>,
        document.body
      )}
    </div>
  );
}

/** Diagrama ER das tabelas de uma tela, com as ligações iluminadas. */
export default function Diagrama(props: Props) {
  return <ReactFlowProvider><Interno {...props} /></ReactFlowProvider>;
}
