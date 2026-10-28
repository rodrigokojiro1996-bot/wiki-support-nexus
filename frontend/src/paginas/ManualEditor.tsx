import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, caminhoTexto, IMPORTACAO_ACEITA, IMPORTACAO_MAXIMO_MB } from '../api';
import Documento from '../componentes/Documento';
import Topo from '../componentes/Topo';
import type { Bloco, Manual, Passo } from '../tipos';

type TipoBloco = Bloco['tipo'];
type BlocoEd = Bloco & { id: number };
type SecaoEd = { id: number; titulo: string; blocos: BlocoEd[] };

const TIPOS_TEXTO: { tipo: Exclude<TipoBloco, 'imagem'>; rotulo: string; dica: string }[] = [
  { tipo: 'passo', rotulo: 'Passo', dica: 'Um passo do procedimento. Ex.: Acesse **Caixa > Fechamento** (F10).' },
  { tipo: 'texto', rotulo: 'Texto', dica: 'Parágrafo explicativo.' },
  { tipo: 'subtitulo', rotulo: 'Subtítulo', dica: 'Título de um trecho dentro da seção.' },
  { tipo: 'obs', rotulo: 'OBS', dica: 'Observação numerada (OBS¹, OBS²…).' },
  { tipo: 'nota', rotulo: 'Nota', dica: 'Destaque em caixa: um alerta ou dica importante.' },
  { tipo: 'sql', rotulo: 'SQL', dica: 'Comando para o analista copiar. Senhas são mascaradas ao salvar.' }
];
const ROTULO: Record<TipoBloco, string> = { ...Object.fromEntries(TIPOS_TEXTO.map(t => [t.tipo, t.rotulo])), imagem: 'Imagem' } as Record<TipoBloco, string>;

let seq = 0;
const novoId = () => ++seq;
const blocoVazio = (tipo: TipoBloco): BlocoEd =>
  tipo === 'imagem' ? { id: novoId(), tipo, arquivo: '', legenda: '' } : { id: novoId(), tipo, texto: '' };
const comIds = (secoes: Manual['secoes']): SecaoEd[] =>
  secoes.map(s => ({ id: novoId(), titulo: s.titulo, blocos: s.blocos.map(b => ({ ...b, id: novoId() })) }));
const semId = ({ id: _id, ...b }: BlocoEd): Bloco => b as Bloco;
const mover = <T,>(lista: T[], i: number, d: number) => {
  const j = i + d;
  if (j < 0 || j >= lista.length) return lista;
  const c = [...lista];
  [c[i], c[j]] = [c[j], c[i]];
  return c;
};
/** mesma regra da API: 1.0 → 1.1 */
const proximaVersao = (v: string) => { const m = /^(\d+)\.(\d+)$/.exec(v); return m ? `${m[1]}.${Number(m[2]) + 1}` : '1.1'; };
const urlImagem = (arquivo: string) => `/api/imagens/${arquivo.split('/').map(encodeURIComponent).join('/')}`;

