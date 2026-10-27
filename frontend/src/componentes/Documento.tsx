import { Fragment } from 'react';
import { caminhoTexto } from '../api';
import type { Bloco, Manual } from '../tipos';
import Marca from './Marca';
import { textoRodape } from '../dataHora';
import { blocoRico, inline, linhas } from './textoRico';

const SOBRESCRITO = ['¹', '²', '³', '⁴', '⁵', '⁶', '⁷', '⁸', '⁹'];

function Blocos({ secao, blocos }: { secao: number; blocos: Bloco[] }) {
  let passo = 0, obs = 0;
  return (
    <>
      {blocos.map((b, i) => {
        switch (b.tipo) {
          case 'passo':
            passo++;
            return <p key={i} className="doc-passo"><span className="doc-passo-n">{b.rotulo ?? `${secao}.${passo}`}.</span><span>{linhas(b.texto)}</span></p>;
          case 'subtitulo':
            return <h3 key={i} className="doc-subtitulo">{inline(b.texto)}</h3>;
          case 'sql':
            return <pre key={i} className="doc-sql">{b.texto}</pre>;
          case 'obs':
            return <p key={i} className="doc-obs">OBS{SOBRESCRITO[obs++] ?? ''}: {linhas(b.texto)}</p>;
          case 'nota':
            return <aside key={i} className="doc-nota">{blocoRico(b.texto, 'doc-nota-corpo')}</aside>;
          case 'texto':
            return <Fragment key={i}>{blocoRico(b.texto, 'doc-texto')}</Fragment>;
          case 'imagem':
            return (
              <figure key={i} className="doc-figura">
                {b.arquivo
                  ? <img src={`/api/imagens/${b.arquivo.split('/').map(encodeURIComponent).join('/')}`} alt={b.legenda || 'Print da tela'} loading="eager" />
                  : <div className="doc-figura-pendente"><b>Print pendente</b><span>{b.legenda}</span></div>}
                {b.arquivo && b.legenda && <figcaption>{b.legenda}</figcaption>}
              </figure>
            );
        }
      })}
    </>
  );
}

/**
 * Manual no modelo visual do Support Nexus (faixa lateral, cabeçalho com a marca, traço de destaque, sumário, seções numeradas).
 * Em PDF, cabeçalho e rodapé vêm do gerador (repetidos em todas as páginas, com número).
 */
export default function Documento({ manual }: { manual: Manual }) {
  const caminho = manual.caminho.length ? caminhoTexto(manual.modulo_nome, manual.caminho) : null;
  return (
    <article className="doc">
      <div className="doc-faixa" aria-hidden="true"><i /><i /><i /></div>

      <header className="doc-cab">
        <div>
          <b>Support Nexus – Base de conhecimento</b>
          <span>{manual.modulo_nome}</span>
        </div>
        <Marca />
      </header>

      <div className="doc-corpo">
        <div className="doc-traco" />
        <h1 className="doc-titulo">{manual.titulo}</h1>
        {manual.subtitulo && <p className="doc-sub">{manual.subtitulo}</p>}

        <p className="doc-versao">Versão do documento: {manual.versao} - {manual.codigo}</p>
        {caminho && (
          <p className="doc-caminho"><span className="doc-caminho-rot">Caminho:</span> {caminho}</p>
        )}

        <h2 className="doc-sumario-tit">Sumário</h2>
        <ol className="doc-sumario">
          {manual.secoes.map((s, i) => (
            <li key={i}><a href={`#secao-${i + 1}`}><span>{i + 1}. {s.titulo}</span><i /></a></li>
          ))}
        </ol>

        {manual.secoes.map((s, i) => (
          <section key={i} id={`secao-${i + 1}`} className="doc-secao">
            <h2 className="doc-secao-tit">{i + 1}. {s.titulo}.</h2>
            <Blocos secao={i + 1} blocos={s.blocos} />
          </section>
        ))}
      </div>

      <footer className="doc-rod">
        <span className="doc-rod-n">1</span>
        <span className="doc-rod-linha" />
        <span className="doc-rod-txt">{textoRodape(manual.alterado_em)}</span>
      </footer>
    </article>
  );
}
