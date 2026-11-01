// Funções pequenas de formatação usadas em várias telas.
//
// Atenção a datas: a API devolve horários SEM fuso ("2026-11-07T14:30:00"),
// que o JavaScript interpreta como horário local — exatamente o que queremos.
// Por isso nunca usamos toISOString() para "hoje" (ele converte para UTC e,
// à noite, devolveria o dia seguinte).

export const CATEGORIAS = [
  { id: "cabelo", nome: "Cabelo" },
  { id: "unhas", nome: "Unhas" },
  { id: "estetica", nome: "Estética" },
  { id: "barba", nome: "Barba" },
  { id: "outros", nome: "Outros" },
];

export const NOMES_CATEGORIA = { ...Object.fromEntries(CATEGORIAS.map((c) => [c.id, c.nome])), avaliacao: "Avaliação" };

export const DIAS_SEMANA_CURTO = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]; // 0 = segunda, como no backend

// Status de um agendamento -> texto e cor do selo.
export const STATUS = {
  pendente: { texto: "Aguardando confirmação", classe: "badge-warn" },
  confirmado: { texto: "Confirmado", classe: "badge-ok" },
  recusado: { texto: "Recusado", classe: "badge-bad" },
  cancelado: { texto: "Cancelado", classe: "badge-bad" },
  concluido: { texto: "Concluído", classe: "badge-info" },
};

export const ORIGENS = {
  web: "Site",
  whatsapp: "WhatsApp",
  manual: "Balcão",
  app: "Site",
};

export function paraISO(data) {
  const dois = (n) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}`;
}

export const hojeISO = () => paraISO(new Date());

// "2026-11-07" -> Date local (meio-dia, para escapar de problemas de horário de verão)
export function dataDeISO(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d, 12);
}

export function formatarHora(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

// Só a PRIMEIRA letra em maiúscula ("sexta, 07/11" -> "Sexta, 07/11").
// Não use a classe CSS "capitalize" para isso: ela põe maiúscula em TODAS as
// palavras ("Sexta, 07/11 Às 14:30").
export function primeiraMaiuscula(texto = "") {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function formatarDiaCurto(iso) {
  const texto = new Date(iso).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
  return primeiraMaiuscula(texto.replace(".", "")); // "seg., 02/11" -> "Seg, 02/11"
}

export function formatarDataHora(iso) {
  return `${formatarDiaCurto(iso)} às ${formatarHora(iso)}`;
}

export function formatarDiaLongo(isoData) {
  return primeiraMaiuscula(
    dataDeISO(isoData).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })
  );
}

export function formatarMesAno(ano, mes) {
  return primeiraMaiuscula(new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" }));
}

export function moeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function iniciais(nome = "") {
  return nome
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

// 5511999998888 -> (11) 99999-8888
export function formatarTelefone(telefone = "") {
  const d = telefone.replace(/\D/g, "").replace(/^55/, "");
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return telefone;
}

export function linkWhatsapp(telefone = "") {
  return `https://wa.me/${telefone.replace(/\D/g, "")}`;
}

// Agrupa procedimentos por categoria, na ordem de CATEGORIAS.
export function agruparPorCategoria(servicos) {
  return CATEGORIAS.map((categoria) => ({
    ...categoria,
    itens: servicos.filter((s) => !s.eh_avaliacao && s.categoria === categoria.id),
  })).filter((grupo) => grupo.itens.length > 0);
}
