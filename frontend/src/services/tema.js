// Lógica dos temas visuais (sem React): quais existem, como salvar a escolha
// e como aplicá-la na página.
//
// O tema ativo é só um atributo no <html>: <html data-tema="glow">. As
// paletas de cada um estão em src/styles/index.css. No tema "unisex" a
// pessoa também escolhe uma COR; aqui geramos os tons dela (claro/escuro)
// e gravamos como variáveis CSS que sobrescrevem as do tema.

export const TEMAS = [
  { id: "unisex", nome: "Unisex", descricao: "Neutro — você escolhe a cor", amostra: ["#4f46e5", "#f1f5f9"] },
  { id: "glow", nome: "Glow", descricao: "Rosé e dourado, sofisticado", amostra: ["#be185d", "#c5a059"] },
  { id: "dark", nome: "Dark", descricao: "Preto, vermelho e azul-marinho", amostra: ["#dc2626", "#1e3a8a"] },
];

export const COR_PADRAO = "#4f46e5";
export const CORES_SUGERIDAS = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#111827"];

const CHAVE_LOCAL = "salao_tema";
const VARIAVEIS_DA_COR = ["--brand-50", "--brand-100", "--brand-500", "--brand-600", "--brand-700", "--accent", "--accent-soft", "--onbrand"];

// ---- Preferência salva no navegador (vale até a pessoa entrar na conta) ----

export function carregarPreferencias() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_LOCAL));
    if (salvo && TEMAS.some((t) => t.id === salvo.tema)) {
      return { tema: salvo.tema, cor: salvo.cor || COR_PADRAO };
    }
  } catch {
    // localStorage indisponível ou JSON quebrado: cai no padrão
  }
  return { tema: "unisex", cor: COR_PADRAO };
}

export function salvarPreferenciasLocal(preferencias) {
  try {
    localStorage.setItem(CHAVE_LOCAL, JSON.stringify(preferencias));
  } catch {
    // sem problema: o tema só não será lembrado na próxima visita
  }
}

// ---- Aplicação na página ---------------------------------------------------

export function aplicarTema({ tema, cor }) {
  const raiz = document.documentElement;
  raiz.setAttribute("data-tema", tema);

  // Limpa qualquer cor personalizada antes de decidir se aplica uma nova.
  VARIAVEIS_DA_COR.forEach((v) => raiz.style.removeProperty(v));

  if (tema === "unisex" && cor) {
    const paleta = gerarPaleta(cor);
    Object.entries(paleta).forEach(([variavel, valor]) => raiz.style.setProperty(variavel, valor));
  }
}

// ---- Cores -----------------------------------------------------------------

function hexParaRgb(hex) {
  const limpo = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(limpo.slice(i, i + 2), 16));
}

// Mistura `rgb` com `alvo` (ex.: branco). t=0 mantém a cor, t=1 vira o alvo.
function misturar(rgb, alvo, t) {
  return rgb.map((canal, i) => Math.round(canal + (alvo[i] - canal) * t));
}

function luminancia([r, g, b]) {
  const [R, G, B] = [r, g, b].map((c) => {
    const x = c / 255;
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

const texto = (rgb) => rgb.join(" ");

// A cor escolhida vira o tom "600" (botões); os outros tons são derivados dela.
export function gerarPaleta(hex) {
  const base = hexParaRgb(hex);
  const branco = [255, 255, 255];
  const preto = [0, 0, 0];
  // Se a cor for muito clara (ex.: amarelo), o texto sobre ela precisa ser escuro.
  const textoSobreCor = luminancia(base) > 0.55 ? "17 24 39" : "255 255 255";

  return {
    "--brand-50": texto(misturar(base, branco, 0.92)),
    "--brand-100": texto(misturar(base, branco, 0.84)),
    "--brand-500": texto(misturar(base, branco, 0.14)),
    "--brand-600": texto(base),
    "--brand-700": texto(misturar(base, preto, 0.2)),
    "--accent": texto(base),
    "--accent-soft": texto(luminancia(base) > 0.55 ? misturar(base, preto, 0.35) : base),
    "--onbrand": textoSobreCor,
  };
}
