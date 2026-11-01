// Painel de gestão do salão — usado pelo DONO e pelos ADMINISTRADORES.
//
// Abas:
//   Solicitações   pedidos de horário aguardando aceite (com contador)
//   Agenda         dias disponíveis no calendário + atendimentos do dia
//   Clientes       controle de clientes (CRM)
//   Procedimentos  cabelo, unhas, estética... com o tempo de cada um
//   Equipe         profissionais e administradores
//   Configurações  dados do salão, bot de WhatsApp, assinatura
//
// Se o salão ainda não existe (dono recém-cadastrado), mostra o formulário
// de criação. Se a assinatura da plataforma estiver vencida, o painel fica
// bloqueado (o cliente final continua usando a agenda normalmente).

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";
import SolicitacoesTab from "../components/admin/SolicitacoesTab";
import AgendaTab from "../components/admin/AgendaTab";
import ClientesTab from "../components/admin/ClientesTab";
import ProcedimentosTab from "../components/admin/ProcedimentosTab";
import EquipeTab from "../components/admin/EquipeTab";
import ConfigTab from "../components/admin/ConfigTab";
import { DIAS_SEMANA_CURTO } from "../services/formatar";

const ABAS = [
  { id: "solicitacoes", nome: "Solicitações" },
  { id: "agenda", nome: "Agenda" },
  { id: "clientes", nome: "Clientes" },
  { id: "procedimentos", nome: "Procedimentos" },
  { id: "equipe", nome: "Equipe" },
  { id: "config", nome: "Configurações" },
];

const INTERVALO_SOLICITACOES_MS = 20000;

