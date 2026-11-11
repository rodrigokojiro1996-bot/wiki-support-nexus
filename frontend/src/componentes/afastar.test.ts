import { describe, expect, it } from 'vitest';
import { afastar, sobrepoe, type Caixa } from './afastar';

const cx = (id: string, x: number, y: number, w = 290, h = 150): Caixa => ({ id, x, y, w, h });
const aplicar = (caixas: Caixa[], m: Map<string, { x: number; y: number }>) =>
  caixas.map(c => ({ ...c, ...(m.get(c.id) ?? {}) }));
const semSobreposicao = (caixas: Caixa[]) =>
  caixas.every((a, i) => caixas.every((b, j) => j <= i || !sobrepoe(a, b, 1)));

describe('afastar', () => {
  it('não mexe em nada quando ninguém se sobrepõe', () => {
    expect(afastar([cx('a', 0, 0), cx('b', 400, 0)], () => 2).size).toBe(0);
  });

  it('a tabela arrastada fica onde a pessoa soltou e a outra sai da frente', () => {
    const caixas = [cx('arrastada', 100, 20), cx('outra', 0, 0)];
    const m = afastar(caixas, id => (id === 'arrastada' ? 0 : 2), { x: 245, y: 95 });
    expect(m.has('arrastada')).toBe(false);
    expect(m.has('outra')).toBe(true);
    expect(semSobreposicao(aplicar(caixas, m))).toBe(true);
  });

  it('o empurrão se propaga: a vizinha empurrada empurra a seguinte', () => {
    const caixas = [cx('arrastada', 0, 0), cx('b', 0, 100), cx('c', 0, 300), cx('d', 0, 500)];
    const m = afastar(caixas, id => (id === 'arrastada' ? 0 : 2), { x: 145, y: 75 });
    expect(m.has('arrastada')).toBe(false);
    expect(semSobreposicao(aplicar(caixas, m))).toBe(true);
  });

  it('a tabela posicionada pela equipe cede menos que a do layout automático', () => {
    const caixas = [cx('equipe', 0, 0), cx('auto', 50, 40)];
    const m = afastar(caixas, id => (id === 'equipe' ? 1 : 2));
    expect([...m.keys()]).toEqual(['auto']);
  });

  it('um monte de tabelas empilhadas no mesmo ponto termina sem nenhuma sobreposição', () => {
    const caixas = Array.from({ length: 12 }, (_, i) => cx(`t${i}`, i * 3, i * 2, 290, 80 + (i % 4) * 40));
    const m = afastar(caixas, id => (id === 't0' ? 0 : 2), { x: 145, y: 40 });
    expect(semSobreposicao(aplicar(caixas, m))).toBe(true);
  });
});
