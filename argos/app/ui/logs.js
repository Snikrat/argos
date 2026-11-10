"use strict";
// Painel de logs: cores ANSI, busca, troca de serviço e log ao lado.

// --- logs ----------------------------------------------------------------

const ANSI_CORES = ["#4b5563", "#ff6b6b", "#5ee09a", "#ffcc66", "#6cb6ff", "#d49cff", "#5fd7d7", "#d4d4d8",
  "#71717a", "#ff8787", "#7cf0b5", "#ffd98a", "#93c8ff", "#e0b8ff", "#8af0f0", "#ffffff"];

function cor256(n) {
  if (n < 16) return ANSI_CORES[n];
  if (n >= 232) { const v = 8 + (n - 232) * 10; return `rgb(${v},${v},${v})`; }
  n -= 16;
  const c = (x) => (x ? 55 + x * 40 : 0);
  return `rgb(${c(Math.floor(n / 36))},${c(Math.floor(n / 6) % 6)},${c(n % 6)})`;
}

function ansiParaHtml(texto) {
  // Barras de progresso reescrevem a linha com \r: fica só a última versão
  texto = texto.split("\n").map((l) => { const i = l.lastIndexOf("\r", l.length - 2); return i >= 0 ? l.slice(i + 1) : l; }).join("\n");
  let st = {}, saida = "", aberto = false;
  const partes = texto.split(/\x1b\[([0-9;?]*)([A-Za-z])/);
  for (let i = 0; i < partes.length; i++) {
    if (i % 3 === 0) { saida += esc(partes[i]); continue; }
    const cod = partes[i], tipo = partes[i + 1];
    i++;
    if (tipo !== "m") continue;
    const ns = cod === "" ? [0] : cod.split(";").map(Number);
    for (let k = 0; k < ns.length; k++) {
      const n = ns[k];
      if (n === 0) st = {};
      else if (n === 1) st.b = true;
      else if (n === 2) st.d = true;
      else if (n === 3) st.it = true;
      else if (n === 4) st.u = true;
      else if (n === 22) { st.b = false; st.d = false; }
      else if (n >= 30 && n <= 37) st.c = ANSI_CORES[n - 30];
      else if (n >= 90 && n <= 97) st.c = ANSI_CORES[n - 82];
      else if (n === 39) st.c = null;
      else if (n === 38 && ns[k + 1] === 5) { st.c = cor256(ns[k + 2]); k += 2; }
      else if (n === 38 && ns[k + 1] === 2) { st.c = `rgb(${ns[k + 2]},${ns[k + 3]},${ns[k + 4]})`; k += 4; }
      else if (n === 48 && (ns[k + 1] === 5 || ns[k + 1] === 2)) k += ns[k + 1] === 5 ? 2 : 4;
    }
    if (aberto) { saida += "</span>"; aberto = false; }
    const css = [st.c && `color:${st.c}`, st.b && "font-weight:700", st.d && "opacity:.55", st.it && "font-style:italic", st.u && "text-decoration:underline"].filter(Boolean).join(";");
    if (css) { saida += `<span style="${css}">`; aberto = true; }
  }
  if (aberto) saida += "</span>";
  return saida.replace(/\x1b[\]()][^\x07\x1b]*(\x07|\x1b\\)?/g, "");
}

let logAtual = null;
const RE_ERRO = /\b(error|erro|exception|traceback|failed|falhou|fatal|panic|unhandled|errno|err!)\b/i;
const semAnsi = (s) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]|\x1b[\]()][^\x07\x1b]*(\x07|\x1b\\)?/g, "");
const MAX_LINHAS_LOG = 6000;

// Outros serviços do mesmo projeto (processos com log e containers): para trocar ou ver ao lado
function servicosDoLog(tipo, alvo) {
  if (!E || tipo === "arquivo") return [];
  const dono = tipo === "processo" ? E.unidades.find((u) => u.gerenciado === alvo) : E.docker.containers.find((c) => c.id === alvo);
  const projeto = dono && dono.projeto;
  if (!projeto) return [];
  return [
    ...E.unidades.filter((u) => u.gerenciado && u.projeto === projeto).map((u) => ({ tipo: "processo", alvo: u.gerenciado, nome: u.nome })),
    ...E.docker.containers.filter((c) => c.estado === "running" && c.projeto === projeto).map((c) => ({ tipo: "container", alvo: c.id, nome: c.nome })),
  ];
}

let logLado = null; // segundo log, mostrado ao lado do principal
function renderServicosLog() {
  const el = $("#log-servicos");
  const lista = logAtual ? servicosDoLog(logAtual.tipo, logAtual.alvo) : [];
  el.hidden = lista.length < 2;
  if (el.hidden) { fecharLogLado(); return; }
  el.innerHTML = lista.map((s) => {
    const ativo = s.alvo === logAtual.alvo, lado = logLado && s.alvo === logLado.alvo;
    return `<span class="servico-log ${ativo ? "ativo" : ""} ${lado ? "lado" : ""}">
      <button data-log-alvo="${esc(s.alvo)}" data-log-tipo="${esc(s.tipo)}" data-log-nome="${esc(s.nome)}" title="Ver este log">${esc(s.nome)}</button>
      ${ativo ? "" : `<button class="dividir" data-log-lado="${esc(s.alvo)}" data-log-tipo="${esc(s.tipo)}" data-log-nome="${esc(s.nome)}"
        title="${lado ? "Fechar o painel ao lado" : "Ver ao lado do log atual"}">${IC.colunas}</button>`}</span>`;
  }).join("");
}

