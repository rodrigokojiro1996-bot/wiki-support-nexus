import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ambienteDoServidor, api, usuario } from '../api';
import { aplicarTema, useTema } from '../tema';

// nomes e módulos ativos vêm do modulos.json do servidor (GET /api/modulos); esta lista só aparece enquanto carrega
const PADRAO = [
  { id: 'pdv', nome: 'PDV', ativo: true },
  { id: 'adm', nome: 'Retaguarda', ativo: false },
  { id: 'fin', nome: 'Financeiro', ativo: false }
];

function SeuNome() {
  const [nome, setNome] = useState(usuario.ler);
  return (
    <label className="topo-usuario" title="Fica registrado em quem validou relações e vinculou tabelas (guardado só neste navegador)">
      <span>Seu nome</span>
      <input value={nome} placeholder="para a autoria" maxLength={80} aria-label="Seu nome, para registrar a autoria"
        onChange={e => setNome(e.target.value)} onBlur={() => usuario.gravar(nome)} />
    </label>
  );
}

/** Claro (padrão) ou escuro; a escolha fica guardada neste navegador */
function BotaoTema() {
  const tema = useTema();
  const escuro = tema === 'escuro';
  return (
    <button type="button" className="topo-tema" aria-pressed={escuro} onClick={() => aplicarTema(escuro ? 'claro' : 'escuro')}
      title={escuro ? 'Voltar ao tema claro' : 'Usar o tema escuro'} aria-label={escuro ? 'Tema claro' : 'Tema escuro'}>
      <span aria-hidden="true">{escuro ? '☀' : '☾'}</span><span className="topo-tema-txt">{escuro ? 'Tema claro' : 'Tema escuro'}</span>
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
      <div className="topo-extra">{children}<BotaoTema /><SeuNome /></div>
    </header>
    <FaixaAmbiente />
    </>
  );
}
