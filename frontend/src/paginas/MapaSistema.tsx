import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, caminhoTexto } from '../api';
import Diagrama from '../componentes/Diagrama';
import MenuArvore from '../componentes/MenuArvore';
import Topo from '../componentes/Topo';
import type { EstadoRelacao, ManualResumo, MenuFicha, MenuNo, Relacao } from '../tipos';

const MODULO_PADRAO = 'pdv';
const ESTADO_ROTULO: Record<EstadoRelacao, string> = { confirmada: 'Confirmada', documentada: 'Documentada', sugerida: 'Sugerida', descartada: 'Descartada' };

type FichaTabela = {
  nome: string; engine: string; linhas: number | null; descricao: string;
  colunas: { nome: string; tipo: string; pk: boolean }[];
  relacoes: Relacao[]; menus: { id: string; caminho: { titulo: string; atalho: string | null }[] }[];
  manuais: { codigo: string; titulo: string }[];
};

const contar = (nos: MenuNo[]): { total: number; comTabela: number; aDetalhar: number } =>
  nos.reduce((a, n) => {
    const f = contar(n.itens);
    return { total: a.total + 1 + f.total, comTabela: a.comTabela + (n.n_tabelas ? 1 : 0) + f.comTabela, aDetalhar: a.aDetalhar + (n.submenu && !n.itens.length ? 1 : 0) + f.aDetalhar };
  }, { total: 0, comTabela: 0, aDetalhar: 0 });

/** primeira tela (na ordem do menu) que já tem tabelas vinculadas: o "por onde começar" da tela inicial */
const primeiraComTabelas = (nos: MenuNo[]): MenuNo | null => {
  for (const n of nos) {
    if (n.n_tabelas && !n.itens.length) return n;
    const f = primeiraComTabelas(n.itens);
    if (f) return f;
  }
  return null;
};

const quando = (em: string | null) => (em ? new Date(em.replace(' ', 'T')).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '');
const autoria = (por: string | null, em: string | null) => [por && `por ${por}`, em && `em ${quando(em)}`].filter(Boolean).join(' ');

const juncao = (r: Relacao) => r.colunas.map(([a, b]) => (a === b ? a : `${a} = ${b}`)).join(' + ');

function RelacaoLinha({ r, onStatus }: { r: Relacao; onStatus: (r: Relacao, s: 'documentada' | 'descartada' | 'sugerida') => void }) {
  return (
    <li className={`rel rel-${r.estado}`}>
      <div className="rel-topo">
        <span className={`estado estado-${r.estado}`}>{ESTADO_ROTULO[r.estado]}</span>
        <code>{r.origem} → {r.destino}</code>
      </div>
      <div className="rel-juncao">por <code>{juncao(r)}</code></div>
      {r.estado === 'sugerida' && r.motivo && <div className="rel-motivo">Sugerida porque {r.motivo}.</div>}
      {(r.estado === 'documentada' || r.estado === 'descartada') && (r.por || r.em) && (
        <div className="rel-autoria">{r.estado === 'documentada' ? 'Validada' : 'Descartada'} {autoria(r.por, r.em)}</div>
      )}
      {r.estado !== 'confirmada' && (
        <div className="rel-acoes">
          {r.estado === 'sugerida' && <>
            <button type="button" className="btn btn-p" onClick={() => onStatus(r, 'documentada')}>Validar</button>
            <button type="button" className="btn btn-p" onClick={() => onStatus(r, 'descartada')}>Descartar</button>
          </>}
          {r.estado === 'documentada' && <button type="button" className="btn btn-p" onClick={() => onStatus(r, 'sugerida')}>Desfazer validação</button>}
        </div>
      )}
    </li>
  );
}

