import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { api, caminhoTexto } from '../api';
import Documento from '../componentes/Documento';
import Topo from '../componentes/Topo';
import type { Manual } from '../tipos';

export default function ManualPagina() {
  const { codigo = '' } = useParams();
  const [manual, setManual] = useState<Manual | null>(null);
  const [erro, setErro] = useState('');
  const [gerando, setGerando] = useState(false);
  const [aviso, setAviso] = useState('');
  const local = useLocation();

  // vindo do editor: "Manual salvo"
  useEffect(() => {
    const msg = (local.state as { aviso?: string } | null)?.aviso;
    if (!msg) return;
    setAviso(msg);
    const t = window.setTimeout(() => setAviso(''), 3500);
    return () => window.clearTimeout(t);
  }, [local.state]);

  useEffect(() => { api.manual(codigo).then(setManual).catch(e => setErro(e.message)); }, [codigo]);
  useEffect(() => { if (manual) document.title = `${manual.codigo} · ${manual.titulo}`; }, [manual]);

  async function exportarPdf() {
    if (!manual) return;
    setGerando(true);
    try {
      const blob = await api.pdf(manual.codigo);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${manual.codigo} - ${manual.modulo_nome} - ${manual.titulo}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      setAviso('PDF gerado.');
    } catch (e) {
      // sem o gerador no servidor, usa a impressão do navegador ("Salvar como PDF")
      setAviso(`${(e as Error).message}. Abrindo a impressão do navegador: escolha "Salvar como PDF".`);
      setTimeout(() => window.print(), 600);
    } finally {
      setGerando(false);
      setTimeout(() => setAviso(''), 5000);
    }
  }

  return (
    <div className="app pagina-manual">
      <Topo />
      <div className="manual-barra">
        <div className="manual-barra-esq">
          <Link to={manual?.menu ? `/?item=${encodeURIComponent(manual.menu)}` : '/'} className="link">← Voltar ao mapa</Link>
          {manual && manual.caminho.length > 0 && <span className="manual-caminho">{caminhoTexto(manual.modulo_nome, manual.caminho)}</span>}
          {manual && manual.fontes?.length > 0 && <span className="manual-fonte" title={manual.fontes.join('\n')}>Fonte: {manual.fontes.length === 1 ? manual.fontes[0] : `${manual.fontes.length} documentos de origem`}</span>}
        </div>
        <div className="editor-acoes">
        {manual && <Link className="btn" to={`/manuais/${encodeURIComponent(manual.codigo)}/editar`}>Editar</Link>}
        <button type="button" className="btn btn-primario" onClick={exportarPdf} disabled={!manual || gerando}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M4 19h16" /></svg>
          {gerando ? 'Gerando PDF…' : 'Exportar PDF'}
        </button>
        </div>
      </div>
      <main className="manual-palco">
        {erro && <p className="alerta">{erro}</p>}
        {manual && <Documento manual={manual} />}
      </main>
      {aviso && <div className="toast" role="status">{aviso}</div>}
    </div>
  );
}
