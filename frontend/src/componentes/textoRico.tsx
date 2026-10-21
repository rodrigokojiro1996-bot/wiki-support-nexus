import { Fragment, type ReactNode } from 'react';

/**
 * Formatação dos blocos de texto dos manuais, a partir do texto como a pessoa colou ou digitou:
 *   linha em branco        → novo parágrafo
 *   • - * ▪ ◦ no começo    → lista; Tab (ou 2 espaços) antes do marcador → subitem
 *   linha sozinha que começa com emoji ou "1." / "2)", ou termina em ":" → título do trecho
 *   primeira linha de um parágrafo que começa com emoji (🎉, ❌…) → destaque
 *   **texto** → negrito · [ Botão ] → botão da tela · -> → seta
 */

const MARCADOR = /^([ \t]*)[•\-*▪◦●]\s+(.*)$/;
const EMOJI = /^\p{Extended_Pictographic}/u;
const NUMERADO = /^\d+[.)]\s/;

/** **negrito**, [ Botão ] e -> dentro de uma linha */
export function inline(texto: string): ReactNode {
  return texto.replace(/\s->\s/g, ' → ').split(/(\*\*[^*]+\*\*|\[ [^\]\n]+ \])/g).map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**') && p.length > 4) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (/^\[ .+ \]$/.test(p)) return <span key={i} className="doc-botao">{p.slice(2, -2)}</span>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

/** Linhas de um mesmo parágrafo, com quebra de linha preservada */
export function linhas(texto: string): ReactNode {
  const ls = texto.split('\n');
  return ls.map((l, i) => <Fragment key={i}>{inline(l.trim())}{i < ls.length - 1 && <br />}</Fragment>);
}

type Item = { nivel: number; texto: string; filhos: Item[] };

const nivelDe = (recuo: string) => [...recuo].reduce((n, c) => n + (c === '\t' ? 2 : 1), 0) >> 1;

function arvore(itens: { nivel: number; texto: string }[]): Item[] {
  const raiz: Item[] = [];
  const pilha: Item[] = [];
  const base = Math.min(...itens.map(i => i.nivel));
  for (const { nivel, texto } of itens) {
    const item: Item = { nivel: nivel - base, texto, filhos: [] };
    while (pilha.length && pilha[pilha.length - 1].nivel >= item.nivel) pilha.pop();
    (pilha.length ? pilha[pilha.length - 1].filhos : raiz).push(item);
    pilha.push(item);
  }
  return raiz;
}

const Lista = ({ itens }: { itens: Item[] }) => (
  <ul className="doc-lista">
    {itens.map((it, i) => <li key={i}>{inline(it.texto)}{it.filhos.length > 0 && <Lista itens={it.filhos} />}</li>)}
  </ul>
);

const ehTitulo = (l: string) => l.length <= 100 && (EMOJI.test(l) || NUMERADO.test(l) || /:$/.test(l));

/** Texto com mais de uma linha vira parágrafos, listas e títulos; texto de uma linha só continua um parágrafo simples. */
export function blocoRico(texto: string, classe: string): ReactNode {
  if (!texto.includes('\n') && !MARCADOR.test(texto)) return <p className={classe}>{inline(texto)}</p>;

  const partes: ReactNode[] = [];
  const grupos = texto.split(/\n[ \t]*\n/).map(g => g.split('\n').filter(l => l.trim())).filter(g => g.length);
  grupos.forEach((grupo, gi) => {
    if (grupo.length === 1 && !MARCADOR.test(grupo[0]) && ehTitulo(grupo[0].trim())) {
      partes.push(<p key={gi} className="doc-rico-tit">{inline(grupo[0].trim())}</p>);
      return;
    }
    // dentro do grupo, linhas de lista e de texto podem se alternar
    let lista: { nivel: number; texto: string }[] = [];
    let texto_: string[] = [];
    const fechar = (k: string) => {
      if (lista.length) { partes.push(<Lista key={`${k}l`} itens={arvore(lista)} />); lista = []; }
      if (texto_.length) {
        const [primeira, ...resto] = texto_;
        const destaque = EMOJI.test(primeira);
        partes.push(
          <p key={`${k}p`} className="doc-rico-p">
            {destaque ? <strong>{inline(primeira)}</strong> : inline(primeira)}
            {resto.map((l, i) => <Fragment key={i}><br />{inline(l)}</Fragment>)}
          </p>
        );
        texto_ = [];
      }
    };
    grupo.forEach((l, li) => {
      const m = MARCADOR.exec(l);
      if (m) {
        if (texto_.length) fechar(`${gi}-${li}`);
        lista.push({ nivel: nivelDe(m[1]), texto: m[2].trim() });
      } else {
        if (lista.length) fechar(`${gi}-${li}`);
        texto_.push(l.trim());
      }
    });
    fechar(`${gi}-fim`);
  });
  return <div className={`${classe} doc-rico`}>{partes}</div>;
}
