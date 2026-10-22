import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { blocoRico } from './textoRico';
// os mesmos exemplos do teste do importador (backend/tests/test_formatacao.py)
import formatacao from '../../../backend/tests/dados/importacao/formatacao.json';

type Caso = { nome: string; texto: string; blocos?: { tipo: string; texto: string }[]; mesma_aparencia?: boolean };

const html = (texto: string) => renderToStaticMarkup(<>{blocoRico(texto, 'doc-texto')}</>);
const casos = (formatacao.casos as Caso[]).filter(c => c.mesma_aparencia);

describe('texto colado x documento importado', () => {
  it('tem exemplos para comparar', () => expect(casos.length).toBeGreaterThan(0));

  it.each(casos.map(c => [c.nome, c] as const))('%s: aparece igual nos dois caminhos', (_, c) => {
    // colado no editor: o texto inteiro num bloco de texto; importado: o bloco que o conversor gerou
    expect(html(c.blocos![0].texto)).toBe(html(c.texto));
  });
});

describe('blocoRico', () => {
  it('lista com subitem vira lista aninhada', () => {
    expect(html('Antes:\n• Fila parada\n\t• há 30 minutos\n• Sem internet')).toBe(
      '<div class="doc-texto doc-rico"><p class="doc-rico-p">Antes:</p><ul class="doc-lista">'
      + '<li>Fila parada<ul class="doc-lista"><li>há 30 minutos</li></ul></li><li>Sem internet</li></ul></div>');
  });

  it('linha sozinha terminada em ":" vira título do trecho', () => {
    expect(html('Para liberar:\n\nUse a loja de origem.')).toContain('<p class="doc-rico-tit">Para liberar:</p>');
  });

  it('[ Botão ], seta e negrito', () => {
    expect(html('Clique em [ Salvar ] -> **Confirmar**.')).toBe(
      '<p class="doc-texto">Clique em <span class="doc-botao">Salvar</span> → <strong>Confirmar</strong>.</p>');
  });
});
