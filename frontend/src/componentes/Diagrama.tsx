import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background, BaseEdge, EdgeLabelRenderer, Handle, Panel, Position, ReactFlow, ReactFlowProvider, getSmoothStepPath, useReactFlow,
  type Edge, type EdgeProps, type Node, type NodeProps
} from '@xyflow/react';
import { api } from '../api';
import { useTema } from '../tema';
import '@xyflow/react/dist/style.css';
import ELK from 'elkjs/lib/elk.bundled.js';
import type { ElkNode } from 'elkjs/lib/elk-api';
import type { NovaRelacao, Relacao } from '../tipos';

const elk = new ELK();

type Coluna = { nome: string; tipo: string; pk: boolean };
type TabelaDiag = { nome: string; engine: string; linhas: number | null; foco: boolean; apoio: boolean; colunas: Coluna[] };
type RespostaDiagrama = { foco: string[]; tabelas: TabelaDiag[]; relacoes: Relacao[]; apoio_ocultas: string[] };

type DadosTabela = {
  nome: string; engine: string; foco: boolean; apoio: boolean; colunas: Coluna[]; ocultas: number;
  chaves: Set<string>; acesas: Set<string>; estado: 'normal' | 'ativo' | 'apagado'; selecionada: boolean; busca: string;
  marcadas: Set<string>; onColuna: (tabela: string, coluna: string) => void; // colunas escolhidas para ligar
  expandida: boolean; onExpandir: (tabela: string) => void; // todas as colunas só desta tabela
};
type Ponta = { tabela: string; coluna: string; pk: boolean };
// uma aresta por par de colunas; "primeira" leva as marcas N/1 da relação
type Ponto = { x: number; y: number };
type DadosRelacao = {
  estado: Relacao['estado']; destaque: boolean; apagada: boolean; juncao: string; primeira: boolean; colOrigem: string; colDestino: string;
  pontos?: Ponto[]; // trajeto calculado pelo ELK (contorna os cartões)
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
  return (
    <div className={`tb ${data.foco ? 'tb-foco' : ''} ${data.selecionada ? 'tb-sel' : ''} tb-${data.estado}`}>
      <div className="tb-cab">
        <span className={b && data.nome.toLowerCase().includes(b) ? 'achou' : undefined}>{data.nome}</span>
        {data.apoio && <em title="Tabela de apoio: muitas outras tabelas apontam para ela">apoio</em>}
        <small>{data.engine}</small>
      </div>
      {data.colunas.map(c => (
        <div key={c.nome} className={`tb-col ${c.pk ? 'pk' : ''} ${data.chaves.has(c.nome) ? 'fk' : ''} ${data.acesas.has(c.nome) ? 'ligada' : ''} ${b && c.nome.toLowerCase().includes(b) ? 'achou' : ''} ${data.marcadas.has(c.nome) ? 'marcada' : ''}`}
          title="Clique para ligar esta coluna à coluna de outra tabela"
          onClick={e => { e.stopPropagation(); data.onColuna(data.nome, c.nome); }}>
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

/* ---------- ligação com marcas N (lado da chave estrangeira) e 1 (lado referenciado) ---------- */
function RelacaoAresta({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<Edge<DadosRelacao>>) {
  const d = data!;
  // trajeto do ELK quando existe; senão, o traçado padrão do React Flow
  const p = d.pontos;
  const caminho = p && p.length > 1 ? caminhoArredondado(p)
    : getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 8, offset: 22 })[0];
  if (p && p.length > 1) { sourceX = p[0].x; sourceY = p[0].y; targetX = p[p.length - 1].x; targetY = p[p.length - 1].y; }
  const est = `${d.destaque ? 'destaque' : ''} ${d.apagada ? 'apagada' : ''}`;
  return (
    <>
      <BaseEdge id={id} path={caminho} className={`rel-aresta ${est} rel-${d.estado}`} />
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

type Props = { modulo: string; tabelas: string[]; onAbrirTabela: (nome: string) => void; onLigou?: () => void };

/** Quem é o lado N (chave estrangeira) e quem é o lado 1: a chave primária fica no destino; sem pista, vale a ordem dos cliques. */
function orientar(a: Ponta, b: Ponta): NovaRelacao {
  const [o, d] = a.pk && !b.pk ? [b, a] : [a, b];
  return { origem: o.tabela, coluna_origem: o.coluna, destino: d.tabela, coluna_destino: d.coluna };
}

function Interno({ modulo, tabelas, onAbrirTabela, onLigou }: Props) {
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
  const { fitView, zoomIn, zoomOut, setCenter, getZoom } = useReactFlow();
  const tema = useTema();

  const chave = tabelas.join(',');
  useEffect(() => { setExpandidas(new Set()); }, [modulo, chave]);
  useEffect(() => {
    if (!chave) { setResp(null); return; }
    setErro('');
    fetch(`/api/modulos/${modulo}/diagrama?tabelas=${encodeURIComponent(chave)}&nivel=${nivel}&apoio=${apoio}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then((d: RespostaDiagrama) => { setResp(d); if (!recarga) setSel(null); })
      .catch(e => setErro(`Não foi possível carregar o diagrama (${e.message}).`));
    // recarga só pede os dados de novo (depois de ligar colunas), sem perder a tabela selecionada
  }, [modulo, chave, nivel, apoio, recarga]);

  const ehPk = useCallback((tabela: string, coluna: string) =>
    !!resp?.tabelas.find(t => t.nome === tabela)?.colunas.find(c => c.nome === coluna)?.pk, [resp]);

  const cancelarLigacao = useCallback(() => { setPonta(null); setProposta(null); setObs(''); setErroLigar(''); }, []);

  // 1º clique marca a coluna; clique na mesma desmarca; na mesma tabela troca; na coluna de outra tabela pergunta
  const escolherColuna = useCallback((tabela: string, coluna: string) => {
    if (proposta) return;
    const nova = { tabela, coluna, pk: ehPk(tabela, coluna) };
    if (!ponta || ponta.tabela === tabela) { setPonta(ponta?.tabela === tabela && ponta.coluna === coluna ? null : nova); return; }
    setProposta(orientar(ponta, nova));
  }, [ponta, proposta, ehPk]);

  // foco no Validar ao abrir a pergunta, sem rolar o diagrama (autoFocus rola o canvas e corta o topo)
  const abriu = !!proposta;
  useEffect(() => { if (abriu) botaoValidar.current?.focus({ preventScroll: true }); }, [abriu]);

  useEffect(() => {
    if (!ponta && !proposta) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') cancelarLigacao(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [ponta, proposta, cancelarLigacao]);

  const validar = async () => {
    if (!proposta) return;
    setEnviando(true); setErroLigar('');
    try {
      const rel = await api.ligarColunas(modulo, { ...proposta, observacao: obs });
      cancelarLigacao();
      setAviso(`Ligação validada: ${rel.colunas.map(([a, b]) => `${rel.origem}.${a} → ${rel.destino}.${b}`).join(', ')}`);
      setRecarga(n => n + 1);
      onLigou?.();
    } catch (e) {
      setErroLigar((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };
  useEffect(() => { if (!aviso) return; const t = window.setTimeout(() => setAviso(''), 4000); return () => clearTimeout(t); }, [aviso]);

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
        data: { nome: t.nome, engine: t.engine, foco: t.foco, apoio: t.apoio, colunas: visiveis, ocultas: t.colunas.length - visiveis.length,
                chaves, acesas: new Set<string>(), estado: 'normal', selecionada: false, busca: '',
                marcadas: new Set<string>(), onColuna: () => {}, expandida, onExpandir: () => {} }
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
          data: { estado: r.estado, destaque: false, apagada: false, juncao, primeira: i === 0, colOrigem: a, colDestino: b }
        } as Edge<DadosRelacao>));
    });

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
      edges: arestas.map(e => ({ id: e.id, sources: [porta(e.source, e.data!.colOrigem, 'E')], targets: [porta(e.target, e.data!.colDestino, 'W')] })),
      children: []
    };
    grafo.children = nos.map(n => ({ id: n.id, width: LARGURA, height: n.height!, ports: portas.get(n.id) ?? [],
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
  const { nos, arestas } = useMemo(() => {
    const marcadas = new Map<string, Set<string>>();
    const marcar = (t: string, c: string) => (marcadas.get(t) ?? marcadas.set(t, new Set()).get(t)!).add(c);
    if (proposta) { marcar(proposta.origem, proposta.coluna_origem); marcar(proposta.destino, proposta.coluna_destino); }
    else if (ponta) marcar(ponta.tabela, ponta.coluna);
    const foco = new Set(resp?.foco ?? []);
    // escolhendo colunas para ligar: nada fica apagado, para a segunda tabela estar à vista
    const ligando = !!ponta || !!proposta;
    const apagar = !!sel && !ligando;
    const centro = sel ? new Set([sel]) : foco;
    const vizinhas = new Set<string>(centro);
    base.arestas.forEach(e => { if (centro.has(e.source)) vizinhas.add(e.target); if (centro.has(e.target)) vizinhas.add(e.source); });
    // colunas nas pontas das linhas acesas ficam marcadas nos dois cartões
    const acesas = new Map<string, Set<string>>();
    const acender = (t: string, c: string) => (acesas.get(t) ?? acesas.set(t, new Set()).get(t)!).add(c);
    base.arestas.forEach(e => {
      if (centro.has(e.source) || centro.has(e.target)) { acender(e.source, e.data!.colOrigem); acender(e.target, e.data!.colDestino); }
    });
    return {
      nos: base.nos.map(n => ({
        ...n,
        data: { ...n.data, selecionada: n.id === sel, busca: termo, acesas: acesas.get(n.id) ?? new Set<string>(),
                estado: apagar ? (vizinhas.has(n.id) ? 'ativo' : 'apagado') : 'normal',
                marcadas: marcadas.get(n.id) ?? new Set<string>(), onColuna: escolherColuna, onExpandir: expandir }
      })) as Node<DadosTabela>[],
      arestas: base.arestas.map(e => {
        const toca = centro.has(e.source) || centro.has(e.target);
        return { ...e, zIndex: toca ? 2 : 0, data: { ...e.data!, destaque: toca, apagada: apagar && !toca } };
      }) as Edge<DadosRelacao>[]
    };
  }, [base, sel, resp, termo, ponta, proposta, escolherColuna, expandir]);

  useEffect(() => {
    if (!base.nos.length) return;
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

  if (!tabelas.length) return <div className="diag-vazio">Nenhuma tabela vinculada a esta tela. Vincule tabelas na aba Visão geral.</div>;

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
        <span className="diag-dica">Clique numa tabela para iluminar as ligações · duplo clique abre a ficha · clique numa coluna e na de outra tabela para ligar</span>
      </div>
      <div className="diag-canvas" ref={setCanvas}>
      <ReactFlow
        nodes={nos} edges={arestas} nodeTypes={tiposNo} edgeTypes={tiposAresta}
        nodesConnectable={false} edgesFocusable={false} minZoom={0.15} maxZoom={1.6} colorMode={tema === 'escuro' ? 'dark' : 'light'}
        fitView fitViewOptions={{ padding: 0.12 }}
        onNodeClick={(_, n) => setSel(n.id === sel ? null : n.id)}
        onNodeDoubleClick={(_, n) => onAbrirTabela(n.id)}
        onPaneClick={() => { setSel(null); if (!proposta) setPonta(null); }}
        proOptions={{ hideAttribution: true }}
      >
      <Background gap={22} size={1.2} />
      <Panel position="bottom-left" className="diag-legenda">
        <span><i className="lg-foco" />Tabela da tela</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" className="lg-linha" /></svg>Confirmada / documentada</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" className="lg-linha sug" /></svg>Sugerida</span>
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
      {aviso && <Panel position="top-center" className="diag-ligando" role="status">{aviso}</Panel>}
      {sel && !ponta && !proposta && (
        <Panel position="top-left" className="diag-sel">
          <b>{sel}</b> · {arestas.filter(e => e.data!.destaque).length} ligações
          <button type="button" className="link" onClick={() => onAbrirTabela(sel)}>Abrir ficha</button>
        </Panel>
      )}
      {erro && <Panel position="top-center" className="diag-erro">{erro}</Panel>}
      </ReactFlow>
      </div>
    </div>
  );
}

/** Diagrama ER das tabelas de uma tela, com as ligações iluminadas. */
export default function Diagrama(props: Props) {
  return <ReactFlowProvider><Interno {...props} /></ReactFlowProvider>;
}
