// Aba "Configurações": dados e horário do salão, modo de agenda, WhatsApp
// (instância, endereço do webhook e simulador do bot) e assinatura.

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { URL_BASE_API, extrairMensagemErro } from "../../services/api";
import { DIAS_SEMANA_CURTO } from "../../services/formatar";

function DadosDoSalao({ salao, recarregar }) {
  const [form, setForm] = useState({
    nome: salao.nome, telefone: salao.telefone, endereco: salao.endereco || "",
    horario_abertura: salao.horario_abertura, horario_fechamento: salao.horario_fechamento,
    dias_funcionamento: salao.dias_funcionamento, somente_dias_marcados: salao.somente_dias_marcados,
  });
  const [msg, setMsg] = useState({ tipo: "", texto: "" });

  function alternarDia(dia) {
    setForm((f) => ({
      ...f,
      dias_funcionamento: f.dias_funcionamento.includes(dia)
        ? f.dias_funcionamento.filter((d) => d !== dia)
        : [...f.dias_funcionamento, dia].sort(),
    }));
  }

  async function salvar(e) {
    e.preventDefault();
    try {
      await api.put(`/saloes/${salao.id}`, form);
      setMsg({ tipo: "ok", texto: "Configurações salvas." });
      recarregar();
    } catch (err) {
      setMsg({ tipo: "erro", texto: extrairMensagemErro(err) });
    }
  }

  return (
    <section className="card">
      <h2 className="titulo mb-4 text-lg">Dados do salão</h2>
      <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
        <div><label className="rotulo" htmlFor="s-nome">Nome</label>
          <input id="s-nome" required className="input" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
        <div><label className="rotulo" htmlFor="s-tel">Telefone</label>
          <input id="s-tel" required className="input" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} /></div>
        <div className="sm:col-span-2"><label className="rotulo" htmlFor="s-end">Endereço</label>
          <input id="s-end" className="input" value={form.endereco} onChange={(e) => setForm({ ...form, endereco: e.target.value })} /></div>
        <div><label className="rotulo" htmlFor="s-ab">Abre às</label>
          <input id="s-ab" type="time" required className="input" value={form.horario_abertura} onChange={(e) => setForm({ ...form, horario_abertura: e.target.value })} /></div>
        <div><label className="rotulo" htmlFor="s-fe">Fecha às</label>
          <input id="s-fe" type="time" required className="input" value={form.horario_fechamento} onChange={(e) => setForm({ ...form, horario_fechamento: e.target.value })} /></div>

        <div className="sm:col-span-2">
          <p className="rotulo">Dias da semana em que atende (regra geral)</p>
          <div className="flex flex-wrap gap-1.5">
            {DIAS_SEMANA_CURTO.map((nome, indice) => (
              <button type="button" key={nome} className={form.dias_funcionamento.includes(indice) ? "chip-on" : "chip"} onClick={() => alternarDia(indice)}>{nome}</button>
            ))}
          </div>
        </div>

        <label className="flex items-start gap-2 rounded-xl border border-line p-3 text-sm sm:col-span-2">
          <input type="checkbox" className="mt-0.5" checked={form.somente_dias_marcados}
            onChange={(e) => setForm({ ...form, somente_dias_marcados: e.target.checked })} />
          <span>
            <strong>Atender somente nos dias que eu marcar na agenda</strong>
            <span className="block text-muted">Ligado: os clientes só veem os dias que você marcou como disponíveis no calendário (aba Agenda). Desligado: vale a regra geral acima, e você marca só as exceções.</span>
          </span>
        </label>

        <div className="flex items-center gap-3 sm:col-span-2">
          <button className="btn-primary">Salvar</button>
          {msg.texto && <span role="status" className={`text-sm ${msg.tipo === "ok" ? "text-[rgb(var(--ok-fg))]" : "text-[rgb(var(--bad-fg))]"}`}>{msg.texto}</span>}
        </div>
      </form>
    </section>
  );
}