export default function MapaSistema() {
  const [params, setParams] = useSearchParams();
  const selecionado = params.get('item');
  // módulo do mapa: o da tela escolhida (prefixo do id, "adm.cadastros…") ou o do ?modulo= (vindo do topo)
  const MODULO = selecionado?.split('.')[0] || params.get('modulo') || MODULO_PADRAO;
  const tabelaSel = params.get('tabela');
  const [menus, setMenus] = useState<MenuNo[]>([]);
  const [nomesTabelas, setNomesTabelas] = useState<string[]>([]);
  const [ficha, setFicha] = useState<MenuFicha | null>(null);
  const [fichaTabela, setFichaTabela] = useState<FichaTabela | null>(null);
  const [filtro, setFiltro] = useState('');
  const [novaTabela, setNovaTabela] = useState('');
  const [aviso, setAviso] = useState('');
  const [erro, setErro] = useState('');
  const [exemplo, setExemplo] = useState(false);
  const [nomeModulo, setNomeModulo] = useState('PDV'); // nome do módulo no modulos.json do servidor
  const [semTela, setSemTela] = useState<ManualResumo[]>([]);

  const recarregarMenus = useCallback(() => api.menus(MODULO).then(setMenus).catch(e => setErro(e.message)), [MODULO]);
  useEffect(() => {
    recarregarMenus();
    api.catalogo(MODULO).then(c => setNomesTabelas(c.tabelas.map(t => t.nome))).catch(() => {});
    api.modulos().then(ms => {
      const m = ms.find(x => x.id === MODULO);
      setExemplo(!!m?.exemplo);
      if (m) setNomeModulo(m.nome);
    }).catch(() => {});
    // manuais cuja tela não existe mais no menu (ex.: depois de trocar o exemplo pelo sistema real)
    api.manuais(MODULO).then(ms => setSemTela(ms.filter(m => !m.menu))).catch(() => {});
  }, [recarregarMenus, MODULO]);

  const recarregarFicha = useCallback(() => {
    if (!selecionado) { setFicha(null); return; }
    api.menu(selecionado).then(setFicha).catch(e => setErro(e.message));
  }, [selecionado]);
  useEffect(recarregarFicha, [recarregarFicha]);

  useEffect(() => {
    if (!tabelaSel) { setFichaTabela(null); return; }
    fetch(`/api/modulos/${MODULO}/tabelas/${encodeURIComponent(tabelaSel)}`).then(r => r.json()).then(setFichaTabela).catch(() => setFichaTabela(null));
  }, [tabelaSel]);

  const aba = params.get('aba') === 'tabelas' ? 'tabelas' : 'geral';
  const comAba = (p: Record<string, string>) => (aba === 'tabelas' ? { ...p, aba: 'tabelas' } : p);
  const avisar = (m: string) => { setAviso(m); window.setTimeout(() => setAviso(''), 2600); };
  const escolher = (id: string) => setParams(comAba({ item: id }));
  const abrirTabela = (nome: string) => setParams(comAba(selecionado ? { item: selecionado, tabela: nome } : { tabela: nome }));
  const mudarAba = (a: 'geral' | 'tabelas') => {
    const p: Record<string, string> = {};
    if (selecionado) p.item = selecionado;
    if (tabelaSel) p.tabela = tabelaSel;
    if (a === 'tabelas') p.aba = 'tabelas';
    setParams(p);
  };

  async function salvarVinculos(tabelas: string[], msg: string) {
    if (!ficha) return;
    try { await api.salvarTabelas(ficha.id, tabelas); recarregarFicha(); recarregarMenus(); avisar(msg); }
    catch (e) { setErro((e as Error).message); }
  }
  async function mudarStatus(r: Relacao, s: 'documentada' | 'descartada' | 'sugerida') {
    try {
      await api.statusRelacao(MODULO, r.id, s);
      recarregarFicha();
      if (tabelaSel) fetch(`/api/modulos/${MODULO}/tabelas/${encodeURIComponent(tabelaSel)}`).then(x => x.json()).then(setFichaTabela);
      avisar(s === 'documentada' ? 'Relação validada pela equipe.' : s === 'descartada' ? 'Relação descartada.' : 'Validação desfeita.');
    } catch (e) { setErro((e as Error).message); }
  }

  const resumo = useMemo(() => contar(menus), [menus]);
  const inicio = useMemo(() => primeiraComTabelas(menus), [menus]);
  const nomesFicha = useMemo(() => new Set(ficha?.tabelas.map(t => t.tabela) ?? []), [ficha]);
  const internas = useMemo(() => ficha?.relacoes.filter(r => nomesFicha.has(r.origem) && nomesFicha.has(r.destino)) ?? [], [ficha, nomesFicha]);
  const externas = useMemo(() => {
    const m = new Map<string, number>();
    ficha?.relacoes.forEach(r => {
      if (nomesFicha.has(r.origem) && nomesFicha.has(r.destino)) return;
      const outra = nomesFicha.has(r.origem) ? r.destino : r.origem;
      m.set(outra, (m.get(outra) ?? 0) + 1);
    });
    return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [ficha, nomesFicha]);

  return (
    <div className="app">
      <Topo modulo={MODULO} />
      <main className={`mapa ${fichaTabela ? 'com-tabela' : ''}`}>
        <section className="painel arvore" aria-label={`Menus do ${nomeModulo}`}>
          <div className="painel-cab">
            <h2>Mapa do sistema</h2>
            {exemplo && <span className="rotulo">Sistema de exemplo</span>}
          </div>
          <div className="busca">
            <input id="filtro-menu" type="search" placeholder="Filtrar menus e telas…" value={filtro} onChange={e => setFiltro(e.target.value)} aria-label="Filtrar menus" />
          </div>
          <div className="painel-corpo">
            <MenuArvore itens={menus} selecionado={selecionado} filtro={filtro} onEscolher={escolher} />
          </div>
        </section>

        <section className="painel ficha" aria-label="Ficha da tela">
          {!ficha ? (
            <div className="painel-corpo boas-vindas">
              <h1>Escolha uma tela do {nomeModulo}</h1>
              <p>Os menus à esquerda seguem a barra do sistema. Ao escolher um item, aparecem o caminho, os manuais, as tabelas do banco que a tela usa e como essas tabelas se ligam.</p>
              <ul className="numeros">
                <li><b>{resumo.total}</b><span>itens de menu mapeados</span></li>
                <li><b>{resumo.comTabela}</b><span>com tabelas vinculadas</span></li>
                <li><b>{resumo.aDetalhar}</b><span>submenus a detalhar</span></li>
              </ul>
              {inicio && (
                <button type="button" className="btn btn-primario" onClick={() => escolher(inicio.id)}>
                  Começar por: {inicio.titulo}
                </button>
              )}
              {semTela.length > 0 && (
                <div className="sem-tela">
                  <h2>Manuais sem tela ({semTela.length})</h2>
                  <p>A tela destes manuais não existe mais no menu do sistema. O conteúdo está guardado; falta escolher a tela.</p>
                  <ul>{semTela.map(m => <li key={m.codigo}><Link to={`/manuais/${encodeURIComponent(m.codigo)}`}>{m.codigo} · {m.titulo}</Link></li>)}</ul>
                </div>
              )}
            </div>
          ) : (<>
            <div className="ficha-topo">
              <nav className="trilha" aria-label="Caminho no sistema">
                {[nomeModulo, ...ficha.caminho.slice(0, -1).map(p => p.titulo)].map((t, i) => <span key={i}>{t}</span>)}
              </nav>
              <h1 className="ficha-titulo">
                {ficha.titulo}
                {ficha.atalho && <kbd>{ficha.atalho}</kbd>}
                {ficha.tela_codigo && <span className="tela-cod" title="Código da janela no sistema">{ficha.tela_codigo}</span>}
              </h1>
              <p className="caminho-completo"><span>Caminho</span>{caminhoTexto(nomeModulo, ficha.caminho)}</p>
              {ficha.desabilitado && <p className="alerta">Este item aparece desabilitado no menu do {nomeModulo}.</p>}
              <div className="abas" role="tablist" aria-label="Seções da ficha">
                <button type="button" role="tab" aria-selected={aba !== 'tabelas'} onClick={() => mudarAba('geral')}>Visão geral</button>
                <button type="button" role="tab" aria-selected={aba === 'tabelas'} onClick={() => mudarAba('tabelas')}>Tabelas <span className="qtd">{ficha.tabelas.length}</span></button>
              </div>
            </div>
            {aba === 'tabelas' ? (
              <div className="ficha-diagrama">
                <Diagrama modulo={MODULO} tabelas={ficha.tabelas.map(t => t.tabela)} onAbrirTabela={abrirTabela} />
              </div>
            ) : (
            <div className="painel-corpo">

              <div className="secao">
                <div className="secao-cab">
                  <h3>Manuais</h3>
                  {ficha.manuais.length > 0 && (
                    <div className="secao-acoes">
                      <Link className="btn btn-p" to={`/manuais/novo?menu=${encodeURIComponent(ficha.id)}&importar=1`}>Importar documento</Link>
                      <Link className="btn btn-p" to={`/manuais/novo?menu=${encodeURIComponent(ficha.id)}`}>+ Novo manual</Link>
                    </div>
                  )}
                </div>
                {ficha.manuais.length ? ficha.manuais.map(m => (
                  <Link key={m.codigo} to={`/manuais/${encodeURIComponent(m.codigo)}`} className="manual-card">
                    <span className="manual-cod">{m.codigo} · v{m.versao}</span>
                    <b>{m.titulo}</b>
                    <small>{m.subtitulo}</small>
                  </Link>
                )) : (
                  <div className="sem-manual">
                    <p className="vazio">Nenhum manual para esta tela ainda.</p>
                    <Link className="btn btn-primario" to={`/manuais/novo?menu=${encodeURIComponent(ficha.id)}`}>Criar manual para esta tela</Link>
                    <Link className="btn" to={`/manuais/novo?menu=${encodeURIComponent(ficha.id)}&importar=1`}>Importar documento</Link>
                  </div>
                )}
              </div>

              {ficha.filhos.length > 0 && (
                <div className="secao">
                  <h3>Opções dentro desta tela ({ficha.filhos.length})</h3>
                  <div className="chips">{ficha.filhos.map(f => <button key={f.id} type="button" className="chip" onClick={() => escolher(f.id)}>{f.titulo}{f.atalho && <kbd>{f.atalho}</kbd>}</button>)}</div>
                </div>
              )}

              <div className="secao">
                <h3>Tabelas que esta tela usa ({ficha.tabelas.length})</h3>
                <div className="chips">
                  {ficha.tabelas.map(t => (
                    <span key={t.tabela} className={`chip-tabela ${t.origem}`} title={t.origem === 'sugerido' ? 'Vínculo sugerido, ainda não confirmado pela equipe' : `Vínculo confirmado pela equipe ${autoria(t.por, t.em)}`.trim()}>
                      <button type="button" onClick={() => abrirTabela(t.tabela)}><code>{t.tabela}</code></button>
                      <button type="button" className="rm" aria-label={`Remover ${t.tabela}`} onClick={() => salvarVinculos(ficha.tabelas.filter(x => x.tabela !== t.tabela).map(x => x.tabela), `${t.tabela} removida desta tela.`)}>×</button>
                    </span>
                  ))}
                  {!ficha.tabelas.length && <p className="vazio">Nenhuma tabela vinculada.</p>}
                </div>
                <form className="vincular" onSubmit={e => {
                  e.preventDefault();
                  const v = novaTabela.trim();
                  if (!nomesTabelas.includes(v)) { avisar(`Essa tabela não existe no banco do ${nomeModulo}.`); return; }
                  salvarVinculos([...ficha.tabelas.map(x => x.tabela), v], `${v} vinculada a esta tela.`); setNovaTabela('');
                }}>
                  <input id="nova-tabela" list="lista-tabelas" placeholder="Vincular tabela…" value={novaTabela} onChange={e => setNovaTabela(e.target.value)} aria-label="Tabela para vincular" />
                  <datalist id="lista-tabelas">{nomesTabelas.filter(n => !nomesFicha.has(n)).map(n => <option key={n} value={n} />)}</datalist>
                  <button type="submit" className="btn">Vincular</button>
                  {ficha.tabelas.some(t => t.origem === 'sugerido') && (
                    <button type="button" className="btn" onClick={() => salvarVinculos(ficha.tabelas.map(x => x.tabela), 'Vínculos confirmados pela equipe.')}>Confirmar vínculos</button>
                  )}
                </form>
                <p className="dica">Tracejado = vínculo sugerido. O banco não sabe quais telas usam cada tabela; quem confirma é a equipe.</p>
              </div>

              <div className="secao">
                <h3>Ligações entre as tabelas da tela ({internas.length})</h3>
                {internas.length ? <ul className="rel-lista">{internas.map(r => <RelacaoLinha key={r.id} r={r} onStatus={mudarStatus} />)}</ul>
                  : <p className="vazio">Nenhuma ligação conhecida entre estas tabelas.</p>}
              </div>

              {externas.length > 0 && (
                <div className="secao">
                  <h3>Também se ligam a ({externas.length} tabelas)</h3>
                  <div className="chips">{externas.slice(0, 30).map(([n, q]) => (
                    <button key={n} type="button" className="chip" onClick={() => abrirTabela(n)}><code>{n}</code>{q > 1 && <span className="qtd">{q}</span>}</button>
                  ))}</div>
                  {externas.length > 30 && <p className="dica">E mais {externas.length - 30}. Abra uma tabela para ver todas as ligações dela.</p>}
                </div>
              )}
            </div>
            )}
          </>)}
        </section>

        {fichaTabela && (
          <section className="painel tabela" aria-label={`Tabela ${fichaTabela.nome}`}>
            <div className="painel-cab">
              <h2><code>{fichaTabela.nome}</code></h2>
              <button type="button" className="fechar" aria-label="Fechar ficha da tabela" onClick={() => setParams(comAba(selecionado ? { item: selecionado } : {}))}>×</button>
            </div>
            <div className="painel-corpo">
              <p className="meta">{fichaTabela.engine}{fichaTabela.linhas != null && ` · ~${fichaTabela.linhas.toLocaleString('pt-BR')} linhas`} · {fichaTabela.colunas.length} colunas</p>
              <div className="secao">
                <h3>Telas que usam</h3>
                {fichaTabela.menus.length ? <ul className="lista-simples">{fichaTabela.menus.map(m => (
                  <li key={m.id}><button type="button" className="link" onClick={() => escolher(m.id)}>{caminhoTexto(nomeModulo, m.caminho)}</button></li>
                ))}</ul> : <p className="vazio">Nenhuma tela vinculada.</p>}
              </div>
              {fichaTabela.manuais.length > 0 && (
                <div className="secao"><h3>Manuais que citam</h3>
                  <ul className="lista-simples">{fichaTabela.manuais.map(m => <li key={m.codigo}><Link to={`/manuais/${encodeURIComponent(m.codigo)}`}>{m.codigo} · {m.titulo}</Link></li>)}</ul>
                </div>
              )}
              <div className="secao">
                <h3>Relações ({fichaTabela.relacoes.filter(r => r.estado !== 'descartada').length})</h3>
                <ul className="rel-lista">{fichaTabela.relacoes.filter(r => r.estado !== 'descartada').slice(0, 40).map(r => <RelacaoLinha key={r.id} r={r} onStatus={mudarStatus} />)}</ul>
              </div>
              <div className="secao">
                <h3>Colunas</h3>
                <table className="colunas"><tbody>{fichaTabela.colunas.map(c => (
                  <tr key={c.nome}><td><code>{c.nome}</code></td><td>{c.tipo}</td><td>{c.pk && <span className="pk">PK</span>}</td></tr>
                ))}</tbody></table>
              </div>
            </div>
          </section>
        )}
      </main>
      {aviso && <div className="toast" role="status">{aviso}</div>}
      {erro && <div className="toast erro" role="alert" onClick={() => setErro('')}>{erro} · A API está rodando na porta 8010?</div>}
    </div>
  );
}
