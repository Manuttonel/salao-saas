// Calendário mensal usado pelo cliente (escolher o dia) e pelo administrador
// (marcar dias disponíveis/indisponíveis).
//
// Recebe a lista de dias que a API devolve em GET /saloes/<id>/calendario:
//   { data, status: "disponivel" | "fechado" | "passado", excecao: "aberto" | "fechado" | null }
//
// - Cliente:        só dias "disponivel" são clicáveis.
// - Administrador:  (modoAdmin) qualquer dia que não passou é clicável, e um
//                   pontinho indica o que ele marcou à mão.

import { dataDeISO, formatarMesAno, hojeISO } from "../services/formatar";

const CABECALHO = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

export default function Calendario({ ano, mes, dias, selecionado, onSelecionar, onMudarMes, modoAdmin = false, carregando = false }) {
  const porData = Object.fromEntries(dias.map((d) => [d.data, d]));
  const primeiro = new Date(ano, mes - 1, 1);
  const vazios = primeiro.getDay(); // 0 = domingo
  const totalDias = new Date(ano, mes, 0).getDate();
  const hoje = hojeISO();
  const mesAtual = hoje.slice(0, 7) === `${ano}-${String(mes).padStart(2, "0")}`;

  const titulo = formatarMesAno(ano, mes);

  const celulas = [];
  for (let i = 0; i < vazios; i += 1) celulas.push(<span key={`v${i}`} />);

  for (let dia = 1; dia <= totalDias; dia += 1) {
    const iso = `${ano}-${String(mes).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
    const info = porData[iso];
    const status = info?.status || "fechado";
    const clicavel = modoAdmin ? status !== "passado" && !!info : status === "disponivel";
    const escolhido = selecionado === iso;

    let classes = "border-transparent text-muted";
    if (status === "passado") classes = "border-transparent text-muted/40";
    else if (status === "fechado") classes = "border-transparent text-muted line-through decoration-muted/50";
    else classes = "border-brand-100 bg-brand-50 text-brand-700 font-medium hover:bg-brand-100";
    if (!clicavel) classes += " cursor-default";
    else if (status === "fechado") classes += " hover:bg-card2";
    if (escolhido) classes = "border-brand-600 bg-brand-600 text-onbrand font-semibold shadow-sm";
    if (iso === hoje && !escolhido) classes += " ring-1 ring-accent/60";

    celulas.push(
      <button
        key={iso}
        type="button"
        disabled={!clicavel}
        onClick={() => onSelecionar(iso)}
        aria-label={`${dataDeISO(iso).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}, ${
          status === "disponivel" ? "disponível" : status === "passado" ? "já passou" : "indisponível"
        }`}
        aria-pressed={escolhido}
        className={`relative aspect-square rounded-lg border text-sm transition ${classes}`}
      >
        {dia}
        {modoAdmin && info?.excecao && (
          <span
            className={`absolute bottom-1 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full ${
              info.excecao === "aberto" ? "bg-[rgb(var(--ok-fg))]" : "bg-[rgb(var(--bad-fg))]"
            }`}
          />
        )}
      </button>
    );
  }

  return (
    <div className={carregando ? "opacity-60 transition" : "transition"}>
      <div className="mb-3 flex items-center justify-between">
        <button type="button" className="btn-ghost btn-sm" onClick={() => onMudarMes(-1)} disabled={!modoAdmin && mesAtual} aria-label="Mês anterior">
          ‹
        </button>
        <span className="titulo text-sm">{titulo}</span>
        <button type="button" className="btn-ghost btn-sm" onClick={() => onMudarMes(1)} aria-label="Próximo mês">
          ›
        </button>
      </div>

      <div className="mb-1 grid grid-cols-7 gap-1 text-center text-[11px] font-medium uppercase tracking-wide text-muted">
        {CABECALHO.map((nome) => (
          <span key={nome}>{nome}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">{celulas}</div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded border border-brand-100 bg-brand-50" /> Disponível
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded border border-line" /> Indisponível
        </span>
        {modoAdmin && (
          <>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--ok-fg))]" /> Aberto por mim
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--bad-fg))]" /> Fechado por mim
            </span>
          </>
        )}
      </div>
    </div>
  );
}
