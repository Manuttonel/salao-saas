// Painel do dono do salão.
//
// Fluxo:
//   1. Se o dono ainda não tem salão cadastrado, mostra o formulário de
//      criação (POST /api/saloes/).
//   2. Com o salão criado, mostra: status da assinatura (bloqueia a
//      gestão se estiver vencida — Salao.acesso_liberado, calculado no
//      backend), cadastro de serviços, cadastro de profissionais e a
//      lista de agendamentos do salão.

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";

const DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

export default function DashboardDono() {
  const navigate = useNavigate();
  const usuario = obterUsuarioLogado();

  const [salao, setSalao] = useState(null);
  const [servicos, setServicos] = useState([]);
  const [profissionais, setProfissionais] = useState([]);
  const [agendamentos, setAgendamentos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    carregarSalaoDoDono();
  }, []);

  async function carregarSalaoDoDono() {
    setCarregando(true);
    try {
      if (usuario.saloes && usuario.saloes.length > 0) {
        const salaoId = usuario.saloes[0];
        const { data } = await api.get(`/saloes/${salaoId}`);
        setSalao(data);
        await Promise.all([carregarServicos(salaoId), carregarProfissionais(salaoId), carregarAgendamentos(salaoId)]);
      }
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  async function carregarServicos(salaoId) {
    const { data } = await api.get(`/saloes/${salaoId}/servicos`);
    setServicos(data);
  }

  async function carregarProfissionais(salaoId) {
    const { data } = await api.get(`/saloes/${salaoId}/profissionais`);
    setProfissionais(data);
  }

  async function carregarAgendamentos(salaoId) {
    const { data } = await api.get(`/agendamentos/`, { params: { salao_id: salaoId } });
    setAgendamentos(data);
  }

  async function cancelarAgendamento(id) {
    try {
      await api.post(`/agendamentos/${id}/cancelar`);
      await carregarAgendamentos(salao.id);
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  if (carregando) {
    return <div className="p-8 text-center text-gray-500">Carregando...</div>;
  }

  return (
    <div>
      <Navbar usuario={usuario} />
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {erro && <p className="text-sm text-red-600">{erro}</p>}

        {!salao ? (
          <CriarSalaoForm
            onCriado={(novoSalao) => {
              usuario.saloes = [novoSalao.id];
              localStorage.setItem("usuario", JSON.stringify(usuario));
              setSalao(novoSalao);
            }}
          />
        ) : (
          <>
            <BannerAssinatura salao={salao} navigate={navigate} />
            <SecaoServicos salaoId={salao.id} servicos={servicos} recarregar={() => carregarServicos(salao.id)} bloqueado={!salao.acesso_liberado} />
            <SecaoProfissionais salaoId={salao.id} profissionais={profissionais} recarregar={() => carregarProfissionais(salao.id)} bloqueado={!salao.acesso_liberado} />
            <SecaoAgendamentos agendamentos={agendamentos} onCancelar={cancelarAgendamento} />
          </>
        )}
      </div>
    </div>
  );
}

function BannerAssinatura({ salao, navigate }) {
  if (salao.acesso_liberado) {
    return (
      <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-md px-4 py-3 flex items-center justify-between">
        <span>Assinatura em dia. Painel liberado.</span>
        <Link to="/assinatura" className="underline">Ver assinatura</Link>
      </div>
    );
  }
  return (
    <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-md px-4 py-3 flex items-center justify-between">
      <span>Assinatura vencida — a gestão do salão está bloqueada até a regularização.</span>
      <button onClick={() => navigate("/assinatura")} className="underline font-medium">
        Regularizar agora
      </button>
    </div>
  );
}

function CriarSalaoForm({ onCriado }) {
  const [form, setForm] = useState({
    nome: "",
    telefone: "",
    endereco: "",
    horario_abertura: "09:00",
    horario_fechamento: "19:00",
    dias_funcionamento: [0, 1, 2, 3, 4, 5],
  });
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  function alternarDia(dia) {
    setForm((atual) => {
      const jaTem = atual.dias_funcionamento.includes(dia);
      return {
        ...atual,
        dias_funcionamento: jaTem
          ? atual.dias_funcionamento.filter((d) => d !== dia)
          : [...atual.dias_funcionamento, dia].sort(),
      };
    });
  }

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
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
    <div className="bg-white border border-gray-200 rounded-xl p-6 max-w-lg">
      <h2 className="font-semibold mb-4">Cadastre seu salão</h2>
      <form onSubmit={enviar} className="space-y-3">
        <input required placeholder="Nome do salão" className="w-full border rounded-md px-3 py-2 text-sm"
          value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
        <input required placeholder="Telefone" className="w-full border rounded-md px-3 py-2 text-sm"
          value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
        <input placeholder="Endereço" className="w-full border rounded-md px-3 py-2 text-sm"
          value={form.endereco} onChange={(e) => setForm({ ...form, endereco: e.target.value })} />
        <div className="flex gap-3">
          <label className="text-sm text-gray-600 flex-1">
            Abertura
            <input type="time" className="w-full border rounded-md px-3 py-2 text-sm mt-1"
              value={form.horario_abertura} onChange={(e) => setForm({ ...form, horario_abertura: e.target.value })} />
          </label>
          <label className="text-sm text-gray-600 flex-1">
            Fechamento
            <input type="time" className="w-full border rounded-md px-3 py-2 text-sm mt-1"
              value={form.horario_fechamento} onChange={(e) => setForm({ ...form, horario_fechamento: e.target.value })} />
          </label>
        </div>
        <div>
          <p className="text-sm text-gray-600 mb-1">Dias de funcionamento</p>
          <div className="flex gap-1 flex-wrap">
            {DIAS_SEMANA.map((label, indice) => (
              <button type="button" key={indice}
                onClick={() => alternarDia(indice)}
                className={`px-2 py-1 rounded-md text-xs border ${
                  form.dias_funcionamento.includes(indice)
                    ? "bg-brand-600 text-white border-brand-600"
                    : "bg-white text-gray-600 border-gray-300"
                }`}>
                {label}
              </button>
            ))}
          </div>
        </div>
        {erro && <p className="text-sm text-red-600">{erro}</p>}
        <button disabled={enviando} className="bg-brand-600 hover:bg-brand-700 text-white rounded-md py-2 px-4 text-sm">
          {enviando ? "Salvando..." : "Criar salão"}
        </button>
      </form>
    </div>
  );
}

function SecaoServicos({ salaoId, servicos, recarregar, bloqueado }) {
  const [form, setForm] = useState({ nome: "", duracao_minutos: 30, preco: "" });
  const [erro, setErro] = useState("");

  async function adicionar(e) {
    e.preventDefault();
    setErro("");
    try {
      await api.post(`/saloes/${salaoId}/servicos`, form);
      setForm({ nome: "", duracao_minutos: 30, preco: "" });
      recarregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <h2 className="font-semibold mb-4">Serviços</h2>
      <ul className="mb-4 divide-y divide-gray-100">
        {servicos.map((s) => (
          <li key={s.id} className="py-2 flex justify-between text-sm">
            <span>{s.nome} — {s.duracao_minutos} min</span>
            <span className="text-gray-500">R$ {s.preco.toFixed(2)}</span>
          </li>
        ))}
        {servicos.length === 0 && <p className="text-sm text-gray-400 py-2">Nenhum serviço cadastrado ainda.</p>}
      </ul>

      {!bloqueado && (
        <form onSubmit={adicionar} className="flex gap-2 flex-wrap items-end">
          <input required placeholder="Nome do serviço" className="border rounded-md px-3 py-2 text-sm flex-1 min-w-[150px]"
            value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
          <input required type="number" min="5" placeholder="Duração (min)" className="border rounded-md px-3 py-2 text-sm w-32"
            value={form.duracao_minutos} onChange={(e) => setForm({ ...form, duracao_minutos: e.target.value })} />
          <input required type="number" min="0" step="0.01" placeholder="Preço (R$)" className="border rounded-md px-3 py-2 text-sm w-32"
            value={form.preco} onChange={(e) => setForm({ ...form, preco: e.target.value })} />
          <button className="bg-brand-600 hover:bg-brand-700 text-white rounded-md py-2 px-4 text-sm">Adicionar</button>
        </form>
      )}
      {erro && <p className="text-sm text-red-600 mt-2">{erro}</p>}
    </section>
  );
}

function SecaoProfissionais({ salaoId, profissionais, recarregar, bloqueado }) {
  const [form, setForm] = useState({ nome: "", email: "", telefone: "", senha_provisoria: "", especialidade: "" });
  const [erro, setErro] = useState("");

  async function adicionar(e) {
    e.preventDefault();
    setErro("");
    try {
      await api.post(`/saloes/${salaoId}/profissionais`, form);
      setForm({ nome: "", email: "", telefone: "", senha_provisoria: "", especialidade: "" });
      recarregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <h2 className="font-semibold mb-4">Profissionais</h2>
      <ul className="mb-4 divide-y divide-gray-100">
        {profissionais.map((p) => (
          <li key={p.id} className="py-2 text-sm">
            {p.nome} {p.especialidade ? `— ${p.especialidade}` : ""}
          </li>
        ))}
        {profissionais.length === 0 && <p className="text-sm text-gray-400 py-2">Nenhum profissional cadastrado ainda.</p>}
      </ul>

      {!bloqueado && (
        <form onSubmit={adicionar} className="grid grid-cols-2 gap-2">
          <input required placeholder="Nome" className="border rounded-md px-3 py-2 text-sm"
            value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
          <input required type="email" placeholder="E-mail" className="border rounded-md px-3 py-2 text-sm"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input required placeholder="Telefone" className="border rounded-md px-3 py-2 text-sm"
            value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
          <input required type="password" placeholder="Senha provisória" className="border rounded-md px-3 py-2 text-sm"
            value={form.senha_provisoria} onChange={(e) => setForm({ ...form, senha_provisoria: e.target.value })} />
          <input placeholder="Especialidade (opcional)" className="border rounded-md px-3 py-2 text-sm col-span-2"
            value={form.especialidade} onChange={(e) => setForm({ ...form, especialidade: e.target.value })} />
          <button className="bg-brand-600 hover:bg-brand-700 text-white rounded-md py-2 px-4 text-sm col-span-2">
            Cadastrar profissional
          </button>
        </form>
      )}
      {erro && <p className="text-sm text-red-600 mt-2">{erro}</p>}
    </section>
  );
}

function SecaoAgendamentos({ agendamentos, onCancelar }) {
  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <h2 className="font-semibold mb-4">Agendamentos</h2>
      <ul className="divide-y divide-gray-100">
        {agendamentos.map((a) => (
          <li key={a.id} className="py-2 flex justify-between items-center text-sm">
            <span>
              {new Date(a.inicio).toLocaleString("pt-BR")} — {a.cliente_nome} com {a.profissional_nome} ({a.servico_nome})
              <span className="ml-2 text-xs text-gray-400">[{a.status}]</span>
            </span>
            {a.status !== "cancelado" && (
              <button onClick={() => onCancelar(a.id)} className="text-red-600 hover:underline text-xs">
                Cancelar
              </button>
            )}
          </li>
        ))}
        {agendamentos.length === 0 && <p className="text-sm text-gray-400 py-2">Nenhum agendamento ainda.</p>}
      </ul>
    </section>
  );
}
