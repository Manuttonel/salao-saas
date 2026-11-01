// Aba "Solicitações": pedidos de horário aguardando resposta (site e WhatsApp).
// Qualquer administrador pode aceitar ou recusar. Ao aceitar, o horário vira
// "confirmado" e some das opções de outros clientes; o cliente é avisado por
// WhatsApp.

import { useState } from "react";
import api, { extrairMensagemErro } from "../../services/api";
import { ORIGENS, formatarDataHora, formatarTelefone, iniciais, linkWhatsapp } from "../../services/formatar";

function Cartao({ pedido, profissionais, concorrentes, aoResponder }) {
  const [profissionalId, setProfissionalId] = useState(pedido.profissional_id);
  const [recusando, setRecusando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [processando, setProcessando] = useState(false);
  const [erro, setErro] = useState("");

  async function responder(acao, corpo) {
    setErro(""); setProcessando(true);
    try {
      await api.post(`/agendamentos/${pedido.id}/${acao}`, corpo);
      aoResponder();
    } catch (e) {
      setErro(extrairMensagemErro(e));
      setProcessando(false);
    }
  }

  return (
    <li className="card !p-4 sm:!p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
            {iniciais(pedido.cliente_nome)}
          </span>
          <div>
            <p className="font-semibold leading-tight">{pedido.cliente_nome}</p>
            {pedido.cliente_telefone && (
              <a href={linkWhatsapp(pedido.cliente_telefone)} target="_blank" rel="noreferrer" className="text-xs text-brand-600 hover:underline">
                {formatarTelefone(pedido.cliente_telefone)}
              </a>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className="badge-info">{ORIGENS[pedido.origem] || pedido.origem}</span>
          {pedido.eh_avaliacao && <span className="badge-warn">Avaliação</span>}
          {concorrentes > 0 && <span className="badge-bad" title="Outro pedido disputa este horário: aceitar um impede o outro.">Disputa horário</span>}
        </div>
      </div>

      <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        <div><dt className="rotulo">Procedimento</dt><dd className="font-medium">{pedido.servico_nome}</dd></div>
        <div><dt className="rotulo">Quando</dt><dd className="font-medium">{formatarDataHora(pedido.inicio)}</dd></div>
        <div><dt className="rotulo">Duração</dt><dd className="font-medium">{pedido.duracao_minutos} min</dd></div>
      </dl>
      {pedido.observacoes && <p className="mt-3 rounded-lg bg-card2 px-3 py-2 text-sm text-muted">“{pedido.observacoes}”</p>}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="rotulo" htmlFor={`prof-${pedido.id}`}>Profissional</label>
          <select id={`prof-${pedido.id}`} className="input !w-auto" value={profissionalId} onChange={(e) => setProfissionalId(e.target.value)}>
            {profissionais.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
          </select>
        </div>
        <button className="btn-primary" disabled={processando} onClick={() => responder("aceitar", { profissional_id: profissionalId })}>
          Aceitar
        </button>
        <button className="btn-outline" disabled={processando} onClick={() => setRecusando((v) => !v)}>
          Recusar
        </button>
      </div>

      {recusando && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <input className="input flex-1" placeholder="Motivo (opcional — o cliente recebe)" value={motivo} maxLength={300}
            onChange={(e) => setMotivo(e.target.value)} />
          <button className="btn-danger" disabled={processando} onClick={() => responder("recusar", { motivo })}>Confirmar recusa</button>
        </div>
      )}
      {erro && <p role="alert" className="mt-3 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
    </li>
  );
}

export default function SolicitacoesTab({ pendentes, profissionais, recarregar }) {
  // Quantos OUTROS pedidos disputam o mesmo profissional no mesmo intervalo.
  const concorrentes = (pedido) =>
    pendentes.filter((o) => o.id !== pedido.id && o.profissional_id === pedido.profissional_id
      && o.inicio < pedido.fim && o.fim > pedido.inicio).length;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="titulo text-lg">Solicitações de horário</h2>
        <p className="text-sm text-muted">Pedidos de clientes aguardando sua resposta. O horário só fica indisponível para os outros depois que você aceita.</p>
      </div>
      <ul className="space-y-4">
        {pendentes.map((p) => (
          <Cartao key={p.id} pedido={p} profissionais={profissionais} concorrentes={concorrentes(p)} aoResponder={recarregar} />
        ))}
      </ul>
      {pendentes.length === 0 && (
        <div className="card text-center text-sm text-muted">Nenhuma solicitação aguardando. Quando um cliente pedir um horário, ele aparece aqui.</div>
      )}
    </div>
  );
}
