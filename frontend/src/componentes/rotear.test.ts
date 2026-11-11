import { describe, expect, it } from 'vitest';
import type { Caixa, Ponto } from './afastar';
import { atravessa, criarRoteador } from './rotear';

const cx = (id: string, x: number, y: number, w = 290, h = 120): Caixa => ({ id, x, y, w, h });
const ortogonal = (p: Ponto[]) => p.every((q, i) => i === 0 || q.x === p[i - 1].x || q.y === p[i - 1].y);
// a linha não pode atravessar nenhum cartão (encostar na borda de saída/chegada pode)
const livre = (p: Ponto[], caixas: Caixa[]) => !atravessa(p, caixas.map(c => ({ ...c, x: c.x + 1, y: c.y + 1, w: c.w - 2, h: c.h - 2 })));

describe('rotear', () => {
  it('liga duas tabelas lado a lado com uma linha reta ou poucas dobras, sem atravessar nada', () => {
    const caixas = [cx('a', 0, 0), cx('b', 500, 0)];
    const de = { x: 290, y: 50 }, para = { x: 500, y: 50 };
    const p = criarRoteador(caixas, [{ de, para }])({ de, para })!;
    expect(p[0]).toEqual(de);
    expect(p[p.length - 1]).toEqual(para);
    expect(ortogonal(p)).toBe(true);
    expect(p.length).toBe(2); // mesma altura: reta
  });

  it('contorna uma tabela que ficou no meio do caminho', () => {
    const caixas = [cx('a', 0, 0), cx('meio', 400, -100, 290, 400), cx('b', 900, 0)];
    const de = { x: 290, y: 50 }, para = { x: 900, y: 50 };
    const p = criarRoteador(caixas, [{ de, para }])({ de, para })!;
    expect(p).not.toBeNull();
    expect(ortogonal(p)).toBe(true);
    expect(livre(p, caixas)).toBe(true);
  });

  it('destino à esquerda da origem: sai pela direita, dá a volta e entra pela esquerda', () => {
    const caixas = [cx('b', 0, 0), cx('a', 500, 200)];
    const de = { x: 790, y: 260 }, para = { x: 0, y: 40 };
    const p = criarRoteador(caixas, [{ de, para }])({ de, para })!;
    expect(ortogonal(p)).toBe(true);
    expect(livre(p, caixas)).toBe(true);
    expect(p[1].x).toBeGreaterThan(de.x);     // primeira dobra à direita da origem
    expect(p[p.length - 2].x).toBeLessThan(para.x); // última dobra à esquerda do destino
  });

  it('atravessa: detecta o trajeto antigo que passa por cima de uma tabela movida', () => {
    expect(atravessa([{ x: 0, y: 50 }, { x: 600, y: 50 }], [cx('x', 200, 0)])).toBe(true);
    expect(atravessa([{ x: 0, y: 500 }, { x: 600, y: 500 }], [cx('x', 200, 0)])).toBe(false);
  });

  it('muitas tabelas: todas as ligações saem sem cruzar cartão', () => {
    const caixas = Array.from({ length: 16 }, (_, i) => cx(`t${i}`, (i % 4) * 420, Math.floor(i / 4) * 220, 290, 80 + (i % 3) * 40));
    const ligs = caixas.slice(1).map((c, i) => ({ de: { x: caixas[i].x + 290, y: caixas[i].y + 50 }, para: { x: c.x, y: c.y + 50 } }));
    const rotear = criarRoteador(caixas, ligs);
    const t0 = performance.now();
    const rotas = ligs.map(rotear);
    expect(performance.now() - t0).toBeLessThan(500);
    rotas.forEach(p => { expect(p).not.toBeNull(); expect(ortogonal(p!)).toBe(true); expect(livre(p!, caixas)).toBe(true); });
  });
});
