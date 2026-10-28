import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ambienteDoServidor, api, usuario } from '../api';

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

/** Homologação: avisa em toda tela que o conteúdo é de exemplo e pode sumir (NEXUS_AMBIENTE=homologacao) */
function FaixaAmbiente() {
  const [ambiente, setAmbiente] = useState('');
  useEffect(() => { ambienteDoServidor().then(setAmbiente); }, []);
  if (ambiente !== 'homologacao') return null;
  return <div className="faixa-ambiente" role="note"><b>Ambiente de homologação</b> — o que for criado aqui pode ser apagado a qualquer momento.</div>;
}

export default function Topo({ children }: { children?: React.ReactNode }) {
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
        {modulos.map(m => (
          <span key={m.id} className="topo-mod" aria-current={m.ativo ? 'page' : undefined} aria-disabled={!m.ativo || undefined}
            title={m.ativo ? undefined : 'Em breve'}>
            <img src={`/marca/modulo-${m.id}.png`} alt="" />
            {m.nome}
            {!m.ativo && <small>em breve</small>}
          </span>
        ))}
      </nav>
      <div className="topo-extra">{children}<SeuNome /></div>
    </header>
    <FaixaAmbiente />
    </>
  );
}
