import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
// fontes da interface empacotadas no build: funcionam sem internet e não consultam o Google a cada acesso
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import './estilo/app.css';
import './estilo/documento.css';
import MapaSistema from './paginas/MapaSistema';
import ManualPagina from './paginas/ManualPagina';
import ManualImpressao from './paginas/ManualImpressao';
import ManualEditor from './paginas/ManualEditor';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapaSistema />} />
        <Route path="/manuais/novo" element={<ManualEditor />} />
        <Route path="/manuais/:codigo" element={<ManualPagina />} />
        <Route path="/manuais/:codigo/editar" element={<ManualEditor />} />
        <Route path="/manuais/:codigo/imprimir" element={<ManualImpressao />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
