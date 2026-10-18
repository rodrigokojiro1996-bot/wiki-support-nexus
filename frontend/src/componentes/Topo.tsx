import { Link } from 'react-router-dom';

const MODULOS = [
  { id: 'pdv', nome: 'PDV', ativo: true },
  { id: 'adm', nome: 'Retaguarda', ativo: false },
  { id: 'fin', nome: 'Financeiro', ativo: false }
];

export default function Topo({ children }: { children?: React.ReactNode }) {
  return (
    <header className="topo">
      <Link to="/" className="topo-marca" aria-label="Support Nexus – início">
        <img className="topo-logo" src="/marca/nexus.svg" alt="" />
        <span><b>Support Nexus</b><small>Mapa vivo do sistema</small></span>
      </Link>
      <nav className="topo-modulos" aria-label="Módulos do sistema">
        {MODULOS.map(m => (
          <span key={m.id} className="topo-mod" aria-current={m.ativo ? 'page' : undefined} aria-disabled={!m.ativo || undefined}
            title={m.ativo ? undefined : 'Em breve'}>
            <img src={`/marca/modulo-${m.id}.svg`} alt="" />
            {m.nome}
            {!m.ativo && <small>em breve</small>}
          </span>
        ))}
      </nav>
      <div className="topo-extra">{children}</div>
    </header>
  );
}