export default function DashboardDono() {
  const usuario = obterUsuarioLogado();
  const ehDono = usuario.papel === "dono";

  const [salaoId, setSalaoId] = useState(usuario.saloes?.[0] || null);
  const [salao, setSalao] = useState(null);
  const [servicos, setServicos] = useState([]);
  const [profissionais, setProfissionais] = useState([]);
  const [pendentes, setPendentes] = useState([]);
  const [aba, setAba] = useState("solicitacoes");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  const recarregarSalao = useCallback(async () => {
    const { data } = await api.get(`/saloes/${salaoId}`);
    setSalao(data);
    return data;
  }, [salaoId]);

  const recarregarServicos = useCallback(async () => {
    const { data } = await api.get(`/saloes/${salaoId}/servicos`);
    setServicos(data);
  }, [salaoId]);

  const recarregarProfissionais = useCallback(async () => {
    const { data } = await api.get(`/saloes/${salaoId}/profissionais`);
    setProfissionais(data);
  }, [salaoId]);

  const recarregarPendentes = useCallback(async () => {
    try {
      const { data } = await api.get("/agendamentos/", { params: { salao_id: salaoId, status: "pendente", futuros: 1 } });
      setPendentes(data);
    } catch {
      // painel bloqueado ou sem rede: mantém a lista anterior
    }
  }, [salaoId]);

  // Ao abrir: atualiza a lista de salões do usuário (pode ter mudado desde o login).
  useEffect(() => {
    api.get("/auth/me").then(({ data }) => {
      localStorage.setItem("usuario", JSON.stringify({ ...usuario, ...data }));
      if (!salaoId && data.saloes?.length) setSalaoId(data.saloes[0]);
      else if (!data.saloes?.length) setCarregando(false);
    }).catch(() => setCarregando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!salaoId) return;
    setCarregando(true);
    recarregarSalao()
      .then((dados) => dados.acesso_liberado && Promise.all([recarregarServicos(), recarregarProfissionais(), recarregarPendentes()]))
      .catch((e) => setErro(extrairMensagemErro(e)))
      .finally(() => setCarregando(false));
  }, [salaoId, recarregarSalao, recarregarServicos, recarregarProfissionais, recarregarPendentes]);

  // Verifica novos pedidos de tempos em tempos (sem precisar recarregar a página).
  useEffect(() => {
    if (!salao?.acesso_liberado) return undefined;
    const intervalo = setInterval(recarregarPendentes, INTERVALO_SOLICITACOES_MS);
    return () => clearInterval(intervalo);
  }, [salao?.acesso_liberado, recarregarPendentes]);

  const titulo = salao?.nome || "Salão SaaS";

  if (carregando) {
    return (
      <div>
        <Navbar usuario={usuario} />
        <p className="p-8 text-center text-muted">Carregando…</p>
      </div>
    );
  }

  if (!salaoId) {
    return (
      <div>
        <Navbar usuario={usuario} />
        <main className="mx-auto max-w-2xl px-4 py-8">
          {erro && <p role="alert" className="mb-4 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
          {ehDono ? (
            <CriarSalaoForm onCriado={(novo) => {
              localStorage.setItem("usuario", JSON.stringify({ ...usuario, saloes: [novo.id] }));
              setSalaoId(novo.id);
            }} />
          ) : (
            <div className="card text-sm text-muted">Você ainda não foi vinculado a nenhum salão. Peça ao dono para adicionar você em Equipe → Administradores.</div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div>
      <Navbar usuario={usuario} titulo={titulo} />

      {salao && !salao.acesso_liberado ? (
        <main className="mx-auto max-w-2xl px-4 py-8">
          <div className="card space-y-3 text-center">
            <h2 className="titulo text-lg">Painel bloqueado</h2>
            <p className="text-sm text-muted">A assinatura da plataforma está vencida. Seus clientes continuam vendo a agenda normalmente, mas a gestão do salão fica bloqueada até a regularização.</p>
            {ehDono ? <Link to="/assinatura" className="btn-primary">Regularizar agora</Link> : <p className="text-sm">Avise o dono do salão para regularizar o pagamento.</p>}
          </div>
        </main>
      ) : (
        <>
          <nav className="border-b border-line bg-card/70" aria-label="Seções do painel">
            <div className="abas-rolagem mx-auto flex max-w-6xl overflow-x-auto px-2" role="tablist">
              {ABAS.map((item) => (
                <button key={item.id} role="tab" aria-selected={aba === item.id} className={aba === item.id ? "tab-on" : "tab"} onClick={() => setAba(item.id)}>
                  {item.nome}
                  {item.id === "solicitacoes" && pendentes.length > 0 && (
                    <span className="ml-2 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-brand-600 px-1.5 text-xs font-semibold text-onbrand">{pendentes.length}</span>
                  )}
                </button>
              ))}
            </div>
          </nav>

          <main className="mx-auto max-w-6xl px-4 py-6">
            {erro && <p role="alert" className="mb-4 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
            {salao && aba === "solicitacoes" && <SolicitacoesTab pendentes={pendentes} profissionais={profissionais} recarregar={recarregarPendentes} />}
            {salao && aba === "agenda" && <AgendaTab salao={salao} servicos={servicos} profissionais={profissionais} recarregarPendentes={recarregarPendentes} />}
            {salao && aba === "clientes" && <ClientesTab salao={salao} />}
            {salao && aba === "procedimentos" && <ProcedimentosTab salaoId={salao.id} servicos={servicos} recarregar={recarregarServicos} />}
            {salao && aba === "equipe" && <EquipeTab salao={salao} profissionais={profissionais} recarregarProfissionais={recarregarProfissionais} ehDono={ehDono} />}
            {salao && aba === "config" && <ConfigTab salao={salao} recarregarSalao={recarregarSalao} ehDono={ehDono} />}
          </main>
        </>
      )}
    </div>
  );
}

function CriarSalaoForm({ onCriado }) {
  const [form, setForm] = useState({
    nome: "", telefone: "", endereco: "", horario_abertura: "09:00", horario_fechamento: "19:00",
    dias_funcionamento: [0, 1, 2, 3, 4, 5],
  });
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  function alternarDia(dia) {
    setForm((f) => ({
      ...f,
      dias_funcionamento: f.dias_funcionamento.includes(dia)
        ? f.dias_funcionamento.filter((d) => d !== dia)
        : [...f.dias_funcionamento, dia].sort(),
    }));
  }

  async function enviar(e) {
    e.preventDefault(); setErro(""); setEnviando(true);
    try {
      const { data } = await api.post("/saloes/", form);
      onCriado(data);
    } catch (err) {
      setErro(extrairMensagemErro(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="card">
      <h2 className="titulo mb-1 text-xl">Cadastre seu salão</h2>
      <p className="mb-5 text-sm text-muted">Leva um minuto. Depois você cadastra os procedimentos, a equipe e os dias de atendimento.</p>
      <form onSubmit={enviar} className="space-y-3">
        <input required placeholder="Nome do salão ou barbearia" className="input" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
        <input required placeholder="Telefone / WhatsApp" className="input" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
        <input placeholder="Endereço (opcional)" className="input" value={form.endereco} onChange={(e) => setForm({ ...form, endereco: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <div><label className="rotulo" htmlFor="n-ab">Abre às</label>
            <input id="n-ab" type="time" className="input" value={form.horario_abertura} onChange={(e) => setForm({ ...form, horario_abertura: e.target.value })} /></div>
          <div><label className="rotulo" htmlFor="n-fe">Fecha às</label>
            <input id="n-fe" type="time" className="input" value={form.horario_fechamento} onChange={(e) => setForm({ ...form, horario_fechamento: e.target.value })} /></div>
        </div>
        <div>
          <p className="rotulo">Dias em que atende</p>
          <div className="flex flex-wrap gap-1.5">
            {DIAS_SEMANA_CURTO.map((nome, i) => (
              <button type="button" key={nome} className={form.dias_funcionamento.includes(i) ? "chip-on" : "chip"} onClick={() => alternarDia(i)}>{nome}</button>
            ))}
          </div>
        </div>
        {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
        <button disabled={enviando} className="btn-primary w-full">{enviando ? "Salvando…" : "Criar salão"}</button>
      </form>
    </div>
  );
}
