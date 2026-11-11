/**
 * Roteador das ligações do diagrama depois que a equipe move tabelas: caminho em ângulos retos que contorna todos os
 * cartões (o ELK só calcula os trajetos do layout automático).
 *
 * Grade de visibilidade ortogonal: as coordenadas candidatas são as bordas de cada cartão (com uma margem), o meio
 * dos corredores entre elas e as pontas das ligações. A* nessa grade, com custo = comprimento + penalidade por curva,
 * dá caminhos curtos e com poucas dobras, sem atravessar nenhum cartão.
 */
import type { Caixa, Ponto } from './afastar';

const MARGEM = 8;      // distância mínima entre a linha e o cartão
export const SAIDA = 18;  // trecho reto ao sair da coluna (e ao chegar), antes da primeira dobra
const CURVA = 40;      // cada dobra custa como 40 px de linha

type Ligacao = { de: Ponto; para: Ponto }; // de: borda direita do cartão de origem; para: borda esquerda do destino

class Heap {
  private a: { f: number; k: number }[] = [];
  get tamanho() { return this.a.length; }
  push(f: number, k: number) {
    const a = this.a; a.push({ f, k });
    for (let i = a.length - 1; i > 0;) { const p = (i - 1) >> 1; if (a[p].f <= a[i].f) break; [a[p], a[i]] = [a[i], a[p]]; i = p; }
  }
  pop() {
    const a = this.a, topo = a[0], fim = a.pop()!;
    if (a.length) {
      a[0] = fim;
      for (let i = 0; ;) {
        const l = 2 * i + 1, r = l + 1; let m = i;
        if (l < a.length && a[l].f < a[m].f) m = l;
        if (r < a.length && a[r].f < a[m].f) m = r;
        if (m === i) break; [a[m], a[i]] = [a[i], a[m]]; i = m;
      }
    }
    return topo;
  }
}

const unicos = (v: number[]) => [...new Set(v.map(n => Math.round(n * 10) / 10))].sort((a, b) => a - b);

/**
 * Prepara a grade para um conjunto de cartões e de ligações, e devolve a função que roteia cada ligação (ou null,
 * quando não há caminho: aí quem chama usa o traçado simples).
 */
