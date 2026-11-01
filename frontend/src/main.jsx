import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { TemaProvider } from "./context/TemaContext.jsx";
import { aplicarTema, carregarPreferencias } from "./services/tema";
import "./styles/index.css";

// Aplica o tema salvo ANTES do primeiro desenho da tela, para não piscar
// o tema errado enquanto o React carrega.
aplicarTema(carregarPreferencias());

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <TemaProvider>
      <App />
    </TemaProvider>
  </React.StrictMode>
);
