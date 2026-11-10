/** Login Microsoft na interface: as regras que não dependem de tela (testadas em acesso.test.ts). */

// códigos que o servidor põe em ?erro_login= (backend/app/rotas/auth.py); o motivo detalhado fica só no log dele
const MENSAGENS: Record<string, string> = {
  negado: 'Esta conta não tem acesso. Entre com a sua conta @farmaciasassociadas.com.br; se a Microsoft abrir outra conta, escolha a da empresa.',
  cancelado: 'O login foi cancelado na tela da Microsoft. Clique em Entrar para tentar de novo.',
  expirado: 'A tentativa de entrar expirou. Clique em Entrar para começar de novo.',
  indisponivel: 'Não foi possível falar com a Microsoft agora. Tente de novo em alguns instantes.',
  config: 'O login Microsoft não está configurado corretamente neste servidor. Avise a equipe de TI.',
  invalido: 'A resposta da Microsoft não pôde ser conferida. Tente de novo; se continuar, avise a equipe de TI.'
};

export const mensagemErroLogin = (codigo: string) =>
  MENSAGENS[codigo] ?? 'Não foi possível entrar. Tente de novo; se continuar, avise a equipe de TI.';

/** A página atual sem o aviso de erro do login: é para lá que a pessoa volta depois de entrar */
export function destinoDepois(caminho: string): string {
  const url = new URL(caminho, 'http://local');
  url.searchParams.delete('erro_login');
  return url.pathname + url.search;
}

/** "Carla Exemplo" → "CE"; "João da Silva Conceição" → "JC" (primeiro e último nome) */
export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const ultima = partes.length > 1 ? partes[partes.length - 1][0] : '';
  return (partes[0][0] + ultima).toUpperCase();
}
