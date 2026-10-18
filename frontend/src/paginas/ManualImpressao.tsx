import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import Documento from '../componentes/Documento';
import type { Manual } from '../tipos';

/** Versão só do documento, aberta pelo gerador de PDF do backend (cabeçalho e rodapé vêm do gerador). */
export default function ManualImpressao() {
  const { codigo = '' } = useParams();
  const [manual, setManual] = useState<Manual | null>(null);
  useEffect(() => {
    document.documentElement.classList.add('modo-pdf');
    api.manual(codigo).then(setManual);
    return () => document.documentElement.classList.remove('modo-pdf');
  }, [codigo]);
  if (!manual) return null;
  return <div data-pronto=""><Documento manual={manual} /></div>;
}
