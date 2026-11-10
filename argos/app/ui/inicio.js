"use strict";
// Eventos globais (clique, teclado, redimensionar) e a inicialização.

// --- eventos -----------------------------------------------------------

document.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-acao]");
  if (!el || el.disabled || el.tagName === "INPUT") return;
  // Botões dentro de uma linha clicável não expandem a linha
  if (el.dataset.acao === "abrir-projeto" && ev.target.closest("button, input, select")) return;
  ev.preventDefault();
  const f = ACOES[el.dataset.acao];
  ultimaAcao = Date.now();
  if (f) f(el.dataset, el.tagName === "BUTTON" ? el : null);
});

// Trocar de serviço no painel de logs, ou abrir um segundo log ao lado
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-log-alvo], [data-log-lado]");
  if (!b) return;
  if (b.dataset.logLado) abrirLogLado(b.dataset.logTipo, b.dataset.logLado, b.dataset.logNome);
  else abrirLogs(b.dataset.logTipo, b.dataset.logAlvo, b.dataset.logNome);
});

// Chaves (switch) disparam a ação ao mudar
document.addEventListener("change", async (ev) => {
  const el = ev.target;
  if (el.tagName === "INPUT" && el.dataset.acao && ACOES[el.dataset.acao]) ACOES[el.dataset.acao](el.dataset, null);
});

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); abrirPaleta(); return; }
  // Linhas que funcionam como botão (role="button") respondem a Enter/Espaço
  if ((e.key === "Enter" || e.key === " ") && e.target.matches?.('[role="button"][data-acao]')) { e.preventDefault(); e.target.click(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && !$("#gaveta").hidden) { e.preventDefault(); $("#log-busca").focus(); return; }
  if ($("#paleta")) return;
  if (e.key === "Escape" && !$("#gaveta").hidden && $("#modal").hidden) ACOES["log-fechar"]();
  else if (e.key === "Escape" && aba === "projetos" && projetoAberto && $("#modal").hidden && !e.target.matches("input, textarea, select")) ACOES["fechar-projeto"]();
  if (e.key === "F5" || ((e.ctrlKey || e.metaKey) && e.key === "r")) { e.preventDefault(); ciclo(); }
  if ((e.ctrlKey || e.metaKey) && e.key === "w") { e.preventDefault(); api.esconder(); }
  if ((e.ctrlKey || e.metaKey) && /^[1-5]$/.test(e.key)) { e.preventDefault(); trocarAba(ABAS[+e.key - 1].id); }
});

// Duplo clique na barra de título maximiza, como no Mac
$("#barra").addEventListener("dblclick", (e) => { if (e.target === e.currentTarget) api.maximizar(); });
document.querySelector(".lateral-topo").addEventListener("dblclick", (e) => { if (e.target === e.currentTarget) api.maximizar(); });

// Semáforos ficam cinza quando a janela perde o foco
window.addEventListener("blur", () => document.body.classList.add("desfocada"));
window.addEventListener("focus", () => { document.body.classList.remove("desfocada"); if (api) api.em_foco(); });

// Busca e filtro do log
$("#log-busca").addEventListener("input", () => renderLog(true));
$("#log-busca").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); e.target.value = ""; renderLog(); } });
$("#log-erros").addEventListener("change", () => { renderLog(); $("#log").scrollTop = $("#log").scrollHeight; });

// Redimensionar pelas alças (a janela não tem a borda do Windows)
document.querySelectorAll("[data-redim]").forEach((alca) => {
  alca.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    alca.setPointerCapture(e.pointerId);
    const dir = alca.dataset.redim;
    const x0 = e.screenX, y0 = e.screenY, w0 = window.outerWidth, h0 = window.outerHeight;
    let pendente = null, enviando = false;
    const enviar = async () => {
      if (enviando || !pendente) return;
      enviando = true;
      const [w, h] = pendente;
      pendente = null;
      try { await api.redimensionar(w, h); } finally { enviando = false; if (pendente) enviar(); }
    };
    const mover = (ev) => {
      const w = dir.includes("e") ? w0 + ev.screenX - x0 : w0;
      const h = dir.includes("s") ? h0 + ev.screenY - y0 : h0;
      pendente = [Math.round(w), Math.round(h)];
      enviar();
    };
    const soltar = () => { alca.removeEventListener("pointermove", mover); alca.removeEventListener("pointerup", soltar); };
    alca.addEventListener("pointermove", mover);
    alca.addEventListener("pointerup", soltar);
  });
});

// --- início ------------------------------------------------------------

montarMenu();
let iniciado = false;
async function iniciar(ponte) {
  if (iniciado) return;
  iniciado = true;
  api = ponte;
  try { CFG = (await api.config()) || {}; } catch { CFG = {}; }
  ciclo();
}

window.addEventListener("pywebviewready", () => iniciar(window.pywebview.api));
setTimeout(() => {
  if (iniciado) return;
  if (window.pywebview && window.pywebview.api) return iniciar(window.pywebview.api);
  if (window.ARGOS_MOCK) return iniciar(criarMock(window.ARGOS_MOCK));
  $("#p-rodando").innerHTML = vazio("rodando", "Sem conexão com o Argos", "Abra pelo app (argos app).");
}, 1200);
