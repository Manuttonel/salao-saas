// Aba "Agenda": o administrador marca no calendário os dias em que atende
// (ou não) e vê/gerencia os atendimentos do dia selecionado.
//
// Marcar um dia cria uma EXCEÇÃO sobre a regra geral do salão (dias da
// semana nas Configurações). Dica: ligando "Atender somente nos dias que eu
// marcar" nas Configurações, só os dias marcados como disponíveis aparecem
// para os clientes.

import { useCallback, useEffect, useState } from "react";
import api, { extrairMensagemErro } from "../../services/api";
import Calendario from "../Calendario";
import useCalendario from "../../hooks/useCalendario";
import { STATUS, ORIGENS, formatarDiaLongo, formatarHora, hojeISO } from "../../services/formatar";

function AgendarManual({ salao, dia, servicos, profissionais, aoAgendar }) {
  const [clientes, setClientes] = useState([]);
  const [form, setForm] = useState({ cliente_id: "", servico_id: "", profissional_id: "", inicio: "" });
  const [horarios, setHorarios] = useState([]);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/clientes/", { params: { salao_id: salao.id } }).then(({ data }) => setClientes(data));
  }, [salao.id]);

  useEffect(() => {
    setForm((f) => ({ ...f, inicio: "" }));
    if (!(form.servico_id && form.profissional_id)) { setHorarios([]); return; }
    api.get("/agendamentos/horarios-disponiveis", {
      params: { salao_id: salao.id, servico_id: form.servico_id, profissional_id: form.profissional_id, data: dia },
    }).then(({ data }) => setHorarios(data.horarios)).catch(() => setHorarios([]));
  }, [salao.id, dia, form.servico_id, form.profissional_id]);

  async function salvar(e) {
    e.preventDefault(); setErro("");
    try {
      await api.post("/agendamentos/manual", form);
      setForm({ cliente_id: "", servico_id: "", profissional_id: "", inicio: "" });
      aoAgendar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  return (
    <form onSubmit={salvar} className="mt-3 grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2">
      <select required className="input" value={form.cliente_id} onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}>
        <option value="">Cliente…</option>
        {clientes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
      </select>
      <select required className="input" value={form.servico_id} onChange={(e) => setForm({ ...form, servico_id: e.target.value })}>
        <option value="">Procedimento…</option>
        {servicos.map((s) => <option key={s.id} value={s.id}>{s.nome} ({s.duracao_minutos} min)</option>)}
      </select>
      <select required className="input" value={form.profissional_id} onChange={(e) => setForm({ ...form, profissional_id: e.target.value })}>
        <option value="">Profissional…</option>
        {profissionais.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
      </select>
      <select required className="input" value={form.inicio} onChange={(e) => setForm({ ...form, inicio: e.target.value })} disabled={horarios.length === 0}>
        <option value="">{horarios.length ? "Horário…" : "Escolha procedimento e profissional"}</option>
        {horarios.map((h) => <option key={h} value={h}>{formatarHora(h)}</option>)}
      </select>
      {clientes.length === 0 && <p className="text-xs text-muted sm:col-span-2">Cadastre o cliente primeiro na aba Clientes.</p>}
      {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))] sm:col-span-2">{erro}</p>}
      <button className="btn-primary sm:col-span-2">Agendar (já confirmado)</button>
    </form>
  );
}