function fecharLogLado() {
  logLado = null;
  $("#log2-caixa").hidden = true;
  $("#gaveta").classList.remove("dividido");
}

function abrirLogLado(tipo, alvo, nome) {
  if (logLado && logLado.alvo === alvo) { fecharLogLado(); renderServicosLog(); return; }
  logLado = { tipo, alvo, nome, fim: -1, texto: "" };
  $("#log2-titulo").textContent = nome;
  $("#log2").innerHTML = "";
  $("#log2-caixa").hidden = false;
  $("#gaveta").classList.add("dividido");
  renderServicosLog();
  puxarLogLado();
}

async function puxarLogLado() {
  const atual = logLado;
  if (!atual || $("#gaveta").hidden) return;
  try {
    const r = await api.logs(atual.tipo, atual.alvo, atual.fim);
    if (atual !== logLado) return;
    const pre = $("#log2");
    const noFim = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    const mudou = r.substituir ? r.texto !== atual.texto : !!r.texto;
    if (r.substituir) atual.texto = r.texto;
    else if (r.texto) atual.texto = (atual.texto + r.texto).slice(-1_000_000);
    atual.fim = r.fim;
    if (mudou) {
      pre.innerHTML = atual.texto.split("\n").slice(-3000).map(ansiParaHtml).join("\n");
      if (noFim) pre.scrollTop = pre.scrollHeight;
    }
  } catch (e) { console.error(e); }
  setTimeout(puxarLogLado, atual.tipo === "container" ? 3000 : 1000);
}

function abrirLogs(tipo, alvo, nome) {
  if (logLado && logLado.alvo === alvo) fecharLogLado();
  logAtual = { tipo, alvo, nome, fim: -1, texto: "" };
  $("#log-titulo").textContent = nome;
  $("#log-sub").textContent = tipo === "container" ? "container · últimas 500 linhas" : "carregando…";
  $("#log").innerHTML = "";
  $("#log-busca").value = "";
  $("#log-erros").checked = false;
  $("#gaveta").hidden = false;
  renderServicosLog();
  puxarLogs();
}

// Desenha o log aplicando o filtro de erros e destacando a busca
function renderLog(rolarParaBusca = false) {
  if (!logAtual) return;
  const pre = $("#log");
  const busca = $("#log-busca").value.trim();
  const soErros = $("#log-erros").checked;
  const re = busca ? new RegExp(esc(busca).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi") : null;
  let achados = 0;
  const html = [];
  for (const linha of logAtual.texto.split("\n").slice(-MAX_LINHAS_LOG)) {
    const pura = semAnsi(linha);
    const erro = RE_ERRO.test(pura);
    if (soErros && !erro) continue;
    let h = ansiParaHtml(linha);
    if (re) h = h.replace(/(^|>)([^<]+)/g, (_, a, t) => a + t.replace(re, (m) => (achados++, `<mark>${m}</mark>`)));
    html.push(erro ? `<span class="linha-erro">${h}</span>` : h);
  }
  pre.innerHTML = html.join("\n") || (soErros ? '<span style="opacity:.5">Nenhuma linha com erro.</span>' : "");
  $("#log-achados").textContent = busca ? (achados ? `${achados}` : "0") : "";
  if (rolarParaBusca && achados) pre.querySelector("mark")?.scrollIntoView({ block: "center" });
}

async function puxarLogs() {
  const atual = logAtual;
  if (!atual || $("#gaveta").hidden) return;
  try {
    const r = await api.logs(atual.tipo, atual.alvo, atual.fim);
    if (atual !== logAtual) return;
    const pre = $("#log");
    const noFim = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    if (r.erro) $("#log-sub").textContent = r.erro;
    else if (atual.tipo !== "container") $("#log-sub").textContent = `${r.vivo ? "rodando" : "parado"}${r.arquivo ? " · " + r.arquivo : ""}`;
    const mudou = r.substituir ? r.texto !== atual.texto : !!r.texto;
    if (r.substituir) atual.texto = r.texto;
    else if (r.texto) {
      atual.texto += r.texto;
      if (atual.texto.length > 2_000_000) atual.texto = atual.texto.slice(-1_000_000);
    }
    if (mudou) renderLog();
    atual.fim = r.fim;
    const buscando = $("#log-busca").value.trim();
    if (mudou && !buscando && ($("#log-seguir").checked || noFim)) pre.scrollTop = pre.scrollHeight;
  } catch (e) { console.error(e); }
  setTimeout(puxarLogs, atual.tipo === "container" ? 3000 : 1000);
}
