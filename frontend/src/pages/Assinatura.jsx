// Página de gestão da assinatura da plataforma (dono do salão).
//
// Mostra o status atual (pendente/aprovada/atrasada/cancelada) e
// permite iniciar uma nova assinatura — o backend cria a "preapproval"
// no Mercado Pago e devolve uma URL de checkout, para onde o dono é
// redirecionado para inserir o cartão. O status real só é confirmado
// depois, quando o Mercado Pago chamar nosso webhook
// (backend/app/routes/webhook_routes.py).

import { useEffect, useState } from "react";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";

const RESUMO_STATUS = {
  pendente: { texto: "Pagamento pendente de confirmação.", cor: "text-yellow-700 bg-yellow-50 border-yellow-200" },
  aprovada: { texto: "Assinatura em dia.", cor: "text-green-700 bg-green-50 border-green-200" },
  atrasada: { texto: "Assinatura atrasada — painel bloqueado.", cor: "text-red-700 bg-red-50 border-red-200" },
  cancelada: { texto: "Assinatura cancelada.", cor: "text-gray-700 bg-gray-50 border-gray-200" },
};

export default function Assinatura() {
  const usuario = obterUsuarioLogado();
  const salaoId = usuario?.saloes?.[0];

  const [assinatura, setAssinatura] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [processando, setProcessando] = useState(false);

  useEffect(() => {
    if (salaoId) carregarAssinatura();
    else setCarregando(false);
  }, [salaoId]);

  async function carregarAssinatura() {
    setCarregando(true);
    try {
      const { data } = await api.get(`/pagamentos/assinaturas/${salaoId}`);
      setAssinatura(data);
    } catch (e) {
      // 404 é esperado quando ainda não existe assinatura
      setAssinatura(null);
    } finally {
      setCarregando(false);
    }
  }

  async function iniciarAssinatura() {
    setErro("");
    setProcessando(true);
    try {
      const { data } = await api.post(`/pagamentos/assinaturas/${salaoId}`);
      // Redireciona o dono para o checkout do Mercado Pago, onde ele
      // insere o cartão e autoriza a cobrança recorrente.
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
      await api.post(`/pagamentos/assinaturas/${salaoId}/cancelar`);
      await carregarAssinatura();
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  if (!salaoId) {
    return (
      <div>
        <Navbar usuario={usuario} />
        <div className="max-w-lg mx-auto px-4 py-8">
          <p className="text-sm text-gray-500">Cadastre seu salão primeiro, no painel principal.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Navbar usuario={usuario} />
      <div className="max-w-lg mx-auto px-4 py-8">
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">Assinatura da plataforma</h2>

          {carregando ? (
            <p className="text-sm text-gray-500">Carregando...</p>
          ) : assinatura ? (
            <div className="space-y-3">
              <div className={`text-sm rounded-md border px-4 py-3 ${RESUMO_STATUS[assinatura.status]?.cor}`}>
                {RESUMO_STATUS[assinatura.status]?.texto}
              </div>
              <p className="text-sm text-gray-600">Valor mensal: R$ {assinatura.valor_mensal.toFixed(2)}</p>
              {assinatura.data_proximo_vencimento && (
                <p className="text-sm text-gray-600">
                  Próximo vencimento: {new Date(assinatura.data_proximo_vencimento).toLocaleDateString("pt-BR")}
                </p>
              )}

              {assinatura.status !== "aprovada" && assinatura.status !== "cancelada" && (
                <button disabled={processando} onClick={iniciarAssinatura}
                  className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-md py-2 px-4 text-sm">
                  {processando ? "Redirecionando..." : "Ir para pagamento"}
                </button>
              )}
              {assinatura.status === "aprovada" && (
                <button disabled={processando} onClick={cancelarAssinatura}
                  className="border border-red-300 text-red-700 hover:bg-red-50 rounded-md py-2 px-4 text-sm">
                  Cancelar assinatura
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-500">Seu salão ainda não tem uma assinatura ativa.</p>
              <button disabled={processando} onClick={iniciarAssinatura}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-md py-2 px-4 text-sm">
                {processando ? "Redirecionando..." : "Assinar agora"}
              </button>
            </div>
          )}

          {erro && <p className="text-sm text-red-600 mt-3">{erro}</p>}
        </div>
      </div>
    </div>
  );
}