export default function AgendaTab({ salao, servicos, profissionais, recarregarPendentes }) {
  const calendario = useCalendario(salao.id);
  const [dia, setDia] = useState(hojeISO());
  const [agendamentos, setAgendamentos] = useState([]);
  const [hora, setHora] = useState({ inicio: "", fim: "", motivo: "" });
  const [manual, setManual] = useState(false);
  const [erro, setErro] = useState("");

  const infoDia = calendario.dias.find((d) => d.data === dia);

  const carregarDia = useCallback(async () => {
    try {
      const { data } = await api.get("/agendamentos/", {
        params: { salao_id: salao.id, data: dia, status: "pendente,confirmado,concluido" },
      });
      setAgendamentos(data);
    } catch {
      setAgendamentos([]);
    }
  }, [salao.id, dia]);

  useEffect(() => { carregarDia(); }, [carregarDia]);

  // Trocou de mês: o dia selecionado ficou para trás, então seleciona um do mês
  // novo (o primeiro disponível a partir de hoje) para o painel não mostrar um
  // dia que nem está na tela.
  useEffect(() => {
    if (!calendario.dias.length || calendario.dias.some((d) => d.data === dia)) return;
    const hoje = hojeISO();
    const futuros = calendario.dias.filter((d) => d.data >= hoje);
    const escolhido = futuros.find((d) => d.status === "disponivel") || futuros[0] || calendario.dias[0];
    setDia(escolhido.data);
  }, [calendario.dias, dia]);

  useEffect(() => { setHora({ inicio: "", fim: "", motivo: infoDia?.motivo || "" }); setErro(""); }, [dia, infoDia?.motivo]);

  async function marcar(aberto) {
    setErro("");
    try {
      await api.put(`/saloes/${salao.id}/dias-agenda/${dia}`, {
        aberto, hora_inicio: hora.inicio || null, hora_fim: hora.fim || null, motivo: hora.motivo,
      });
      calendario.recarregar();
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }

  async function voltarAoPadrao() {
    setErro("");
    try {
      await api.delete(`/saloes/${salao.id}/dias-agenda/${dia}`);
      calendario.recarregar();
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }

  async function acao(id, nome) {
    if (nome === "cancelar" && !confirm("Cancelar este horário? O cliente será avisado se já estava confirmado.")) return;
    try {
      await api.post(`/agendamentos/${id}/${nome}`);
      carregarDia(); recarregarPendentes();
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  const passado = dia < hojeISO();

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <section className="card h-fit">
        <h2 className="titulo mb-1 text-lg">Dias disponíveis</h2>
        <p className="mb-4 text-sm text-muted">Clique em um dia para marcá-lo como disponível ou indisponível.</p>
        <Calendario {...calendario} modoAdmin selecionado={dia} onSelecionar={setDia} onMudarMes={calendario.mudarMes} />
      </section>

      <div className="space-y-5">
        <section className="card">
          <h2 className="titulo text-lg">{formatarDiaLongo(dia)}</h2>
          <p className="mt-1 text-sm text-muted">
            {passado ? "Este dia já passou." : infoDia?.status === "disponivel"
              ? `Atendendo das ${infoDia.hora_inicio} às ${infoDia.hora_fim}${infoDia.excecao ? " (marcado por você)" : ""}.`
              : `Sem atendimento${infoDia?.excecao === "fechado" ? " (marcado por você)" : ""}${infoDia?.motivo ? ` — ${infoDia.motivo}` : ""}.`}
          </p>

          {!passado && (
            <div className="mt-4 space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div><label className="rotulo" htmlFor="h-ini">Abrir às (opcional)</label>
                  <input id="h-ini" type="time" className="input" value={hora.inicio} onChange={(e) => setHora({ ...hora, inicio: e.target.value })} /></div>
                <div><label className="rotulo" htmlFor="h-fim">Fechar às (opcional)</label>
                  <input id="h-fim" type="time" className="input" value={hora.fim} onChange={(e) => setHora({ ...hora, fim: e.target.value })} /></div>
                <div><label className="rotulo" htmlFor="h-mot">Observação</label>
                  <input id="h-mot" className="input" placeholder="Ex.: Feriado" maxLength={120} value={hora.motivo} onChange={(e) => setHora({ ...hora, motivo: e.target.value })} /></div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-primary" onClick={() => marcar(true)}>Marcar como disponível</button>
                <button className="btn-outline" onClick={() => marcar(false)}>Marcar como indisponível</button>
                {infoDia?.excecao && <button className="btn-ghost" onClick={voltarAoPadrao}>Voltar ao padrão</button>}
              </div>
              {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
            </div>
          )}
        </section>

        <section className="card">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="titulo text-lg">Atendimentos do dia</h2>
            {!passado && <button className="btn-outline btn-sm" onClick={() => setManual((v) => !v)}>{manual ? "Fechar" : "+ Agendar manualmente"}</button>}
          </div>
          {manual && (
            <AgendarManual salao={salao} dia={dia} servicos={servicos} profissionais={profissionais}
              aoAgendar={() => { setManual(false); carregarDia(); }} />
          )}

          <ul className="mt-4 divide-y divide-line">
            {agendamentos.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div>
                  <p className="font-medium">
                    {formatarHora(a.inicio)} – {formatarHora(a.fim)} · {a.cliente_nome}
                  </p>
                  <p className="text-xs text-muted">{a.servico_nome} com {a.profissional_nome} · {ORIGENS[a.origem]}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={STATUS[a.status].classe}>{STATUS[a.status].texto}</span>
                  {a.status === "confirmado" && <button className="btn-outline btn-sm" onClick={() => acao(a.id, "concluir")}>Concluir</button>}
                  {["pendente", "confirmado"].includes(a.status) && (
                    <button className="btn-ghost btn-sm text-[rgb(var(--bad-fg))]" onClick={() => acao(a.id, "cancelar")}>Cancelar</button>
                  )}
                </div>
              </li>
            ))}
            {agendamentos.length === 0 && <li className="py-3 text-sm text-muted">Nada agendado para este dia.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}
