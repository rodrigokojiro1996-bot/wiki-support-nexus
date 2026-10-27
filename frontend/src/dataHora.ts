/**
 * "Manual alterado em 27/10/2026 às 20:15". A data já vem do servidor na hora de Brasília ("AAAA-MM-DD HH:MM:SS"),
 * então aqui só se troca o formato: sem new Date(), que converteria para o fuso de quem está olhando.
 * Mesma regra de texto_rodape() em backend/app/pdf.py.
 */
export function textoRodape(alteradoEm?: string | null): string {
  const m = alteradoEm && /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(alteradoEm);
  if (!m) return 'Documento gerado pelo Support Nexus';
  const [, ano, mes, dia, hora, minuto] = m;
  return `Manual alterado em ${dia}/${mes}/${ano} às ${hora}:${minuto}`;
}
