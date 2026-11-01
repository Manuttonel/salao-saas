// Página de gestão da assinatura da plataforma (somente o dono).
//
// Mostra o status (pendente/aprovada/atrasada/cancelada) e permite iniciar
// uma assinatura: o backend cria a "preapproval" no Mercado Pago e devolve a
// URL de checkout, para onde o dono é redirecionado. O status real só é
// confirmado depois, quando o Mercado Pago chama nosso webhook
// (backend/app/routes/webhook_routes.py).

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";
import { moeda } from "../services/formatar";

const RESUMO_STATUS = {
  pendente: { texto: "Pagamento pendente de confirmação.", classe: "badge-warn" },
  aprovada: { texto: "Assinatura em dia.", classe: "badge-ok" },
  atrasada: { texto: "Assinatura atrasada — painel bloqueado.", classe: "badge-bad" },
  cancelada: { texto: "Assinatura cancelada.", classe: "badge-bad" },
};

export default function Assinatura() {
  const usuario = obterUsuarioLogado();
  const salaoId = usuario?.saloes?.[0];

  const [assinatura, setAssinatura] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [processando, setProcessando] = useState(false);

  useEffect(() => {
    if (!salaoId) { setCarregando(false); return; }
    api.get(`/pagamentos/assinaturas/${salaoId}`)
      .then(({ data }) => setAssinatura(data))
      .catch(() => setAssinatura(null)) // 404 é esperado quando ainda não existe assinatura
      .finally(() => setCarregando(false));
  }, [salaoId]);

  async function iniciarAssinatura() {
    setErro(""); setProcessando(true);
    try {
      const { data } = await api.post(`/pagamentos/assinaturas/${salaoId}`);
      // O dono insere o cartão no checkout do Mercado Pago.
      window.location.href = data.checkout_url;
    } catch (e) {
      setErro(extrairMensagemErro(e));
      setProcessando(false);
    }
  }

  async function cancelarAssinatura() {
    if (!confirm("Cancelar a assinatura da plataforma? O painel do salão ficará bloqueado.")) return;
    setProcessando(true);
    try {
      const { data } = await api.post(`/pagamentos/assinaturas/${salaoId}/cancelar`);
      setAssinatura(data);
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  return (
    <div>
      <Navbar usuario={usuario} titulo="Assinatura" />
      <main className="mx-auto max-w-lg px-4 py-8">
        <Link to="/dashboard" className="mb-4 inline-block text-sm text-brand-600 hover:underline">← Voltar ao painel</Link>
        <div className="card">
          <h2 className="titulo mb-4 text-lg">Assinatura da plataforma</h2>

          {!salaoId ? (
            <p className="text-sm text-muted">Cadastre seu salão primeiro, no painel principal.</p>
          ) : carregando ? (
            <p className="text-sm text-muted">Carregando…</p>
          ) : assinatura ? (
            <div className="space-y-3">
              <span className={`${RESUMO_STATUS[assinatura.status]?.classe} !block !rounded-lg !px-4 !py-3 text-sm`}>
                {RESUMO_STATUS[assinatura.status]?.texto}
              </span>
              <p className="text-sm text-muted">Valor mensal: {moeda(assinatura.valor_mensal)}</p>
              {assinatura.data_proximo_vencimento && (
                <p className="text-sm text-muted">Próximo vencimento: {new Date(assinatura.data_proximo_vencimento).toLocaleDateString("pt-BR")}</p>
              )}
              {!["aprovada", "cancelada"].includes(assinatura.status) && (
                <button disabled={processando} onClick={iniciarAssinatura} className="btn-primary">{processando ? "Redirecionando…" : "Ir para pagamento"}</button>
              )}
              {assinatura.status === "aprovada" && (
                <button disabled={processando} onClick={cancelarAssinatura} className="btn-danger">Cancelar assinatura</button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted">Seu salão ainda não tem uma assinatura ativa.</p>
              <button disabled={processando} onClick={iniciarAssinatura} className="btn-primary">{processando ? "Redirecionando…" : "Assinar agora"}</button>
            </div>
          )}

          {erro && <p role="alert" className="mt-3 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
        </div>
      </main>
    </div>
  );
}
