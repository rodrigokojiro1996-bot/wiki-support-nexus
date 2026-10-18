import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import './estilo/app.css';
import './estilo/documento.css';
import MapaSistema from './paginas/MapaSistema';
import ManualPagina from './paginas/ManualPagina';
import ManualImpressao from './paginas/ManualImpressao';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapaSistema />} />
        <Route path="/manuais/:codigo" element={<ManualPagina />} />
        <Route path="/manuais/:codigo/imprimir" element={<ManualImpressao />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
