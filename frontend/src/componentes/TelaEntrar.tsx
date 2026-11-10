import { mensagemErroLogin } from '../acesso';
import { sessao } from '../api';

/* Tela de entrar com a conta Microsoft. É um nó do próprio mapa: tabelas do PDV ao fundo, desenhadas como no
   diagrama, com as relações convergindo para o cartão. Uma relação acesa em laranja (o destaque do diagrama) se
   desenha uma vez até o cartão; é o único movimento da tela. */

type No = { nome: string; x: number; y: number; cols: string[] };
const LARGURA = 170, CAB = 30, LINHA = 22; // mesma proporção dos cartões do diagrama (cabeçalho e linhas)

// viewBox 1200 × 800; o centro (600, 400) fica sob o cartão, então toda ligação "entra" nele em qualquer tela
const NOS: No[] = [
  { nome: 'lojas', x: 515, y: 24, cols: ['id', 'nome'] },
  { nome: 'vendas', x: 80, y: 130, cols: ['id', 'caixa_id', 'cliente_id'] },
  { nome: 'caixa', x: 940, y: 112, cols: ['id', 'loja_id', 'aberto_em'] },
  { nome: 'clientes', x: 60, y: 560, cols: ['id', 'cpf'] },
  { nome: 'produtos', x: 965, y: 575, cols: ['id', 'ean', 'preco'] },
  { nome: 'usuarios', x: 470, y: 704, cols: ['id', 'login'] }
];
// [início (com o ponto da chave), caminho]
const LIGACOES: [number, number, string][] = [
  [600, 98, 'M600 98V400'],
  [250, 193, 'M250 193H330V400H600'],
  [230, 601, 'M230 601H330V400'],
  [965, 616, 'M965 616H700V400'],
  [555, 704, 'M555 704V400'],
  [80, 215, 'M80 215H40V601H60'],    // vendas.cliente_id → clientes.id
  [940, 175, 'M940 175H820V65H685']  // caixa.loja_id → lojas.id
];
const RELACAO_ACESA = 'M940 153H880V400H600'; // caixa.id → o cartão de entrar

function Tabela({ no, acesa }: { no: No; acesa?: boolean }) {
  const { x, y } = no;
  const altura = CAB + LINHA * no.cols.length;
  return (
    <g className={acesa ? 'no no-aceso' : 'no'}>
      <rect className="no-fundo" x={x} y={y} width={LARGURA} height={altura} rx={8} />
      <path className="no-cab" d={`M${x} ${y + CAB}V${y + 8}a8 8 0 0 1 8-8H${x + LARGURA - 8}a8 8 0 0 1 8 8V${y + CAB}Z`} />
      <line className="no-div" x1={x} x2={x + LARGURA} y1={y + CAB} y2={y + CAB} />
      <rect className="no-borda" x={x} y={y} width={LARGURA} height={altura} rx={8} />
      <text className="no-tit" x={x + 12} y={y + 20}>{no.nome}</text>
      {no.cols.map((c, i) => <text key={c} className="no-col" x={x + 12} y={y + CAB + LINHA * i + 15}>{c}</text>)}
    </g>
  );
}

function MapaDoSistema() {
  return (
    // tamanho real (1 unidade = 1 px, como no diagrama), centrado no cartão; os pontos do fundo ficam no CSS
    <svg className="entrar-mapa" viewBox="0 0 1200 800" width="1200" height="800" aria-hidden="true" focusable="false">
      <g className="fundo">
        {LIGACOES.map(([cx, cy, d]) => (
          <g key={d}><path className="lig" d={d} /><circle className="lig-ponto" cx={cx} cy={cy} r={3.5} /></g>
        ))}
        {NOS.map(n => <Tabela key={n.nome} no={n} />)}
      </g>
      <path className="rel" d={RELACAO_ACESA} pathLength={1} />
      <circle className="rel-ponto" cx={940} cy={153} r={4.5} />
      <Tabela no={NOS[2]} acesa />
    </svg>
  );
}

function MarcaMicrosoft() {
  return (
    <span className="entrar-ms" aria-hidden="true">
      <svg viewBox="0 0 21 21">
        <rect x="1" y="1" width="9" height="9" fill="#f25022" />
        <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
        <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
        <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
      </svg>
    </span>
  );
}

/** voltar: página para onde ir depois de entrar; erro: código de ?erro_login= quando a tentativa anterior falhou */
export default function TelaEntrar({ voltar, erro }: { voltar: string; erro?: string }) {
  return (
    <main className="entrar">
      <MapaDoSistema />
      <section className="entrar-no" aria-labelledby="entrar-titulo">
        <div className="entrar-placa">
          <img src="/marca/logo-associadas.png" alt="Farmácias Associadas" />
        </div>
        <div className="entrar-corpo">
          <h1 id="entrar-titulo">Support Nexus</h1>
          <p className="entrar-sub">Mapa vivo do sistema</p>
          {erro && <p className="entrar-erro" role="alert">{mensagemErroLogin(erro)}</p>}
          <a className="entrar-botao" href={sessao.urlEntrar(voltar)}>
            <MarcaMicrosoft />
            Entrar com a conta Microsoft
          </a>
          <p className="entrar-nota">Só contas <b>@farmaciasassociadas.com.br</b> têm acesso.</p>
        </div>
      </section>
    </main>
  );
}
