// Seletor de aparência: Unisex, Glow ou Dark (e, no Unisex, a cor principal).
//
// Dois modos:
//   - <SeletorTema inline />  -> aberto, usado na tela de login;
//   - <SeletorTema />         -> botão que abre um painel, usado na barra de topo.

import { useEffect, useRef, useState } from "react";
import { useTema } from "../context/TemaContext";
import { TEMAS, CORES_SUGERIDAS } from "../services/tema";

function Amostra({ cores }) {
  return (
    <span className="flex -space-x-1">
      {cores.map((cor) => (
        <span key={cor} className="h-5 w-5 rounded-full border border-white/70 shadow-sm" style={{ background: cor }} />
      ))}
    </span>
  );
}

function Opcoes() {
  const { tema, cor, alterar } = useTema();

  return (
    <div className="space-y-3">
      <div className="grid gap-2">
        {TEMAS.map((opcao) => (
          <button
            key={opcao.id}
            type="button"
            onClick={() => alterar({ tema: opcao.id })}
            aria-pressed={tema === opcao.id}
            className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
              tema === opcao.id ? "border-brand-600 bg-brand-50" : "border-line bg-card hover:bg-card2"
            }`}
          >
            <Amostra cores={opcao.amostra} />
            <span className="flex-1">
              <span className="block text-sm font-semibold text-ink">{opcao.nome}</span>
              <span className="block text-xs text-muted">{opcao.descricao}</span>
            </span>
            {tema === opcao.id && <span className="text-brand-600 text-sm" aria-hidden="true">✓</span>}
          </button>
        ))}
      </div>

      {tema === "unisex" && (
        <div>
          <p className="rotulo">Cor principal</p>
          <div className="flex flex-wrap items-center gap-2">
            {CORES_SUGERIDAS.map((sugestao) => (
              <button
                key={sugestao}
                type="button"
                aria-label={`Usar a cor ${sugestao}`}
                onClick={() => alterar({ cor: sugestao })}
                className={`h-7 w-7 rounded-full border-2 transition ${
                  cor.toLowerCase() === sugestao ? "border-ink scale-110" : "border-transparent"
                }`}
                style={{ background: sugestao }}
              />
            ))}
            <label className="relative h-7 w-7 cursor-pointer overflow-hidden rounded-full border border-line" title="Outra cor">
              <span
                className="absolute inset-0 flex items-center justify-center text-xs text-muted"
                style={{ background: "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)" }}
              />
              <input
                type="color"
                value={cor}
                onChange={(e) => alterar({ cor: e.target.value })}
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                aria-label="Escolher outra cor"
              />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SeletorTema({ inline = false }) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef(null);

  // Fecha o painel ao clicar fora dele ou apertar Esc.
  useEffect(() => {
    if (!aberto) return undefined;
    const fora = (e) => raiz.current && !raiz.current.contains(e.target) && setAberto(false);
    const esc = (e) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  if (inline) {
    return (
      <div>
        <p className="rotulo">Aparência</p>
        <Opcoes />
      </div>
    );
  }

  return (
    <div className="relative" ref={raiz}>
      <button type="button" className="btn-outline btn-sm" onClick={() => setAberto((v) => !v)} aria-expanded={aberto}>
        <span aria-hidden="true">◐</span> Tema
      </button>
      {aberto && (
        <div className="card absolute right-0 z-30 mt-2 w-72 !p-4">
          <p className="titulo mb-3 text-sm">Aparência</p>
          <Opcoes />
        </div>
      )}
    </div>
  );
}