export function criarRoteador(caixas: Caixa[], ligacoes: Ligacao[]) {
  const obst = caixas.map(c => ({ x1: c.x - MARGEM, y1: c.y - MARGEM, x2: c.x + c.w + MARGEM, y2: c.y + c.h + MARGEM }));
  const xsBorda = obst.flatMap(o => [o.x1, o.x2]);
  const ysBorda = obst.flatMap(o => [o.y1, o.y2]);
  const meio = (v: number[]) => { const s = unicos(v); return s.slice(1).map((n, i) => (n + s[i]) / 2); };
  const xs = unicos([...xsBorda, ...meio(xsBorda), ...ligacoes.flatMap(l => [l.de.x + SAIDA, l.para.x - SAIDA]),
    Math.min(...xsBorda) - 40, Math.max(...xsBorda) + 40]);
  const ys = unicos([...ysBorda, ...meio(ysBorda), ...ligacoes.flatMap(l => [l.de.y, l.para.y]),
    Math.min(...ysBorda) - 40, Math.max(...ysBorda) + 40]);
  const NX = xs.length, NY = ys.length;
  const ix = new Map(xs.map((v, i) => [v, i])), iy = new Map(ys.map((v, i) => [v, i]));
  const dentro = (x: number, y: number) => obst.some(o => x > o.x1 && x < o.x2 && y > o.y1 && y < o.y2);
  // livre[i][j]: o ponto não está dentro de cartão; dir/baixo: o trecho até o vizinho não atravessa cartão
  const livre = new Uint8Array(NX * NY), paraDireita = new Uint8Array(NX * NY), paraBaixo = new Uint8Array(NX * NY);
  for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) livre[i * NY + j] = dentro(xs[i], ys[j]) ? 0 : 1;
  for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) {
    const k = i * NY + j;
    if (!livre[k]) continue;
    if (i + 1 < NX && livre[k + NY]) {
      const y = ys[j], a = xs[i], b = xs[i + 1];
      paraDireita[k] = obst.some(o => y > o.y1 && y < o.y2 && a < o.x2 && b > o.x1) ? 0 : 1;
    }
    if (j + 1 < NY && livre[k + 1]) {
      const x = xs[i], a = ys[j], b = ys[j + 1];
      paraBaixo[k] = obst.some(o => x > o.x1 && x < o.x2 && a < o.y2 && b > o.y1) ? 0 : 1;
    }
  }

  return function rotear({ de, para }: Ligacao): Ponto[] | null {
    const i0 = ix.get(Math.round((de.x + SAIDA) * 10) / 10), j0 = iy.get(Math.round(de.y * 10) / 10);
    const i1 = ix.get(Math.round((para.x - SAIDA) * 10) / 10), j1 = iy.get(Math.round(para.y * 10) / 10);
    if (i0 === undefined || j0 === undefined || i1 === undefined || j1 === undefined) return null;
    if (!livre[i0 * NY + j0] || !livre[i1 * NY + j1]) return null;
    // estado = ponto da grade × direção de chegada (0 →, 1 ←, 2 ↓, 3 ↑): a curva custa a mais
    const custo = new Float64Array(NX * NY * 4).fill(Infinity);
    const veio = new Int32Array(NX * NY * 4).fill(-1);
    const h = (i: number, j: number) => Math.abs(xs[i] - xs[i1]) + Math.abs(ys[j] - ys[j1]);
    const heap = new Heap();
    const s0 = (i0 * NY + j0) * 4 + 0; // sai da coluna indo para a direita
    custo[s0] = 0; heap.push(h(i0, j0), s0);
    let fim = -1;
    while (heap.tamanho) {
      const { k: s } = heap.pop();
      const p = s >> 2, d = s & 3, i = Math.floor(p / NY), j = p % NY;
      if (i === i1 && j === j1) { if (d === 0) { fim = s; break; } }
      const viz: [number, number, number, boolean][] = [
        [i + 1, j, 0, i + 1 < NX && !!paraDireita[p]],
        [i - 1, j, 1, i > 0 && !!paraDireita[p - NY]],
        [i, j + 1, 2, j + 1 < NY && !!paraBaixo[p]],
        [i, j - 1, 3, j > 0 && !!paraBaixo[p - 1]],
      ];
      for (const [ni, nj, nd, ok] of viz) {
        if (!ok) continue;
        if ((d ^ nd) === 1 && d < 2 === nd < 2) continue; // não volta pelo mesmo caminho
        const ns = (ni * NY + nj) * 4 + nd;
        const c = custo[s] + Math.abs(xs[ni] - xs[i]) + Math.abs(ys[nj] - ys[j]) + (nd !== d ? CURVA : 0);
        if (c < custo[ns]) { custo[ns] = c; veio[ns] = s; heap.push(c + h(ni, nj), ns); }
      }
    }
    if (fim < 0) return null;
    // refaz o caminho e tira os pontos que não são dobra
    const cam: Ponto[] = [];
    for (let s = fim; s >= 0; s = veio[s]) { const p = s >> 2; cam.push({ x: xs[Math.floor(p / NY)], y: ys[p % NY] }); }
    cam.reverse();
    const pts = [de, ...cam, para];
    return pts.filter((q, n) => {
      if (n === 0 || n === pts.length - 1) return true;
      const a = pts[n - 1], b = pts[n + 1];
      return !((a.x === q.x && q.x === b.x) || (a.y === q.y && q.y === b.y));
    });
  };
}

/** Algum trecho do caminho atravessa algum cartão? (para refazer trajetos do ELK que uma tabela movida cobriu) */
export function atravessa(pontos: Ponto[], caixas: Caixa[]): boolean {
  for (let n = 1; n < pontos.length; n++) {
    const a = pontos[n - 1], b = pontos[n];
    const x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x), y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y);
    if (caixas.some(c => x1 < c.x + c.w - 1 && x2 > c.x + 1 && y1 < c.y + c.h - 1 && y2 > c.y + 1)) return true;
  }
  return false;
}
