// Página do cliente: SOLICITAR um horário e acompanhar os pedidos.
//
// Passo a passo: salão -> procedimento (ou "Marcar Avaliação") -> dia
// (só dias disponíveis) -> profissional (opcional) e horário -> enviar.
// O pedido NÃO é uma reserva: ele chega ao salão como "pendente" e só vira
// horário garantido quando um administrador aceita.

import { useCallback, useEffect, useMemo, useState } from "react";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";
import Calendario from "../components/Calendario";
import useCalendario from "../hooks/useCalendario";
import {
  STATUS, agruparPorCategoria, formatarDataHora, formatarDiaLongo, formatarHora, moeda,
} from "../services/formatar";

function Passo({ numero, titulo, children, bloqueado = false }) {
  return (
    <section className={`card transition ${bloqueado ? "opacity-50" : ""}`}>
      <h2 className="titulo mb-4 flex items-center gap-3 text-base">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-sm text-onbrand">{numero}</span>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

export default function AgendaCliente() {
  const usuario = obterUsuarioLogado();

  const [saloes, setSaloes] = useState([]);
  const [salaoId, setSalaoId] = useState("");
  const [servicos, setServicos] = useState([]);
  const [profissionais, setProfissionais] = useState([]);
  const [servicoId, setServicoId] = useState("");
  const [dia, setDia] = useState("");
  const [profissionalId, setProfissionalId] = useState("");
  const [horarios, setHorarios] = useState([]);
  const [horario, setHorario] = useState("");
  const [observacoes, setObservacoes] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [meusPedidos, setMeusPedidos] = useState([]);

  const calendario = useCalendario(salaoId);
  const servico = servicos.find((s) => s.id === servicoId);
  const avaliacao = servicos.find((s) => s.eh_avaliacao);
  const grupos = useMemo(() => agruparPorCategoria(servicos), [servicos]);

  const carregarPedidos = useCallback(async () => {
    try {
      const { data } = await api.get("/agendamentos/");
      setMeusPedidos(data.sort((a, b) => b.inicio.localeCompare(a.inicio)));
    } catch {
      // sem pedidos ainda
    }
  }, []);

  useEffect(() => {
    api.get("/saloes/").then(({ data }) => {
      setSaloes(data);
      if (data.length === 1) setSalaoId(data[0].id);
    });
    carregarPedidos();
    // Atualiza sozinho: assim o cliente vê o pedido ser confirmado sem recarregar.
    const intervalo = setInterval(carregarPedidos, 30000);
    return () => clearInterval(intervalo);
  }, [carregarPedidos]);

  // Trocou de salão: recarrega o cardápio e zera as escolhas seguintes.
  useEffect(() => {
    setServicoId(""); setDia(""); setProfissionalId(""); setHorario(""); setHorarios([]);
    if (!salaoId) { setServicos([]); setProfissionais([]); return; }
    api.get(`/saloes/${salaoId}/servicos`).then(({ data }) => setServicos(data));
    api.get(`/saloes/${salaoId}/profissionais`).then(({ data }) => setProfissionais(data));
  }, [salaoId]);

  const buscarHorarios = useCallback(async () => {
    if (!(salaoId && servicoId && dia)) { setHorarios([]); return; }
    try {
      const params = { salao_id: salaoId, servico_id: servicoId, data: dia };
      if (profissionalId) params.profissional_id = profissionalId;
      const { data } = await api.get("/agendamentos/horarios-disponiveis", { params });
      setHorarios(data.horarios);
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }, [salaoId, servicoId, dia, profissionalId]);

  useEffect(() => { setHorario(""); buscarHorarios(); }, [buscarHorarios]);

  function escolherServico(id) {
    setServicoId(id); setHorario(""); setSucesso(""); setErro("");
  }

  async function enviarSolicitacao() {
    setErro(""); setSucesso(""); setEnviando(true);
    try {
      const corpo = { salao_id: salaoId, servico_id: servicoId, inicio: horario, observacoes };
      if (profissionalId) corpo.profissional_id = profissionalId;
      await api.post("/agendamentos/", corpo);
      setSucesso("Solicitação enviada! O salão vai analisar e você será avisado quando for confirmada.");
      setHorario(""); setObservacoes("");
      buscarHorarios(); carregarPedidos();
    } catch (e) {
      setErro(extrairMensagemErro(e));
      buscarHorarios();
    } finally {
      setEnviando(false);
    }
  }

  async function cancelar(id) {
    if (!confirm("Cancelar este pedido de horário?")) return;
    try {
      await api.post(`/agendamentos/${id}/cancelar`);
      carregarPedidos(); buscarHorarios();
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  const ativos = meusPedidos.filter((p) => ["pendente", "confirmado"].includes(p.status));
  const anteriores = meusPedidos.filter((p) => !["pendente", "confirmado"].includes(p.status)).slice(0, 5);

  return (
    <div>
      <Navbar usuario={usuario} />
      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[1fr_340px]">
        <div className="space-y-5">
          <Passo numero={1} titulo="Escolha o salão">
            {saloes.length === 0 ? (
              <p className="text-sm text-muted">Nenhum salão cadastrado ainda.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {saloes.map((s) => (
                  <button key={s.id} type="button" onClick={() => setSalaoId(s.id)} aria-pressed={salaoId === s.id}
                    className={`rounded-xl border p-3 text-left transition ${salaoId === s.id ? "border-brand-600 bg-brand-50" : "border-line hover:bg-card2"}`}>
                    <span className="block font-semibold">{s.nome}</span>
                    <span className="block text-xs text-muted">{s.endereco || "Endereço não informado"}</span>
                  </button>
                ))}
              </div>
            )}
          </Passo>

          <Passo numero={2} titulo="O que você quer fazer?" bloqueado={!salaoId}>
            {salaoId && (
              <div className="space-y-4">
                {avaliacao && (
                  <button type="button" onClick={() => escolherServico(avaliacao.id)} aria-pressed={servicoId === avaliacao.id}
                    className={`flex w-full items-center justify-between gap-3 rounded-xl border-2 p-4 text-left transition ${
                      servicoId === avaliacao.id ? "border-brand-600 bg-brand-50" : "border-dashed border-accent/60 hover:bg-card2"}`}>
                    <span>
                      <span className="titulo block text-base text-brand-600">{avaliacao.nome}</span>
                      <span className="block text-sm text-muted">{avaliacao.descricao || "Uma conversa rápida para avaliar o que você precisa."}</span>
                    </span>
                    <span className="badge-info shrink-0">{avaliacao.duracao_minutos} min</span>
                  </button>
                )}

                {grupos.map((grupo) => (
                  <div key={grupo.id}>
                    <h3 className="rotulo uppercase tracking-wide">{grupo.nome}</h3>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {grupo.itens.map((item) => (
                        <button key={item.id} type="button" onClick={() => escolherServico(item.id)} aria-pressed={servicoId === item.id}
                          className={`rounded-xl border p-3 text-left transition ${servicoId === item.id ? "border-brand-600 bg-brand-50" : "border-line hover:bg-card2"}`}>
                          <span className="block font-medium">{item.nome}</span>
                          <span className="block text-xs text-muted">{item.duracao_minutos} min · {moeda(item.preco)}</span>
                          {item.descricao && <span className="mt-1 block text-xs text-muted">{item.descricao}</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {grupos.length === 0 && !avaliacao && <p className="text-sm text-muted">Este salão ainda não cadastrou procedimentos.</p>}
              </div>
            )}
          </Passo>

          <Passo numero={3} titulo="Escolha o dia" bloqueado={!servicoId}>
            {servicoId && (
              <div className="max-w-sm">
                <Calendario {...calendario} selecionado={dia} carregando={calendario.carregando}
                  onSelecionar={(iso) => { setDia(iso); setSucesso(""); }} onMudarMes={calendario.mudarMes} />
              </div>
            )}
          </Passo>

          <Passo numero={4} titulo="Profissional e horário" bloqueado={!dia}>
            {dia && (
              <div className="space-y-4">
                <p className="text-sm text-muted">{formatarDiaLongo(dia)}</p>
                <div className="max-w-xs">
                  <label className="rotulo" htmlFor="prof">Profissional</label>
                  <select id="prof" className="input" value={profissionalId} onChange={(e) => setProfissionalId(e.target.value)}>
                    <option value="">Qualquer um disponível</option>
                    {profissionais.map((p) => <option key={p.id} value={p.id}>{p.nome}{p.especialidade ? ` — ${p.especialidade}` : ""}</option>)}
                  </select>
                </div>

                {horarios.length > 0 ? (
                  <div className="flex flex-wrap gap-2" role="group" aria-label="Horários disponíveis">
                    {horarios.map((h) => (
                      <button key={h} type="button" className={horario === h ? "chip-on" : "chip"} onClick={() => setHorario(h)}>
                        {formatarHora(h)}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted">Nenhum horário livre neste dia. Tente outro dia ou outro profissional.</p>
                )}
              </div>
            )}
          </Passo>

          {horario && servico && (
            <section className="card border-brand-600">
              <h2 className="titulo mb-3 text-base">Confira e envie</h2>
              <p className="text-sm">
                <strong>{servico.nome}</strong> ({servico.duracao_minutos} min) · <span>{formatarDataHora(horario)}</span>
              </p>
              <label className="rotulo mt-4" htmlFor="obs">Quer avisar algo ao salão? (opcional)</label>
              <textarea id="obs" rows={2} maxLength={500} className="input" placeholder="Ex.: cabelo longo, primeira vez..."
                value={observacoes} onChange={(e) => setObservacoes(e.target.value)} />
              <p className="mt-3 text-xs text-muted">Seu horário só fica garantido depois que o salão confirmar o pedido.</p>
              <button className="btn-primary mt-4 w-full sm:w-auto" disabled={enviando} onClick={enviarSolicitacao}>
                {enviando ? "Enviando..." : "Enviar solicitação"}
              </button>
            </section>
          )}

          {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
          {sucesso && <p role="status" className="badge-ok !block !rounded-xl !px-4 !py-3 text-sm">{sucesso}</p>}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <section className="card">
            <h2 className="titulo mb-3 text-base">Meus pedidos</h2>
            <ul className="space-y-3">
              {ativos.map((p) => (
                <li key={p.id} className="rounded-xl border border-line p-3 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{p.servico_nome}</span>
                    <span className={STATUS[p.status].classe}>{STATUS[p.status].texto}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">{formatarDataHora(p.inicio)} · {p.salao_nome}</p>
                  <button className="mt-2 text-xs text-[rgb(var(--bad-fg))] hover:underline" onClick={() => cancelar(p.id)}>Cancelar</button>
                </li>
              ))}
              {ativos.length === 0 && <li className="text-sm text-muted">Você não tem pedidos em andamento.</li>}
            </ul>
          </section>

          {anteriores.length > 0 && (
            <section className="card">
              <h2 className="titulo mb-3 text-base">Anteriores</h2>
              <ul className="space-y-2 text-sm">
                {anteriores.map((p) => (
                  <li key={p.id}>
                    <div className="flex items-center justify-between gap-2">
                      <span>{p.servico_nome}</span>
                      <span className={STATUS[p.status].classe}>{STATUS[p.status].texto}</span>
                    </div>
                    <p className="text-xs text-muted">{formatarDataHora(p.inicio)}</p>
                    {p.motivo_recusa && <p className="text-xs text-muted">Motivo: {p.motivo_recusa}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </main>
    </div>
  );
}