export default function ManualEditor() {
  const { codigo } = useParams();             // editar: /manuais/:codigo/editar · novo: /manuais/novo?menu=…
  const [params] = useSearchParams();
  const navegar = useNavigate();

  const [titulo, setTitulo] = useState('');
  const [subtitulo, setSubtitulo] = useState('');
  const [secoes, setSecoes] = useState<SecaoEd[]>([]);
  const [contexto, setContexto] = useState<{ modulo: string; moduloNome: string; menu: string | null; caminho: Passo[]; versao: string } | null>(null);
  const [sujo, setSujo] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [mostrarErros, setMostrarErros] = useState(false);
  const [vista, setVista] = useState<'editar' | 'previa'>('editar');
  const [erro, setErro] = useState('');
  const [aviso, setAviso] = useState('');
  // importação: painel aberto pelo "Importar documento" do mapa; avisos e fontes vêm do documento convertido
  const [importando, setImportando] = useState<'fechado' | 'aberto' | 'enviando'>(params.get('importar') ? 'aberto' : 'fechado');
  const [avisosImportacao, setAvisosImportacao] = useState<{ arquivo: string; avisos: string[] } | null>(null);
  const [fontes, setFontes] = useState<string[]>([]);
  const seletorDocumento = useRef<HTMLInputElement>(null);
  const alvo = useRef<{ secao: number; bloco: number | null }>({ secao: -1, bloco: null }); // onde o print colado entra
  const seletor = useRef<HTMLInputElement>(null);
  const trocando = useRef<{ secao: number; bloco: number } | null>(null);

  const avisar = (m: string) => { setAviso(m); window.setTimeout(() => setAviso(''), 3200); };

  // ---------- carregar ----------
  useEffect(() => {
    if (codigo) {
      api.manual(codigo).then(m => {
        setTitulo(m.titulo); setSubtitulo(m.subtitulo); setSecoes(comIds(m.secoes));
        setContexto({ modulo: m.modulo, moduloNome: m.modulo_nome, menu: m.menu, caminho: m.caminho, versao: m.versao });
      }).catch(e => setErro(e.message));
      return;
    }
    const menu = params.get('menu');
    if (!menu) { setErro('Abra o editor a partir de uma tela do mapa do sistema.'); return; }
    Promise.all([api.menu(menu), api.modulos()]).then(([ficha, mods]) => {
      setContexto({ modulo: ficha.modulo, moduloNome: mods.find(x => x.id === ficha.modulo)?.nome ?? ficha.modulo, menu, caminho: ficha.caminho, versao: '' });
      setTitulo(ficha.titulo);
      setSecoes([{ id: novoId(), titulo: 'Procedimento', blocos: [blocoVazio('passo')] }]);
    }).catch(e => setErro(e.message));
  }, [codigo, params]);

  useEffect(() => { document.title = codigo ? `Editar ${codigo}` : 'Novo manual'; }, [codigo]);

  // alterações não salvas: o navegador pergunta antes de sair
  useEffect(() => {
    if (!sujo) return;
    const f = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', f);
    return () => window.removeEventListener('beforeunload', f);
  }, [sujo]);

  // ---------- edição ----------
  const alterar = useCallback((f: (s: SecaoEd[]) => SecaoEd[]) => { setSecoes(f); setSujo(true); }, []);
  const alterarBloco = (si: number, bi: number, mud: Partial<Bloco>) =>
    alterar(ss => ss.map((s, i) => (i !== si ? s : { ...s, blocos: s.blocos.map((b, j) => (j === bi ? ({ ...b, ...mud } as BlocoEd) : b)) })));
  const inserirBloco = (si: number, bloco: BlocoEd, depoisDe: number | null = null) =>
    alterar(ss => ss.map((s, i) => {
      if (i !== si) return s;
      const pos = depoisDe == null ? s.blocos.length : depoisDe + 1;
      return { ...s, blocos: [...s.blocos.slice(0, pos), bloco, ...s.blocos.slice(pos)] };
    }));

  async function subirImagem(arquivo: File | Blob, destino?: { secao: number; bloco: number }) {
    if (!arquivo.type.startsWith('image/')) { avisar('Esse arquivo não é uma imagem.'); return; }
    avisar('Enviando o print…');
    try {
      const nome = await api.enviarImagem(arquivo);
      if (destino) {
        alterarBloco(destino.secao, destino.bloco, { arquivo: nome });
      } else {
        // entra logo depois do bloco em que a pessoa estava; sem foco, no fim da última seção
        const si = alvo.current.secao >= 0 ? alvo.current.secao : secoes.length - 1;
        if (si < 0) return;
        inserirBloco(si, { id: novoId(), tipo: 'imagem', arquivo: nome, legenda: '' }, alvo.current.secao >= 0 ? alvo.current.bloco : null);
      }
      avisar('Print adicionado. Escreva uma legenda, se quiser.');
    } catch (e) { setErro((e as Error).message); }
  }
  async function importarDocumento(arquivo: File) {
    if (!contexto) return;
    if (sujo && !window.confirm('O conteúdo importado substitui o que já está no editor. Continuar?')) return;
    setImportando('enviando');
    try {
      const r = await api.importarManual(contexto.modulo, arquivo);
      setTitulo(r.titulo || titulo);
      setSubtitulo(r.subtitulo);
      // PDF escaneado não traz texto: fica uma seção vazia para começar
      setSecoes(r.secoes.length ? comIds(r.secoes) : [{ id: novoId(), titulo: 'Procedimento', blocos: [blocoVazio('passo')] }]);
      setFontes(r.fontes);
      setAvisosImportacao({ arquivo: arquivo.name, avisos: r.avisos });
      setSujo(true);
      setImportando('fechado');
      setMostrarErros(false);
      avisar('Documento importado. Revise e clique em Salvar manual.');
    } catch (e) {
      setImportando('aberto');
      setErro(`Não foi possível importar ${arquivo.name}: ${(e as Error).message}`);
    }
  }

  const subir = useRef(subirImagem);
  subir.current = subirImagem;

  // Ctrl+V de um print em qualquer lugar da página
  useEffect(() => {
    const colar = (e: ClipboardEvent) => {
      const img = [...(e.clipboardData?.files ?? [])].find(f => f.type.startsWith('image/'));
      if (!img) return;
      e.preventDefault();
      subir.current(img);
    };
    window.addEventListener('paste', colar);
    return () => window.removeEventListener('paste', colar);
  }, []);

  // ---------- validação (a mesma regra da API, para avisar antes de enviar) ----------
  const problemas = useMemo(() => {
    const p: string[] = [];
    if (!titulo.trim()) p.push('O manual precisa de título.');
    if (!secoes.length) p.push('Inclua pelo menos uma seção.');
    secoes.forEach((s, i) => {
      if (!s.titulo.trim()) p.push(`Seção ${i + 1} sem título.`);
      s.blocos.forEach((b, j) => { if (b.tipo !== 'imagem' && !b.texto.trim()) p.push(`Seção ${i + 1}, bloco ${j + 1} (${ROTULO[b.tipo]}) sem texto.`); });
    });
    return p;
  }, [titulo, secoes]);

  async function salvar() {
    if (!contexto) return;
    if (problemas.length) { setMostrarErros(true); return; }
    setSalvando(true);
    try {
      const r = await api.salvarManual({
        titulo, subtitulo, modulo: contexto.modulo, menu: contexto.menu, fontes,
        secoes: secoes.map(s => ({ titulo: s.titulo, blocos: s.blocos.map(semId) }))
      }, codigo);
      setSujo(false);
      navegar(`/manuais/${encodeURIComponent(r.codigo)}`, { state: { aviso: codigo ? `Manual salvo (versão ${r.versao}).` : `Manual ${r.codigo} criado.` } });
    } catch (e) { setErro((e as Error).message); }
    finally { setSalvando(false); }
  }

  function cancelar() {
    if (sujo && !window.confirm('Descartar as alterações que ainda não foram salvas?')) return;
    setSujo(false);
    navegar(codigo ? `/manuais/${encodeURIComponent(codigo)}` : contexto?.menu ? `/?item=${encodeURIComponent(contexto.menu)}` : '/');
  }

  // ---------- prévia: o mesmo componente dos manuais publicados ----------
  const previa: Manual | null = contexto && {
    codigo: codigo ?? `${contexto.modulo.toUpperCase()}.???`, titulo: titulo || 'Título do manual', subtitulo,
    versao: contexto.versao ? proximaVersao(contexto.versao) : '1.0', modulo: contexto.modulo, modulo_nome: contexto.moduloNome, menu: contexto.menu,
    caminho: contexto.caminho, tabelas: [], fontes, atualizado_em: '',
    secoes: secoes.map(s => ({ titulo: s.titulo || 'Seção sem título', blocos: s.blocos.map(semId) }))
  };

  const vazio = (b: BlocoEd) => b.tipo !== 'imagem' && !b.texto.trim();

  return (
    <div className="app pagina-manual">
      <Topo modulo={contexto?.modulo} />
      <div className="manual-barra">
        <div className="manual-barra-esq">
          <button type="button" className="link" onClick={cancelar}>← {codigo ? 'Voltar ao manual' : 'Voltar ao mapa'}</button>
          <b>{codigo ? `Editando ${codigo}` : 'Novo manual'}</b>
          {contexto && contexto.caminho.length > 0 && <span className="manual-caminho">{caminhoTexto(contexto.moduloNome, contexto.caminho)}</span>}
        </div>
        <div className="editor-acoes">
          <div className="editor-vistas" role="tablist" aria-label="Editar ou ver a prévia">
            <button type="button" role="tab" aria-selected={vista === 'editar'} onClick={() => setVista('editar')}>Editar</button>
            <button type="button" role="tab" aria-selected={vista === 'previa'} onClick={() => setVista('previa')}>Prévia</button>
          </div>
          {!codigo && <button type="button" className="btn" onClick={() => setImportando(i => (i === 'fechado' ? 'aberto' : 'fechado'))}
            aria-expanded={importando !== 'fechado'} disabled={!contexto || importando === 'enviando'}>Importar documento</button>}
          <button type="button" className="btn" onClick={cancelar}>Cancelar</button>
          <button type="button" className="btn btn-primario" onClick={salvar} disabled={!contexto || salvando}>{salvando ? 'Salvando…' : 'Salvar manual'}</button>
        </div>
      </div>

      {mostrarErros && problemas.length > 0 && (
        <div className="editor-problemas" role="alert">
          <b>Antes de salvar:</b>
          <ul>{problemas.map(p => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      {!codigo && contexto && importando !== 'fechado' && (
        <div className={`editor-importar${importando === 'enviando' ? ' enviando' : ''}`}
          onDragOver={e => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); e.stopPropagation(); } }}
          onDrop={e => { const f = e.dataTransfer.files[0]; if (f) { e.preventDefault(); e.stopPropagation(); importarDocumento(f); } }}>
          {importando === 'enviando' ? <b>Convertendo o documento…</b> : (
            <>
              <b>Arraste o documento para cá</b>
              <span>PDF, Word (.docx), .txt ou .md, até {IMPORTACAO_MAXIMO_MB} MB. O conteúdo abre aqui no editor para revisar; nada é salvo até você clicar em Salvar manual.</span>
              <button type="button" className="btn btn-primario" onClick={() => seletorDocumento.current?.click()}>Escolher arquivo</button>
            </>
          )}
          <input ref={seletorDocumento} type="file" accept={IMPORTACAO_ACEITA} hidden
            onChange={e => { const f = e.target.files?.[0]; if (f) importarDocumento(f); e.target.value = ''; }} />
        </div>
      )}

      {avisosImportacao && (
        <div className="editor-avisos" role="status">
          <b>Importado de {avisosImportacao.arquivo}.</b> A conversão é automática: confira o texto, as seções e os prints antes de salvar.
          {avisosImportacao.avisos.length > 0 && <ul>{avisosImportacao.avisos.map(a => <li key={a}>{a}</li>)}</ul>}
          <button type="button" className="link" onClick={() => setAvisosImportacao(null)}>Fechar</button>
        </div>
      )}

      {contexto && (
        <main className={`editor vista-${vista}`}
          onDragOver={e => { if (e.dataTransfer.types.includes('Files')) e.preventDefault(); }}
          onDrop={e => {
            const f = e.dataTransfer.files[0];
            if (!f) return;
            e.preventDefault();
            // documento solto no editor de um manual novo: importa; imagem: vira print
            if (!codigo && !f.type.startsWith('image/')) importarDocumento(f); else subirImagem(f);
          }}>
          <section className="editor-form" aria-label="Conteúdo do manual">
            <p className="dica">Cole um print com <kbd>Ctrl</kbd>+<kbd>V</kbd> (ou arraste a imagem) e ele entra logo depois do bloco em que você está. Formatação ao colar ou digitar: linha em branco separa parágrafos; <code>•</code> ou <code>-</code> no começo da linha vira lista (Tab antes = subitem); linha sozinha que começa com emoji, com <code>1.</code> ou termina em <code>:</code> vira título; <code>[ Botão ]</code> aparece como botão; <code>**texto**</code> é negrito.</p>

            <label className="campo">
              <span>Título do manual</span>
              <input value={titulo} maxLength={200} aria-invalid={mostrarErros && !titulo.trim()} onChange={e => { setTitulo(e.target.value); setSujo(true); }} />
            </label>
            <label className="campo">
              <span>Subtítulo <small>(opcional) · quando usar este manual</small></span>
              <textarea rows={2} value={subtitulo} maxLength={500} onChange={e => { setSubtitulo(e.target.value); setSujo(true); }} />
            </label>

            {secoes.map((s, si) => (
              <fieldset key={s.id} className="editor-secao">
                <legend className="sr">Seção {si + 1}</legend>
                <div className="editor-secao-cab">
                  <span className="editor-n">{si + 1}.</span>
                  <input className="editor-secao-tit" value={s.titulo} placeholder="Título da seção" maxLength={200} aria-label={`Título da seção ${si + 1}`}
                    aria-invalid={mostrarErros && !s.titulo.trim()}
                    onFocus={() => { alvo.current = { secao: si, bloco: null }; }}
                    onChange={e => alterar(ss => ss.map((x, i) => (i === si ? { ...x, titulo: e.target.value } : x)))} />
                  <div className="editor-mini">
                    <button type="button" aria-label={`Subir seção ${si + 1}`} disabled={si === 0} onClick={() => alterar(ss => mover(ss, si, -1))}>↑</button>
                    <button type="button" aria-label={`Descer seção ${si + 1}`} disabled={si === secoes.length - 1} onClick={() => alterar(ss => mover(ss, si, 1))}>↓</button>
                    <button type="button" aria-label={`Remover seção ${si + 1}`} onClick={() => {
                      if (s.blocos.some(b => !vazio(b)) && !window.confirm(`Remover a seção "${s.titulo || si + 1}" e o que tem nela?`)) return;
                      alterar(ss => ss.filter((_, i) => i !== si));
                    }}>×</button>
                  </div>
                </div>

                {s.blocos.map((b, bi) => (
                  <div key={b.id} className={`editor-bloco tipo-${b.tipo}`} onFocus={() => { alvo.current = { secao: si, bloco: bi }; }}>
                    <div className="editor-bloco-cab">
                      {b.tipo === 'imagem' ? <span className="editor-tipo">Imagem</span> : (
                        <select className="editor-tipo" value={b.tipo} aria-label="Tipo do bloco"
                          onChange={e => alterarBloco(si, bi, { tipo: e.target.value as Exclude<TipoBloco, 'imagem'> })}>
                          {TIPOS_TEXTO.map(t => <option key={t.tipo} value={t.tipo}>{t.rotulo}</option>)}
                        </select>
                      )}
                      <div className="editor-mini">
                        <button type="button" aria-label="Subir bloco" disabled={bi === 0} onClick={() => alterar(ss => ss.map((x, i) => (i === si ? { ...x, blocos: mover(x.blocos, bi, -1) } : x)))}>↑</button>
                        <button type="button" aria-label="Descer bloco" disabled={bi === s.blocos.length - 1} onClick={() => alterar(ss => ss.map((x, i) => (i === si ? { ...x, blocos: mover(x.blocos, bi, 1) } : x)))}>↓</button>
                        <button type="button" aria-label="Remover bloco" onClick={() => alterar(ss => ss.map((x, i) => (i === si ? { ...x, blocos: x.blocos.filter((_, j) => j !== bi) } : x)))}>×</button>
                      </div>
                    </div>
                    {b.tipo === 'imagem' ? (
                      <div className="editor-imagem">
                        {b.arquivo
                          ? <img src={urlImagem(b.arquivo)} alt={b.legenda || 'Print'} />
                          : <div className="editor-imagem-vazia">Cole um print (<kbd>Ctrl</kbd>+<kbd>V</kbd>) ou escolha um arquivo</div>}
                        <div className="editor-imagem-lado">
                          <button type="button" className="btn btn-p" onClick={() => { trocando.current = { secao: si, bloco: bi }; seletor.current?.click(); }}>
                            {b.arquivo ? 'Trocar imagem' : 'Escolher arquivo'}
                          </button>
                          <input value={b.legenda} placeholder="Legenda (opcional)" maxLength={500} aria-label="Legenda da imagem"
                            onChange={e => alterarBloco(si, bi, { legenda: e.target.value })} />
                        </div>
                      </div>
                    ) : (
                      <textarea value={b.texto} rows={Math.min(24, Math.max(b.tipo === 'sql' ? 4 : 2, b.texto.split('\n').length + 1))} spellCheck={b.tipo !== 'sql'}
                        placeholder={TIPOS_TEXTO.find(t => t.tipo === b.tipo)?.dica} aria-label={`${ROTULO[b.tipo]} ${bi + 1} da seção ${si + 1}`}
                        aria-invalid={mostrarErros && vazio(b)}
                        onChange={e => alterarBloco(si, bi, { texto: e.target.value })} />
                    )}
                  </div>
                ))}

                <div className="editor-add" aria-label={`Adicionar à seção ${si + 1}`}>
                  <span>Adicionar:</span>
                  {TIPOS_TEXTO.map(t => <button key={t.tipo} type="button" className="chip" onClick={() => inserirBloco(si, blocoVazio(t.tipo))}>+ {t.rotulo}</button>)}
                  <button type="button" className="chip" onClick={() => inserirBloco(si, blocoVazio('imagem'))}>+ Imagem</button>
                </div>
              </fieldset>
            ))}

            <button type="button" className="btn" onClick={() => alterar(ss => [...ss, { id: novoId(), titulo: '', blocos: [blocoVazio('passo')] }])}>+ Nova seção</button>
            <input ref={seletor} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden
              onChange={e => { const f = e.target.files?.[0]; if (f) subirImagem(f, trocando.current ?? undefined); trocando.current = null; e.target.value = ''; }} />
          </section>

          <section className="editor-previa" aria-label="Prévia do manual">
            {previa && <Documento manual={previa} />}
          </section>
        </main>
      )}

      {erro && <div className="toast erro" role="alert" onClick={() => setErro('')}>{erro}</div>}
      {aviso && !erro && <div className="toast" role="status">{aviso}</div>}
    </div>
  );
}

