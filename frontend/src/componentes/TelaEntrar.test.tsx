import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import TelaEntrar from './TelaEntrar';
import { mensagemErroLogin } from '../acesso';

const html = (voltar: string, erro?: string) => renderToStaticMarkup(<TelaEntrar voltar={voltar} erro={erro} />);

describe('tela de entrar', () => {
  it('o botão vai para o login da Microsoft e depois volta para a página pedida', () => {
    expect(html('/manuais/DEMO.001')).toContain('href="/api/auth/entrar?voltar=%2Fmanuais%2FDEMO.001"');
  });

  it('sem erro, nenhum alerta', () => {
    expect(html('/')).not.toContain('role="alert"');
  });

  it.each(['negado', 'cancelado', 'expirado', 'indisponivel', 'config', 'invalido', 'codigo-que-nao-existe'])(
    'erro %s aparece como alerta, com texto', erro => {
      expect(html('/', erro)).toMatch(/role="alert"[^>]*>[^<]{20,}/);
    });

  it('cada erro conhecido diz uma coisa diferente', () => {
    const codigos = ['negado', 'cancelado', 'expirado', 'indisponivel', 'config', 'invalido'];
    expect(new Set(codigos.map(mensagemErroLogin)).size).toBe(codigos.length);
  });
});
