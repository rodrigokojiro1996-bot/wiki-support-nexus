import { createContext, useContext, useEffect, useState } from 'react';
import { destinoDepois } from '../acesso';
import { sessao, type Acesso as EstadoAcesso } from '../api';
import TelaEntrar from './TelaEntrar';

const Contexto = createContext<EstadoAcesso>({ login: false, usuario: null });

/** { login: false } com o login desligado; com ele ligado, quem entrou */
export const useAcesso = () => useContext(Contexto);

const paginaAtual = () => destinoDepois(window.location.pathname + window.location.search);

/**
 * Porta do app. Pergunta ao servidor se o login Microsoft está ligado e quem entrou:
 * - desligado: o app abre como sempre (autoria pelo nome digitado no topo);
 * - ligado e sem sessão: tela de entrar;
 * - a sessão terminou com a tela aberta: aviso no topo, sem trocar de tela (não perde o que está em edição).
 */
export default function Acesso({ children }: { children: React.ReactNode }) {
  const [estado, setEstado] = useState<EstadoAcesso | null>(null);
  const [terminou, setTerminou] = useState(false);

  useEffect(() => {
    // sem resposta do servidor, abre como desligado: se o login estiver ligado, a API recusa e o aviso aparece
    sessao.eu().then(setEstado).catch(() => setEstado({ login: false, usuario: null }));
    return sessao.aoExpirar(() => setTerminou(true));
  }, []);

  // de volta a esta aba depois de entrar de novo na outra: confere e tira o aviso
  useEffect(() => {
    if (!terminou) return;
    const conferir = () => sessao.eu().then(e => { if (e.usuario) { setEstado(e); setTerminou(false); } }).catch(() => {});
    window.addEventListener('focus', conferir);
    return () => window.removeEventListener('focus', conferir);
  }, [terminou]);

  if (!estado) return null;
  if (estado.login && !estado.usuario) {
    const erro = new URLSearchParams(window.location.search).get('erro_login') ?? undefined;
    return <TelaEntrar voltar={paginaAtual()} erro={erro} />;
  }
  return (
    <Contexto.Provider value={estado}>
      {terminou && (
        <div className="faixa-sessao" role="alert">
          <span><b>Sua sessão terminou.</b> Entre de novo numa nova aba: o que está aberto aqui continua, e depois é só salvar.</span>
          <a className="faixa-sessao-botao" href={sessao.urlEntrar(paginaAtual())} target="_blank" rel="noopener">Entrar de novo</a>
        </div>
      )}
      {children}
    </Contexto.Provider>
  );
}
