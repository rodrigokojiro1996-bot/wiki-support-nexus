import { describe, expect, it } from 'vitest';
import { textoRodape } from './dataHora';

describe('textoRodape', () => {
  it('manual alterado: dia/mês/ano e a hora, sem converter o fuso', () => {
    expect(textoRodape('2026-10-27 23:59:10')).toBe('Manual alterado em 27/10/2026 às 23:59');
  });
  it('sem alteração pela interface: o texto padrão', () => {
    expect(textoRodape(null)).toBe('Documento gerado pelo Support Nexus');
    expect(textoRodape(undefined)).toBe('Documento gerado pelo Support Nexus');
  });
});
