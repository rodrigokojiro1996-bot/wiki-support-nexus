import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { iniciais } from '../acesso';
import { ambienteDoServidor, api, sessao, usuario } from '../api';
import { aplicarTema, useTema } from '../tema';
import { useAcesso } from './Acesso';

// nomes e módulos ativos vêm do modulos.json do servidor (GET /api/modulos); esta lista só aparece enquanto carrega
const PADRAO = [
  { id: 'pdv', nome: 'PDV', ativo: true },
  { id: 'adm', nome: 'Retaguarda', ativo: false },
  { id: 'fin', nome: 'Financeiro', ativo: false }
];

function SeuNome() {
  const [nome, setNome] = useState(usuario.ler);
  return (
    <label className="topo-usuario" title="Vai para o Histórico de alterações em tudo o que você validar, alterar, salvar ou excluir (guardado só neste navegador)">
      <span>Seu nome</span>
      <input value={nome} placeholder="para a autoria" maxLength={80} aria-label="Seu nome, para registrar a autoria"
        onChange={e => setNome(e.target.value)} onBlur={() => usuario.gravar(nome)} />
    </label>
  );
}

/** Com o login Microsoft: quem entrou e o botão de sair. Sem ele: o campo "Seu nome" para a autoria. */
function Quem() {
  const { login, usuario: pessoa } = useAcesso();
  if (!login) return <SeuNome />;
  if (!pessoa) return null;
  const sair = () => { sessao.sair().finally(() => window.location.assign('/')); };
  return (
    <div className="topo-quem" title={pessoa.email}>
      <span className="topo-quem-ini" aria-hidden="true">{iniciais(pessoa.nome)}</span>
      <span className="topo-quem-nome">{pessoa.nome}</span>
      <button type="button" className="topo-sair" onClick={sair}>Sair</button>
    </div>
  );
}

const SOL = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);
const LUA = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" />
  </svg>
);

/** Claro (padrão) ou escuro; a escolha fica guardada neste navegador. O novo tema se abre em círculo a partir do botão. */
function BotaoTema() {
  const tema = useTema();
  const escuro = tema === 'escuro';
  return (
    <button type="button" className="topo-tema topo-tema-icone" aria-pressed={escuro}
      onClick={e => aplicarTema(escuro ? 'claro' : 'escuro', { x: e.clientX, y: e.clientY })}
      title={escuro ? 'Voltar ao tema claro' : 'Usar o tema escuro'} aria-label={escuro ? 'Tema claro' : 'Tema escuro'}>
      <span className="topo-tema-ic" aria-hidden="true">{escuro ? SOL : LUA}</span>
    </button>
  );
}

/** Homologação: avisa em toda tela que o conteúdo é de exemplo e pode sumir (NEXUS_AMBIENTE=homologacao) */
function FaixaAmbiente() {
  const [ambiente, setAmbiente] = useState('');
  useEffect(() => { ambienteDoServidor().then(setAmbiente); }, []);
  if (ambiente !== 'homologacao') return null;
  return <div className="faixa-ambiente" role="note"><b>Ambiente de homologação</b> — o que for criado aqui pode ser apagado a qualquer momento.</div>;
}

/** modulo: o módulo que a página mostra (fica destacado); os módulos com banco mapeado levam ao mapa deles */
export default function Topo({ children, modulo }: { children?: React.ReactNode; modulo?: string }) {
  const [modulos, setModulos] = useState(PADRAO);
  useEffect(() => {
    // ativo = o módulo já tem banco mapeado (os outros aparecem como "em breve")
    api.modulos().then(ms => setModulos(ms.map(m => ({ id: m.id, nome: m.nome, ativo: !!m.banco })))).catch(() => {});
  }, []);
  return (
    <>
    <header className="topo">
      <Link to="/" className="topo-marca" aria-label="Support Nexus – início">
        <img className="topo-logo" src="/marca/logo-associadas.png" alt="Farmácias Associadas" />
        <span className="topo-div" aria-hidden="true" />
        <span><b>Support Nexus</b><small>Mapa vivo do sistema</small></span>
      </Link>
      <nav className="topo-modulos" aria-label="Módulos do sistema">
        {modulos.map(m => m.ativo ? (
          <Link key={m.id} to={`/?modulo=${encodeURIComponent(m.id)}`} className="topo-mod" aria-current={m.id === modulo ? 'page' : undefined}>
            <img src={`/marca/modulo-${m.id}.svg`} alt="" />
            {m.nome}
          </Link>
        ) : (
          <span key={m.id} className="topo-mod" aria-disabled title="Em breve">
            <img src={`/marca/modulo-${m.id}.svg`} alt="" />
            {m.nome}
            <small>em breve</small>
          </span>
        ))}
      </nav>
      <div className="topo-extra">
        {children}
        <Link to="/historico" className="topo-tema topo-historico" title="Quem validou, alterou, salvou ou excluiu o quê, e quando">
          <span aria-hidden="true">↺</span><span className="topo-tema-txt">Histórico</span>
        </Link>
        <BotaoTema /><Quem />
      </div>
    </header>
    <FaixaAmbiente />
    </>
  );
}
