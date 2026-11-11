/** Auto-organização do diagrama: nenhuma tabela fica por cima de outra. */
export type Ponto = { x: number; y: number };
export type Caixa = { id: string; x: number; y: number; w: number; h: number };

export const FOLGA = 28; // espaço mínimo entre dois cartões

/**
 * Empurra as caixas que se sobrepõem até nenhuma encostar na outra (com `folga` entre elas).
 *
 * Quem cede numa sobreposição é decidido pela `prioridade` (menor = mais firme): a tabela que a pessoa está arrastando
 * tem prioridade 0 e nunca sai do lugar; as que a equipe já posicionou, 1; as do layout automático, 2. No empate,
 * cede a mais distante da âncora (a tabela arrastada), para o empurrão se propagar para fora; sem âncora, a de
 * índice maior. O empurrão vai pelo eixo com menos sobreposição, para o lado em que a caixa já estava.
 *
 * Devolve só as caixas que mudaram de lugar.
 */
export function afastar(caixas: Caixa[], prioridade: (id: string) => number, ancora?: Ponto, folga = FOLGA,
                        voltas = 120): Map<string, Ponto> {
  const c = caixas.map(b => ({ ...b }));
  const dist = (b: Caixa) => (ancora ? Math.hypot(b.x + b.w / 2 - ancora.x, b.y + b.h / 2 - ancora.y) : 0);
  for (let v = 0; v < voltas; v++) {
    let mexeu = false;
    for (let i = 0; i < c.length; i++) {
      for (let j = i + 1; j < c.length; j++) {
        const a = c[i], b = c[j];
        const sx = (a.w + b.w) / 2 + folga - Math.abs(a.x + a.w / 2 - (b.x + b.w / 2));
        const sy = (a.h + b.h) / 2 + folga - Math.abs(a.y + a.h / 2 - (b.y + b.h / 2));
        if (sx <= 0.5 || sy <= 0.5) continue;
        const pa = prioridade(a.id), pb = prioridade(b.id);
        if (pa === 0 && pb === 0) continue; // duas arrastadas juntas: ficam como a pessoa pôs
        const cede = pa !== pb ? (pa > pb ? a : b) : ancora ? (dist(a) > dist(b) ? a : b) : b;
        const outra = cede === a ? b : a;
        // eixo com menos sobreposição; o lado é onde o centro de quem cede já estava (empate: direita/baixo)
        if (sx < sy) {
          const lado = cede.x + cede.w / 2 >= outra.x + outra.w / 2 ? 1 : -1;
          cede.x += lado * sx;
        } else {
          const lado = cede.y + cede.h / 2 >= outra.y + outra.h / 2 ? 1 : -1;
          cede.y += lado * sy;
        }
        mexeu = true;
      }
    }
    if (!mexeu) break;
  }
  const saida = new Map<string, Ponto>();
  c.forEach((b, i) => {
    if (Math.abs(b.x - caixas[i].x) > 0.5 || Math.abs(b.y - caixas[i].y) > 0.5) saida.set(b.id, { x: Math.round(b.x), y: Math.round(b.y) });
  });
  return saida;
}

/** Duas caixas se sobrepõem (com folga)? */
export function sobrepoe(a: Caixa, b: Caixa, folga = 0): boolean {
  return a.x < b.x + b.w + folga && b.x < a.x + a.w + folga && a.y < b.y + b.h + folga && b.y < a.y + a.h + folga;
}
