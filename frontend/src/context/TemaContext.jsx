// Guarda o tema escolhido e o disponibiliza para qualquer componente via
// useTema(). Ao trocar de tema:
//   1. aplica na hora (aplicarTema muda o atributo data-tema do <html>);
//   2. lembra no navegador (para a próxima visita, mesmo sem login);
//   3. se a pessoa estiver logada, salva também na conta (PATCH
//      /auth/preferencias), para o tema acompanhar em outros aparelhos.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import api from "../services/api";
import { aplicarTema, carregarPreferencias, salvarPreferenciasLocal, COR_PADRAO } from "../services/tema";

const TemaContext = createContext(null);

export function TemaProvider({ children }) {
  const [preferencias, setPreferencias] = useState(carregarPreferencias);
  const temporizador = useRef(null);

  useEffect(() => {
    aplicarTema(preferencias);
    salvarPreferenciasLocal(preferencias);
  }, [preferencias]);

  // Salva na conta com um pequeno atraso: o seletor de cor dispara muitos
  // eventos enquanto a pessoa arrasta, e só o último interessa.
  function sincronizarComConta(novas) {
    if (!localStorage.getItem("access_token")) return;
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => {
      api
        .patch("/auth/preferencias", { tema: novas.tema, cor_primaria: novas.cor })
        .then(({ data }) => {
          const usuario = JSON.parse(localStorage.getItem("usuario") || "null");
          if (usuario) {
            localStorage.setItem("usuario", JSON.stringify({ ...usuario, tema: data.tema, cor_primaria: data.cor_primaria }));
          }
        })
        .catch(() => {
          // Falhou? O tema continua valendo neste navegador; só não sincroniza.
        });
    }, 500);
  }

  // Chamado quando a PESSOA escolhe (clique no seletor).
  const alterar = useCallback(
    (mudanca) => {
      setPreferencias((atual) => {
        const novas = { ...atual, ...mudanca };
        sincronizarComConta(novas);
        return novas;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Chamado no login: o que está salvo na conta passa a valer, sem regravar.
  const adotarDaConta = useCallback((usuario) => {
    if (!usuario?.tema) return;
    setPreferencias({ tema: usuario.tema, cor: usuario.cor_primaria || COR_PADRAO });
  }, []);

  return (
    <TemaContext.Provider value={{ ...preferencias, alterar, adotarDaConta }}>{children}</TemaContext.Provider>
  );
}

export function useTema() {
  const contexto = useContext(TemaContext);
  if (!contexto) throw new Error("useTema precisa estar dentro de <TemaProvider>.");
  return contexto;
}
