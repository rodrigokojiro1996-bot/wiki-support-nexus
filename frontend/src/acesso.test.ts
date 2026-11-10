import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, sessao } from './api';
import { destinoDepois, iniciais } from './acesso';

const resposta = (status: number, corpo: unknown) => new Response(JSON.stringify(corpo), { status });

describe('sessão que terminou no meio do uso', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('um 401 da API avisa a tela e traz o motivo do servidor', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(401, { detail: 'Entre com a sua conta Microsoft para continuar.' })));
    const aviso = vi.fn();
    const parar = sessao.aoExpirar(aviso);
    await expect(api.modulos()).rejects.toThrow('Entre com a sua conta Microsoft para continuar.');
    expect(aviso).toHaveBeenCalledTimes(1);
    parar();
  });

  it('salvar um manual com a sessão vencida também avisa (sem perder o que está na tela)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(401, { detail: 'Entre com a sua conta Microsoft para continuar.' })));
    const aviso = vi.fn();
    const parar = sessao.aoExpirar(aviso);
    await expect(api.salvarManual({} as never, 'PDV.001')).rejects.toThrow('Entre com a sua conta Microsoft');
    expect(aviso).toHaveBeenCalledTimes(1);
    parar();
  });

  it('resposta normal não avisa', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(200, [])));
    const aviso = vi.fn();
    const parar = sessao.aoExpirar(aviso);
    await api.modulos();
    expect(aviso).not.toHaveBeenCalled();
    parar();
  });

  it('quem parou de ouvir não é mais avisado', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(401, { detail: 'x' })));
    const aviso = vi.fn();
    sessao.aoExpirar(aviso)();
    await api.modulos().catch(() => {});
    expect(aviso).not.toHaveBeenCalled();
  });
});

describe('destino depois de entrar', () => {
  it.each([
    ['/?erro_login=negado', '/'],
    ['/?erro_login=negado&modulo=pdv', '/?modulo=pdv'],
    ['/manuais/DEMO.001', '/manuais/DEMO.001'],
    ['/?modulo=pdv', '/?modulo=pdv']
  ])('%s → %s', (atual, destino) => expect(destinoDepois(atual)).toBe(destino));
});

describe('iniciais no topo', () => {
  it.each([
    ['Carla Exemplo', 'CE'],
    ['João da Silva Conceição', 'JC'],
    ['Ana', 'A'],
    ['ana@farmaciasassociadas.com.br', 'A'],
    ['  ', '?']
  ])('%s → %s', (nome, ini) => expect(iniciais(nome)).toBe(ini));
});