function Simulador({ salaoId }) {
  const [mensagens, setMensagens] = useState([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const fim = useRef(null);

  useEffect(() => { fim.current?.scrollIntoView({ block: "nearest" }); }, [mensagens]);

  async function enviar(conteudo) {
    if (!conteudo.trim() || enviando) return;
    setMensagens((m) => [...m, { de: "cliente", texto: conteudo }]);
    setTexto(""); setEnviando(true);
    try {
      const { data } = await api.post(`/saloes/${salaoId}/bot/simular`, { texto: conteudo, nome: "Cliente Teste" });
      setMensagens((m) => [...m, ...data.respostas.map((r) => ({ de: "bot", texto: r }))]);
    } catch (e) {
      setMensagens((m) => [...m, { de: "bot", texto: extrairMensagemErro(e) }]);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div>
      <div className="h-72 space-y-2 overflow-y-auto rounded-xl border border-line bg-card2 p-3" aria-live="polite">
        {mensagens.length === 0 && <p className="text-center text-sm text-muted">Digite “oi” para começar a conversa com o bot.</p>}
        {mensagens.map((m, i) => (
          <div key={i} className={`flex ${m.de === "cliente" ? "justify-end" : "justify-start"}`}>
            <p className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${m.de === "cliente" ? "bg-brand-600 text-onbrand" : "border border-line bg-card"}`}>
              {m.texto.replace(/\*/g, "")}
            </p>
          </div>
        ))}
        <div ref={fim} />
      </div>
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
        <input className="input" placeholder="Mensagem do cliente…" aria-label="Mensagem do cliente" value={texto} onChange={(e) => setTexto(e.target.value)} />
        <button className="btn-primary" disabled={enviando}>Enviar</button>
        <button type="button" className="btn-outline" onClick={() => setMensagens([])}>Limpar</button>
      </form>
      <p className="mt-2 text-xs text-muted">Atenção: pedidos feitos no simulador são reais e aparecem em “Solicitações” — recuse depois, se for só teste.</p>
    </div>
  );
}

function WhatsApp({ salao, recarregar }) {
  const [instancia, setInstancia] = useState(salao.whatsapp_instancia || "");
  const [msg, setMsg] = useState("");
  const [copiado, setCopiado] = useState(false);
  const webhook = `${URL_BASE_API}/webhooks/whatsapp/${salao.id}`;

  async function salvar(e) {
    e.preventDefault();
    try {
      await api.put(`/saloes/${salao.id}`, { whatsapp_instancia: instancia });
      setMsg("Salvo."); recarregar();
    } catch (err) {
      setMsg(extrairMensagemErro(err));
    }
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(webhook);
      setCopiado(true); setTimeout(() => setCopiado(false), 2000);
    } catch {
      // navegador sem permissão de área de transferência: a pessoa copia à mão
    }
  }

  return (
    <section className="card space-y-5">
      <div>
        <h2 className="titulo text-lg">Bot de WhatsApp</h2>
        <p className="text-sm text-muted">O cliente conversa pelo WhatsApp, escolhe procedimento, dia e horário, e o pedido chega em “Solicitações” — igual ao do site.</p>
      </div>

      <form onSubmit={salvar} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[220px] flex-1">
          <label className="rotulo" htmlFor="w-inst">Instância do WhatsApp deste salão (Evolution API)</label>
          <input id="w-inst" className="input" placeholder="Em branco = usa a instância padrão do servidor" value={instancia} onChange={(e) => setInstancia(e.target.value)} />
        </div>
        <button className="btn-outline">Salvar</button>
        {msg && <span role="status" className="pb-2 text-sm text-muted">{msg}</span>}
      </form>

      <div>
        <p className="rotulo">Endereço do webhook (cole no painel da Evolution API ou da Meta)</p>
        <div className="flex gap-2">
          <input readOnly className="input font-mono text-xs" value={webhook} onFocus={(e) => e.target.select()} aria-label="Endereço do webhook" />
          <button type="button" className="btn-outline" onClick={copiar}>{copiado ? "Copiado!" : "Copiar"}</button>
        </div>
        <p className="mt-1 text-xs text-muted">Se o servidor tiver WHATSAPP_WEBHOOK_TOKEN configurado, acrescente <code>?token=SEU_TOKEN</code> ao final.</p>
      </div>

      <div>
        <p className="rotulo">Simulador — teste a conversa sem usar o celular</p>
        <Simulador salaoId={salao.id} />
      </div>
    </section>
  );
}

export default function ConfigTab({ salao, recarregarSalao, ehDono }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <DadosDoSalao salao={salao} recarregar={recarregarSalao} />
        {ehDono && (
          <section className="card">
            <h2 className="titulo text-lg">Assinatura da plataforma</h2>
            <p className="mb-4 text-sm text-muted">Veja o status da cobrança mensal e regularize o pagamento.</p>
            <Link to="/assinatura" className="btn-outline">Gerenciar assinatura</Link>
          </section>
        )}
      </div>
      <WhatsApp salao={salao} recarregar={recarregarSalao} />
    </div>
  );
}
