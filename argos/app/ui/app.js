"use strict";

// --- utilitários -------------------------------------------------------

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const attr = (o) => Object.entries(o).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
const agora = () => Date.now() / 1000;

function hora(ts) {
  const d = new Date(ts * 1000), hoje = new Date();
  const h = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === hoje.toDateString() ? h : `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${h}`;
}
function duracao(seg) {
  seg = Math.max(0, seg);
  const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}min` : m ? `${m} min` : "agora";
}
function ram(mb) {
  if (mb == null) return "–";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1).replace(".", ",")} GB` : `${mb} MB`;
}
function bytes(n) {
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0).replace(".", ",")} ${u[i]}`;
}
const plural = (n, s, p) => `${n} ${n === 1 ? s : p}`;

// Ícones de traço fino, no espírito dos SF Symbols
const IC = (() => {
  const s = (d, extra = "") => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;
  return {
    rodando: s('<path d="M13 2 4.5 13.5H12L11 22l8.5-11.5H12z"/>'),
    projetos: s('<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>'),
    docker: s('<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>'),
    ferramentas: s('<path d="M14.5 6.5a4 4 0 0 0-5.3 5.3L3.5 17.5a1.5 1.5 0 0 0 2.1 2.1l5.7-5.7a4 4 0 0 0 5.3-5.3l-2.5 2.5-2.1-.6-.6-2.1z"/>'),
    hoje: s('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
    config: s('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>'),
    logs: s('<path d="M5 6h14M5 10h14M5 14h9M5 18h6"/>'),
    reiniciar: s('<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>'),
    parar: s('<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>'),
    play: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.8v14.4a1 1 0 0 0 1.5.9l11.4-7.2a1 1 0 0 0 0-1.8L8.5 3.9A1 1 0 0 0 7 4.8z"/></svg>`,
    pasta: s('<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>'),
    codigo: s('<path d="m8 7-5 5 5 5M16 7l5 5-5 5"/>'),
    terminal: s('<rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15H17"/>'),
    jogo: s('<path d="M6.5 8h11a4 4 0 0 1 3.9 4.8l-.8 3.6a2.3 2.3 0 0 1-4 1l-1.6-2.4h-6l-1.6 2.4a2.3 2.3 0 0 1-4-1l-.8-3.6A4 4 0 0 1 6.5 8z"/><path d="M8 11v3M6.5 12.5h3"/><circle cx="16" cy="11.5" r=".6" fill="currentColor"/><circle cx="17.5" cy="13.5" r=".6" fill="currentColor"/>'),
    lixo: s('<path d="M4 7h16M10 11v6M14 11v6M5.5 7l1 12a1.5 1.5 0 0 0 1.5 1.4h8a1.5 1.5 0 0 0 1.5-1.4l1-12M9 7V4.5h6V7"/>'),
    fechar: s('<path d="m6 6 12 12M18 6 6 18"/>'),
    copiar: s('<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5v-3a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 5.5V14A1.5 1.5 0 0 0 6 15.5h2.5"/>'),
    busca: s('<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.3-4.3"/>'),
    chevron: s('<path d="m9 6 6 6-6 6"/>'),
    atualizar: s('<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>'),
    ok: s('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12 2.5 2.5 4.5-5"/>'),
    celular: s('<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>'),
    auto: s('<path d="M4.5 12a7.5 7.5 0 0 1 12.8-5.3L19.5 9"/><path d="M19.5 4.5V9H15"/><path d="M19.5 12a7.5 7.5 0 0 1-12.8 5.3L4.5 15"/><path d="M4.5 19.5V15H9"/>'),
    filtro: s('<path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/>'),
    retomar: s('<path d="M4 12a8 8 0 1 0 2.3-5.7"/><path d="M4 4v5h5"/><path d="m10.5 9 4.5 3-4.5 3z" fill="currentColor"/>'),
    mundo: s('<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5S9.5 6.1 12 3.5z"/>'),
    chave: s('<circle cx="8" cy="15" r="4"/><path d="m11 12 8.5-8.5M16 7l2.5 2.5M18.5 4.5 21 7"/>'),
    teste: s('<path d="M9 3.5h6M10 3.5v6L5 19a1.5 1.5 0 0 0 1.3 2h11.4A1.5 1.5 0 0 0 19 19l-5-9.5v-6"/><path d="M7.5 14.5h9"/>'),
    fixar: s('<path d="M9 4h6l-1 5 3 3v2H7v-2l3-3z"/><path d="M12 14v6"/>'),
    fixado: `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M9 4h6l-1 5 3 3v2H7v-2l3-3z"/><path d="M12 14v6" fill="none" stroke-linecap="round"/></svg>`,
    git: s('<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 8v8M18 10c0 4-6 3-11.2 6.6"/>'),
  };
})();

// --- ponte com o Python --------------------------------------------------

let api = null;

// Sem pywebview (ex: index.html aberto no navegador) usa window.ARGOS_MOCK, se
// existir. Nenhuma ação real é executada nesse modo.
function criarMock(dados) {
  const ok = (msg) => async () => ({ ok: true, msg: `(exemplo) ${msg}` });
  return new Proxy({}, {
    get: (_, m) => ({
      estado: async () => ({ estado: dados.estado, saude: dados.saude || {}, eventos: [], ultimo_evento: 0 }),
      celular: async (p) => ({ ok: true, url: `http://192.168.0.107:${p}`, so_local: p === 5173, dica: "rode com --host, ex: npm run dev -- --host",
        svg: '<svg viewBox="0 0 29 29" width="174" height="174"><rect width="29" height="29" fill="#fff"/><path d="M2 2h7v7H2zM20 2h7v7h-7zM2 20h7v7H2zM12 12h5v5h-5z" fill="#000"/></svg>' }),
      projetos: async () => dados.projetos || [],
      historico: async () => dados.historico || [],
      config: async () => dados.config || {},
      dependencias: async () => [{ nome: "node_modules", caminho: "x\\node_modules", bytes: 412000000 }],
      docker_disco: async () => [{ tipo: "Imagens", total: 12, ativos: 2, tamanho: "8.4GB", recuperavel: "6.1GB (72%)" }],
      logs: async (t, a, desde) => desde > 0 ? { texto: "", fim: desde, vivo: true } :
        { texto: "\x1b[2m=== argos: npm run dev ===\x1b[0m\n\n  \x1b[32m\x1b[1mVITE\x1b[0m \x1b[32mv5.4.2\x1b[0m  ready in \x1b[1m312\x1b[0m ms\n\n  \x1b[32m➜\x1b[0m  \x1b[1mLocal\x1b[0m:   \x1b[36mhttp://localhost:\x1b[1m5173\x1b[0m\x1b[36m/\x1b[0m\n", fim: 200, vivo: true },
      maximizar: async () => false,
      git_branches: async () => ({ atual: "main", locais: ["main", "feature/login"] }),
      ambiente: async () => [{ sub: "", pasta: "x", arquivos: [{ nome: ".env", caminho: "x\\.env", chaves: 4 }],
        exemplo: { nome: ".env.example" }, faltando: ["STRIPE_KEY", "SMTP_HOST"], sem_env: false },
        { sub: "backend", pasta: "x\\backend", arquivos: [], exemplo: { nome: ".env.example" }, faltando: ["DATABASE_URL"], sem_env: true }],
      testes: async () => ({ lista: [{ cmd: "npm test", sub: "", chave: ".|npm test" }, { cmd: "uv run pytest -q", sub: "backend", chave: "backend|uv run pytest -q" }],
        resultados: { ".|npm test": { ok: true, resumo: "Tests  24 passed (24)", quando: Date.now() / 1000 - 3600, log: "x" },
          "backend|uv run pytest -q": { ok: false, resumo: "2 failed, 31 passed in 1.8s", quando: Date.now() / 1000 - 600, log: "x" } } }),
    }[m] || ok(m)),
  });
}

// --- estado ----------------------------------------------------------

let E = null;          // estado vindo do Python
let S = {};            // saúde das portas
let CFG = {};
let aba = "rodando";
let projetosCache = null;
let filtroProjetos = "";
let projetoAberto = null; // nome do projeto com a página aberta
let depsCache = {};
let discoCache;        // undefined = não analisado, null = analisando
let timer = null;
let ultimoEvento = -1; // -1 = ainda não sabe qual foi o último aviso

const ABAS = [
  { id: "rodando", rot: "Rodando" },
  { id: "projetos", rot: "Projetos" },
  { id: "docker", rot: "Docker" },
  { id: "ferramentas", rot: "Ferramentas" },
  { id: "hoje", rot: "Hoje" },
];

function montarMenu() {
  $("#menu").innerHTML = ABAS.map((a) => `
    <button ${attr({ acao: "aba", aba: a.id })} class="${a.id === aba ? "ativo" : ""}">
      <span class="ic">${IC[a.id]}</span><span class="rot">${a.rot}</span><span class="cont" id="cont-${a.id}"></span>
    </button>`).join("");
  $("#btn-config").innerHTML = IC.config;
  $("#ic-busca-log").innerHTML = IC.busca;
  $("#btn-copiar").innerHTML = IC.copiar;
  $("#btn-pasta-logs").innerHTML = IC.pasta;
  $("#btn-fechar-log").innerHTML = IC.fechar;
}

async function ciclo() {
  clearTimeout(timer);
  try {
    const r = await api.estado(ultimoEvento);
    if (r && r.estado) {
      E = r.estado;
      S = r.saude || {};
      render();
    }
    if (r) {
      if (ultimoEvento >= 0) (r.eventos || []).forEach(avisarEvento);
      ultimoEvento = r.ultimo_evento ?? ultimoEvento;
    }
  } catch (e) {
    console.error(e);
  }
  timer = setTimeout(ciclo, Math.max(1, CFG.intervalo || 3) * 1000);
}

function render() {
  renderLateral();
  renderBarra();
  if (aba === "rodando") renderRodando();
  if (aba === "docker") renderDocker();
  if (aba === "ferramentas") renderFerramentas();
  if (aba === "projetos") atualizarProjetosRodando();
}

function renderLateral() {
  const r = E.resumo;
  const n = r.processos + r.containers;
  const cr = $("#cont-rodando");
  cr.textContent = r.orfaos ? `${r.orfaos} órfão${r.orfaos > 1 ? "s" : ""}` : n || "";
  cr.classList.toggle("alerta", !!r.orfaos);
  $("#cont-docker").textContent = r.containers || "";
  const cf = $("#cont-ferramentas");
  cf.textContent = r.ferramentas_orfas ? `${r.ferramentas_orfas} vazada${r.ferramentas_orfas > 1 ? "s" : ""}` : "";
  cf.classList.toggle("alerta", !!r.ferramentas_orfas);

  const dk = E.docker;
  let txt;
  if (!dk.instalado) txt = "Docker não instalado";
  else if (dk.ligado) txt = `Docker <b>ligado</b>${dk.vmmem_mb ? `<br>WSL usando <b>${ram(dk.vmmem_mb)}</b>` : ""}`;
  else txt = `Docker desligado${dk.vmmem_mb ? `<br>WSL ainda usa <b>${ram(dk.vmmem_mb)}</b>` : ""}`;
  if (E.atualizacao) txt = `<button class="link-atualizar" data-acao="procurar-atualizacao">Atualizar para ${esc(E.atualizacao.versao)}</button><br>` + txt;
  $("#estado-docker").innerHTML = txt;
}

function renderBarra() {
  const r = E.resumo;
  const titulos = { rodando: "Rodando", projetos: "Projetos", docker: "Docker", ferramentas: "Ferramentas", hoje: "Hoje" };
  $("#titulo").textContent = titulos[aba];
  let sub = "";
  if (aba === "rodando") {
    const partes = [plural(r.processos, "processo", "processos"), plural(r.containers, "container", "containers"), plural(r.portas, "porta", "portas")];
    sub = partes.join(" · ");
  } else if (aba === "projetos" && projetosCache) sub = plural(projetosCache.length, "projeto", "projetos");
  else if (aba === "ferramentas") sub = `${ram(E.ferramentas.reduce((t, f) => t + f.ram_mb, 0))} no total`;
  $("#subtitulo").textContent = sub;

  const acoes = $("#barra-acoes");
  const chave = aba + (aba === "projetos" ? "" : "");
  if (acoes.dataset.aba === chave) return;
  acoes.dataset.aba = chave;
  if (aba === "projetos") {
    acoes.innerHTML = `<label class="busca">${IC.busca}<input id="busca" placeholder="Buscar" value="${esc(filtroProjetos)}"></label>
      <button class="ib" data-acao="recarregar-projetos" title="Recarregar">${IC.atualizar}</button>`;
    $("#busca").addEventListener("input", (e) => { filtroProjetos = e.target.value; projetoAberto = null; renderProjetos(); });
  } else {
    acoes.innerHTML = `<button class="atalho-k" data-acao="paleta" title="Comandos">${IC.busca}<span>Comandos</span><kbd>Ctrl K</kbd></button>
      <button class="ib" data-acao="modo-jogo" title="Modo jogo: para tudo e libera memória">${IC.jogo}</button>`;
  }
}

// --- peças -------------------------------------------------------------

function chipPorta(p, tipo = "") {
  const s = S[p];
  const estado = { ok: "respondendo", erro: "erro no servidor (5xx)", off: "não responde", tcp: "aberta, mas não é HTTP" }[s] || "verificando";
  const oque = { site: "Site (front-end): abre no navegador", api: "API (back-end)" }[tipo] || "Porta";
  return `<button class="porta ${tipo}" ${attr({ acao: "abrir", tipo: "url", alvo: `http://localhost:${p}` })}
    title="${esc(`${oque} · ${estado}\nAbrir localhost:${p}`)}"><i class="${esc(s || "")}"></i>${p}${tipo ? `<span class="tipo-porta">${tipo === "site" ? "site" : "API"}</span>` : ""}</button>`;
}

// Porta para abrir no navegador/celular: o site, se houver
const portaSite = (u) => u.portas.find((p) => u.portas_tipo?.[p] === "site") ?? u.portas[0];

const ib = (icone, dados, titulo, extra = "") => `<button class="ib ${extra}" ${attr(dados)} title="${esc(titulo)}" aria-label="${esc(titulo)}">${IC[icone]}</button>`;

function botoesPasta(pasta) {
  if (!pasta) return "";
  return ib("pasta", { acao: "abrir", tipo: "pasta", alvo: pasta }, "Abrir pasta")
    + ib("codigo", { acao: "abrir", tipo: "vscode", alvo: pasta }, "Abrir no VS Code")
    + ib("terminal", { acao: "abrir", tipo: "terminal", alvo: pasta }, "Abrir terminal aqui");
}

function vazio(icone, titulo, texto) {
  return `<div class="vazio"><div class="ic-grande">${IC[icone]}</div><strong>${esc(titulo)}</strong>${texto}</div>`;
}

// --- rodando -------------------------------------------------------------

// Mini gráfico da memória nos últimos 30 minutos
function spark(pontos, alerta) {
  if (!pontos || pontos.length < 3) return "";
  const w = 46, h = 16, min = Math.min(...pontos), max = Math.max(...pontos), faixa = max - min || 1;
  const d = pontos.map((v, i) => `${((i / (pontos.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / faixa) * (h - 4)).toFixed(1)}`).join(" ");
  return `<svg class="spark ${alerta ? "alta" : ""}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="Memória nos últimos 30 minutos">
    <title>Memória: ${ram(min)} → ${ram(pontos[pontos.length - 1])} (últimos 30 min)</title><polyline points="${d}"/></svg>`;
}

function linhaUnidade(u) {
  const sub = [
    u.orfao ? "terminal fechado" : `aberto por ${esc(u.origem)}`,
    `há ${duracao(agora() - u.inicio)}`,
    ...(u.sem_uso_ha > 1800 ? [`<span class="etq laranja" title="Nenhuma conexão (aba aberta ou requisição) nesse tempo">sem uso há ${duracao(u.sem_uso_ha)}</span>`] : []),
    u.vazando ? `<span class="etq laranja">${ram(u.ram_mb)} e subindo</span>` : ram(u.ram_mb),
    `PID ${u.pid}`,
  ].join('<span class="p">·</span>');
  const logs = u.gerenciado
    ? ib("logs", { acao: "logs", tipo: "processo", alvo: u.gerenciado, nome: u.nome }, "Logs")
    : `<button class="ib" disabled title="Iniciado fora do Argos">${IC.logs}</button>`;
  const auto = u.gerenciado
    ? ib("auto", { acao: "auto", id: u.gerenciado, ligar: u.auto ? "" : "1" },
        u.auto ? "Reinício automático ligado (clique para desligar)" : "Reiniciar sozinho se cair", u.auto ? "ligado" : "")
    : "";
  return `<div class="linha ${u.orfao ? "alerta" : ""}">
    <span class="ponto ${u.orfao ? "laranja" : ""}" title="${u.orfao ? "Órfão: o terminal que o abriu foi fechado" : "Rodando"}"></span>
    <div class="linha-corpo">
      <div class="linha-titulo mono" title="${esc(u.cmd)}">${esc(u.nome)}${u.auto ? ` <span class="etq azul" title="Reinicia sozinho se cair">auto</span>` : ""}</div>
      <div class="linha-sub">${sub}</div>
    </div>
    <div class="linha-fim">
      ${spark(u.ram_hist, u.vazando)}
      ${u.portas.map((p) => chipPorta(p, u.portas_tipo?.[p])).join("")}
      <div class="acoes ocultas">
        ${u.portas.length ? ib("celular", { acao: "celular", porta: portaSite(u), unidade: u.id }, "Abrir no celular (QR code)") : ""}
        ${u.portas.length ? ib("mundo", { acao: "tunel", porta: portaSite(u) }, "Link público (compartilhar pela internet)") : ""}
        ${logs}
        ${auto}
        ${ib("reiniciar", { acao: "reiniciar", pid: u.pid, ger: u.gerenciado || "" }, "Reiniciar")}
        ${ib("parar", { acao: "encerrar", pid: u.pid, nome: u.nome }, "Encerrar", "perigo")}
      </div>
    </div>
  </div>`;
}

function linhaContainer(c) {
  return `<div class="linha">
    <span class="ponto azul" title="Container"></span>
    <div class="linha-corpo">
      <div class="linha-titulo">${esc(c.nome)}</div>
      <div class="linha-sub">${esc(c.imagem)}<span class="p">·</span>${esc(c.status)}</div>
    </div>
    <div class="linha-fim">
      ${c.portas.map(([h]) => chipPorta(h)).join("")}
      <div class="acoes ocultas">
        ${ib("logs", { acao: "logs", tipo: "container", alvo: c.id, nome: c.nome }, "Logs")}
        ${ib("reiniciar", { acao: "container", op: "reiniciar", id: c.id }, "Reiniciar")}
        ${ib("parar", { acao: "container", op: "parar", id: c.id }, "Parar", "perigo")}
      </div>
    </div>
  </div>`;
}

function renderRodando() {
  const partes = [];
  const s = E.sessao;
  if (s) {
    const oq = [s.processos && plural(s.processos, "processo", "processos"), s.containers && plural(s.containers, "container", "containers")].filter(Boolean).join(" e ");
    partes.push(`<div class="aviso-linha sessao"><span class="ic-sessao">${IC.retomar}</span>
      <span style="flex:1">Sessão salva ${s.motivo === "modo jogo" ? "no modo jogo " : ""}às ${hora(s.quando)}: ${oq}${s.projetos.length ? ` (${esc(s.projetos.join(", "))})` : ""}.</span>
      <button class="bt texto" ${attr({ acao: "descartar-sessao", id: s.id })}>Descartar</button>
      <button class="bt azul" ${attr({ acao: "retomar", id: s.id })}>Retomar</button></div>`);
  }
  if (E.resumo.orfaos) {
    partes.push(`<div class="aviso-linha"><span class="ponto laranja"></span>
      <span>${plural(E.resumo.orfaos, "processo continua", "processos continuam")} rodando, mas o terminal que os abriu já foi fechado.</span></div>`);
  }

  for (const a of E.ativos) {
    const acoesProj = a.nome
      ? botoesPasta(a.pasta) + ib("reiniciar", { acao: "reiniciar-projeto", nome: a.nome }, "Reiniciar tudo")
        + ib("parar", { acao: "parar-projeto", nome: a.nome }, "Parar tudo", "perigo")
      : "";
    const nomeUrl = a.nome ? enderecoNome(`${dns(a.nome)}.localhost`) : null;
    const nomeApi = a.nome ? enderecoNome(`api.${dns(a.nome)}.localhost`) : null;
    const links = [nomeUrl && `<button class="link-nome" ${attr({ acao: "abrir", tipo: "url", alvo: nomeUrl })} title="Abrir o site pelo nome">${esc(nomeUrl.replace("http://", ""))}</button>`,
      nomeApi && `<button class="link-nome api" ${attr({ acao: "abrir", tipo: "url", alvo: nomeApi })} title="Abrir a API pelo nome">${esc(nomeApi.replace("http://", ""))}</button>`].filter(Boolean).join("");
    partes.push(`<div class="bloco">
      <div class="titulo-secao">${esc(a.nome || "Sem projeto")}
        <span class="sec">desde ${hora(a.inicio)}</span>${links}
        <div class="acoes">${acoesProj}</div>
      </div>
      <div class="grupo">${a.unidades.map(linhaUnidade).join("")}${a.containers.map(linhaContainer).join("")}</div>
    </div>`);
  }

  if (!E.ativos.length) {
    partes.push(vazio("ok", "Nada rodando", `Inicie um projeto em <b>Projetos</b> ou use <code>argos rodar npm run dev</code>.`));
  }

  if (E.parados.length) {
    partes.push(`<div class="titulo-secao">Parados recentemente</div>
      <div class="grupo">${E.parados.map((p) => `<div class="linha">
        <span class="ponto cinza"></span>
        <div class="linha-corpo">
          <div class="linha-titulo mono">${esc(p.nome)}</div>
          <div class="linha-sub">${esc(p.projeto || "sem projeto")}<span class="p">·</span>parou às ${esc(hora(p.parado_em))}</div>
        </div>
        <div class="linha-fim"><div class="acoes ocultas">
          ${ib("logs", { acao: "logs", tipo: "processo", alvo: p.id, nome: p.nome }, "Logs")}
          ${ib("play", { acao: "reiniciar-ger", id: p.id }, "Iniciar de novo")}
          ${ib("fechar", { acao: "esquecer", id: p.id }, "Remover da lista")}
        </div></div>
      </div>`).join("")}</div>`);
  }

  const soltas = E.portas.filter((p) => !p.unidade && p.tipo !== "container");
  if (soltas.length) {
    partes.push(`<div class="titulo-secao">Outras portas abertas</div>
      <div class="grupo">${soltas.map((p) => `<div class="linha">
        <span class="ponto cinza"></span>
        <div class="linha-corpo"><div class="linha-titulo">${esc(p.programa)}</div>
          <div class="linha-sub">PID ${p.pid}<span class="p">·</span>${esc(p.acesso)}</div></div>
        <div class="linha-fim">${chipPorta(p.porta)}<div class="acoes ocultas">
          ${ib("parar", { acao: "encerrar-porta", porta: p.porta, nome: p.programa }, "Encerrar", "perigo")}</div></div>
      </div>`).join("")}</div>`);
  }

  $("#p-rodando").innerHTML = partes.join("");
}

// --- projetos ------------------------------------------------------------

async function renderProjetos(recarregar = false) {
  const el = $("#p-projetos");
  if (!projetosCache || recarregar) {
    if (!projetosCache) el.innerHTML = vazio("projetos", "Lendo projetos…", "");
    projetosCache = await api.projetos();
    if (E) renderBarra();
  }
  const f = filtroProjetos.toLowerCase();
  const lista = projetosCache.filter((p) => !f || p.nome.toLowerCase().includes(f));
  if (!lista.length) {
    el.innerHTML = vazio("busca", "Nenhum projeto", f ? "Nada com esse nome." : "Configure as pastas de projetos nas configurações.");
    return;
  }
  assinaturaAtivos = assinatura();
  if (projetoAberto) {
    const p = projetosCache.find((x) => x.nome === projetoAberto);
    if (p) { el.innerHTML = paginaProjeto(p); el.scrollTop = 0; return; }
    projetoAberto = null;
  }
  // Os que estão rodando ficam em cima, separados, para ver na hora o que está aberto
  const rodando = lista.filter((p) => ativoDe(p.nome));
  const outros = lista.filter((p) => !ativoDe(p.nome));
  el.innerHTML = (rodando.length ? `<div class="titulo-secao">Rodando agora <span class="sec">${rodando.length}</span></div>
      <div class="cards">${rodando.map(cartaoProjeto).join("")}</div>` : "")
    + (outros.length ? `<div class="titulo-secao">${rodando.length ? "Parados" : "Todos"} <span class="sec">${outros.length}</span></div>
      <div class="cards">${outros.map(cartaoProjeto).join("")}</div>` : "");
}

// Projeto em execução agora (vem do estado), pelo nome
const ativoDe = (nome) => E?.ativos.find((a) => a.nome && a.nome.toLowerCase() === nome.toLowerCase());
const assinatura = () => (E ? E.ativos.map((a) => `${a.nome}:${a.portas.join(",")}`).join("|") : "");
let assinaturaAtivos = "";

function etiquetasProjeto(p) {
  const partes = [];
  if (p.git) {
    partes.push(`<span class="git">${IC.git}${esc(p.git.branch)}</span>`);
    if (p.git.alteracoes) partes.push(`<span class="etq laranja" title="Arquivos alterados e não commitados">${plural(p.git.alteracoes, "alteração", "alterações")}</span>`);
    if (p.git.a_enviar) partes.push(`<span class="etq azul" title="Commits que ainda não foram para o GitHub (git push)">${p.git.a_enviar} a enviar</span>`);
    if (p.git.a_receber) partes.push(`<span class="etq" title="Commits no servidor que você ainda não puxou (git pull)">${p.git.a_receber} a receber</span>`);
  }
  if (p.erro_grupo) partes.push(`<span class="etq vermelho" title="${esc(p.erro_grupo)}">argos.toml com erro</span>`);
  if (p.env_faltando) partes.push(`<span class="etq laranja" title="Variáveis do .env.example que não estão no .env">.env: ${plural(p.env_faltando, "faltando", "faltando")}</span>`);
  if (p.testes) partes.push(p.testes.ok
    ? `<span class="etq verde" title="Últimos testes: ${esc(hora(p.testes.quando))}">✓ testes</span>`
    : `<span class="etq vermelho" title="Últimos testes: ${esc(hora(p.testes.quando))}">✗ ${plural(p.testes.falhas, "teste falhou", "testes falharam")}</span>`);
  return partes;
}

function portasDoAtivo(a) {
  const tipos = Object.assign({}, ...a.unidades.map((u) => u.portas_tipo || {}));
  // Site primeiro: é o que normalmente se abre no navegador
  return [...a.portas].sort((x, y) => (tipos[y] === "site") - (tipos[x] === "site")).map((p) => chipPorta(p, tipos[p] || ""));
}

function cartaoProjeto(p) {
  const a = ativoDe(p.nome);
  const principal = p.comandos[0];
  const rodape = a
    ? `${portasDoAtivo(a).slice(0, 3).join("")}<span class="direita">
        ${ib("reiniciar", { acao: "reiniciar-projeto", nome: a.nome }, "Reiniciar tudo")}
        ${ib("parar", { acao: "parar-projeto", nome: a.nome }, "Parar tudo", "perigo")}</span>`
    : principal ? `<button class="bt" ${attr({ acao: "iniciar", projeto: p.nome, chave: principal.chave })}
        title="${esc((principal.chave === p.fixo ? "Comando fixado · " : "") + (principal.detalhe || principal.cmd))}">
        <span style="color:var(--verde)">${IC.play}</span>${principal.sub ? `<span class="sub-cmd">${esc(principal.sub)}</span>` : ""}${esc(principal.rotulo)}</button>` : `<span class="linha-sub">sem comandos</span>`;
  return `<div class="cartao ${a ? "rodando" : ""}" role="button" tabindex="0" ${attr({ acao: "abrir-projeto", projeto: p.nome })}>
    <div class="cartao-topo">
      <span class="ponto ${a ? "" : "cinza"}"></span>
      <span class="cartao-nome">${esc(p.nome)}</span>
      ${a ? `<span class="cartao-desde">desde ${hora(a.inicio)}</span>` : ""}
    </div>
    <div class="cartao-tipos">${esc(p.tipos.join(" · ") || "sem comandos detectados")}</div>
    <div class="cartao-etqs">${etiquetasProjeto(p).join("")}</div>
    <div class="cartao-rodape">${rodape}</div>
  </div>`;
}

// Página de um projeto (substitui a lista de cards)
function paginaProjeto(p) {
  return `<div class="pag">
    <button class="voltar" data-acao="fechar-projeto">${IC.chevron}Projetos</button>
    <div class="pag-cab">
      <div class="linha-corpo">
        <div class="pag-nome">${esc(p.nome)}</div>
        <div class="linha-sub">${[esc(p.tipos.join(" · ") || "sem comandos detectados"), ...etiquetasProjeto(p)].join('<span class="p">·</span>')}</div>
      </div>
      <div class="linha-fim">${botoesPasta(p.pasta)}</div>
    </div>
    <div data-status-projeto>${statusProjeto(p)}</div>
    ${detalheProjeto(p)}
  </div>`;
}

function statusProjeto(p) {
  const a = ativoDe(p.nome);
  if (!a) return "";
  const nomeUrl = enderecoNome(`${dns(a.nome)}.localhost`);
  const nomeApi = enderecoNome(`api.${dns(a.nome)}.localhost`);
  const links = [nomeUrl && `<button class="link-nome" ${attr({ acao: "abrir", tipo: "url", alvo: nomeUrl })} title="Abrir o site pelo nome">${esc(nomeUrl.replace("http://", ""))}</button>`,
    nomeApi && `<button class="link-nome api" ${attr({ acao: "abrir", tipo: "url", alvo: nomeApi })} title="Abrir a API pelo nome">${esc(nomeApi.replace("http://", ""))}</button>`].filter(Boolean).join("");
  return `<div class="pag-rodando">
    <span class="ponto"></span><b>Rodando</b><span class="linha-sub">desde ${hora(a.inicio)} · ${plural(a.unidades.length + a.containers.length, "item", "itens")}</span>
    ${portasDoAtivo(a).join("")}${links}
    <span class="direita">
      <button class="bt texto" ${attr({ acao: "aba", aba: "rodando" })}>Ver processos</button>
      ${ib("reiniciar", { acao: "reiniciar-projeto", nome: a.nome }, "Reiniciar tudo")}
      ${ib("parar", { acao: "parar-projeto", nome: a.nome }, "Parar tudo", "perigo")}
    </span>
  </div>`;
}

// A cada ciclo: só redesenha os projetos quando algo começou/parou ou mudou de porta
function atualizarProjetosRodando() {
  if (!projetosCache || assinatura() === assinaturaAtivos) return;
  if (projetoAberto) {
    assinaturaAtivos = assinatura();
    const p = projetosCache.find((x) => x.nome === projetoAberto);
    const el = document.querySelector("[data-status-projeto]");
    if (p && el) el.innerHTML = statusProjeto(p);
  } else renderProjetos();
}

function detalheProjeto(p) {
  const grupo = p.erro_grupo
    ? `<div class="erro-grupo">argos.toml: ${esc(p.erro_grupo)}</div>`
    : p.grupo ? "" : `<div class="lin dica-grupo"><span>Tem mais de uma parte (banco, backend, frontend)? Um <b>argos.toml</b> sobe tudo em ordem com um clique.</span>
        <button class="bt texto" ${attr({ acao: "criar-grupo", projeto: p.nome })}>Criar argos.toml</button></div>`;
  // Comandos agrupados pela pasta onde rodam (raiz, backend/, frontend/...)
  const pastas = [...new Set(p.comandos.map((c) => c.sub || ""))];
  const linhaCmd = (c) => {
    const fixo = c.chave === p.fixo;
    return `<div class="cmd-linha" role="button" tabindex="0" ${attr({ acao: "iniciar", projeto: p.nome, chave: c.chave })} title="${esc(c.detalhe || c.cmd)}">
      <span class="play">${IC.play}</span><span class="nome">${esc(c.rotulo)}</span>
      ${c.recente ? `<span class="etq">recente</span>` : ""}
      ${c.porta || c.ferramenta ? `<button class="porta-prev ${c.porta_fixa ? "fixa" : ""}" ${attr({ acao: "editar-porta", projeto: p.nome, chave: c.chave, porta: c.porta || "" })}
        title="${c.porta_fixa ? "Porta fixa deste comando (clique para mudar)" : c.ferramenta ? "Porta prevista: vira fixa ao iniciar (clique para escolher)" : "Porta prevista"}">:${c.porta || "?"}</button>` : ""}
      <span class="cmd-acoes">
        ${c.recente ? ib("fechar", { acao: "esquecer-recente", projeto: p.nome, chave: c.chave }, "Remover dos recentes")
          : ib("fechar", { acao: "ocultar-comando", projeto: p.nome, chave: c.chave }, "Apagar da lista\n(dá para restaurar depois)")}
        ${ib(fixo ? "fixado" : "fixar", { acao: "fixar", projeto: p.nome, chave: fixo ? "" : c.chave },
            fixo ? "Fixado como principal (clique para soltar)" : "Fixar como comando principal", fixo ? "ligado fixo" : "")}
      </span>
    </div>`;
  };
  const opcoesPasta = pastas.filter(Boolean).map((s) => `<option value="${esc(s)}">${esc(s)}/</option>`).join("");
  return `<div class="detalhe">
    <div class="extra"><div class="extra-titulo">${IC.play}Comandos</div>
    ${p.comandos.length ? pastas.map((s) => `<div class="cmd-grupo">
      ${pastas.length > 1 ? `<div class="cmd-pasta">${s ? `${IC.pasta}${esc(s)}/` : `${IC.pasta}raiz do projeto`}</div>` : ""}
      ${p.comandos.filter((c) => (c.sub || "") === s).map(linhaCmd).join("")}
    </div>`).join("") : ""}
    <div class="lin">
      ${opcoesPasta ? `<select class="campo seletor" data-custom-pasta="${esc(p.nome)}" title="Pasta onde o comando roda">
        <option value="">raiz</option>${opcoesPasta}</select>` : ""}
      <input class="campo mono" placeholder="Outro comando…" data-custom="${esc(p.nome)}">
      <button class="bt" ${attr({ acao: "iniciar-custom", projeto: p.nome })}>Rodar</button>
    </div>
    ${(p.ocultos || []).length ? `<div class="lin cmd-ocultos">
      <span class="linha-sub">${plural(p.ocultos.length, "apagado", "apagados")}:</span>
      ${p.ocultos.map((o) => `<button class="cmd-oculto" ${attr({ acao: "restaurar-comandos", projeto: p.nome, chave: o.chave })}
        title="Restaurar este comando">${IC.reiniciar}${o.sub ? esc(o.sub) + "/ " : ""}${esc(o.rotulo)}</button>`).join("")}
      ${p.ocultos.length > 1 ? `<button class="bt texto" ${attr({ acao: "restaurar-comandos", projeto: p.nome })}>Restaurar todos</button>` : ""}
    </div>` : ""}
    ${grupo}
    </div>
    <div data-extras="${esc(p.nome)}">${renderExtras(p)}</div>
    <div class="extra"><div class="lin">
      <div class="deps" data-deps="${esc(p.pasta)}" style="flex:1">${renderDeps(p.pasta)}</div>
    </div></div>
  </div>`;
}

// Git, .env e testes: carregados quando o projeto é aberto
const extrasCache = {};
const extrasCarregando = new Set();

async function carregarExtras(nome, forcar = false) {
  if ((extrasCache[nome] && !forcar) || extrasCarregando.has(nome)) return;
  extrasCarregando.add(nome);
  try {
    const [branches, env, testes] = await Promise.all([api.git_branches(nome), api.ambiente(nome), api.testes(nome)]);
    extrasCache[nome] = { branches, env, testes };
  } finally {
    extrasCarregando.delete(nome);
  }
  const el = document.querySelector(`[data-extras="${CSS.escape(nome)}"]`);
  const p = (projetosCache || []).find((x) => x.nome === nome);
  if (el && p) el.innerHTML = renderExtras(p);
}

function renderExtras(p) {
  const x = extrasCache[p.nome];
  if (!x) { carregarExtras(p.nome); return `<div class="extra-carregando"><span class="girando"></span></div>`; }
  const blocos = [];

  if (p.git && x.branches.locais.length) {
    const g = p.git;
    const opcoes = x.branches.locais.map((b) => `<option ${b === x.branches.atual ? "selected" : ""}>${esc(b)}</option>`).join("");
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.git}Git</div><div class="lin">
      <select class="campo seletor" data-git-branch="${esc(p.nome)}" title="Trocar de branch">${opcoes}</select>
      <span class="linha-sub" style="flex:1">${g.alteracoes ? plural(g.alteracoes, "alteração", "alterações") + " não commitada(s)" : "sem alterações"}</span>
      <button class="bt texto" ${attr({ acao: "git", projeto: p.nome, op: "fetch" })} title="Buscar novidades do servidor">Fetch</button>
      <button class="bt ${g.a_receber ? "azul" : ""}" ${attr({ acao: "git", projeto: p.nome, op: "pull" })}>Pull${g.a_receber ? ` (${g.a_receber})` : ""}</button>
      <button class="bt ${g.a_enviar ? "azul" : ""}" ${attr({ acao: "git", projeto: p.nome, op: "push" })}>Push${g.a_enviar ? ` (${g.a_enviar})` : ""}</button>
    </div></div>`);
  }

  if (x.env.length) {
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.chave}Variáveis de ambiente</div>${x.env.map((a) => `
      <div class="env-pasta">
        ${x.env.length > 1 || a.sub ? `<span class="env-onde">${esc(a.sub ? a.sub + "/" : "raiz")}</span>` : ""}
        ${a.arquivos.map((f) => `<button class="bt texto" ${attr({ acao: "editar-env", caminho: f.caminho, projeto: p.nome })} title="${f.chaves} variável(is)">${esc(f.nome)}</button>`).join("")}
        ${a.faltando.length ? `<span class="etq laranja" title="${esc(a.faltando.join(", "))}">${a.sem_env ? "sem .env" : `faltam ${a.faltando.length}: ${esc(a.faltando.slice(0, 3).join(", "))}${a.faltando.length > 3 ? "…" : ""}`}</span>
          <button class="bt texto" ${attr({ acao: "completar-env", pasta: a.pasta, projeto: p.nome })}>${a.sem_env ? "Criar .env do exemplo" : "Completar"}</button>` : ""}
      </div>`).join("")}</div>`);
  }

  const lista = (x.testes && x.testes.lista) || [];
  if (lista.length) {
    const res = x.testes.resultados || {};
    blocos.push(`<div class="extra"><div class="extra-titulo">${IC.teste}Testes
      <button class="bt texto" style="margin-left:auto" ${attr({ acao: "testar", projeto: p.nome })}>Rodar todos</button></div>
      ${lista.map((t) => { const r = res[t.chave]; return `<div class="lin teste-linha">
        <span class="ponto ${r ? (r.ok ? "" : "vermelho") : "cinza"}"></span>
        <span class="mono">${t.sub ? esc(t.sub) + "/ " : ""}${esc(t.cmd)}</span>
        <span class="linha-sub" style="flex:1">${r ? `${esc(r.resumo)} · ${esc(hora(r.quando))}` : "nunca rodou"}</span>
        ${r ? `<button class="bt texto" ${attr({ acao: "log-teste", caminho: r.log })}>Log</button>` : ""}
        <button class="ib" ${attr({ acao: "testar", projeto: p.nome, chave: t.chave })} title="Rodar">${IC.play}</button>
      </div>`; }).join("")}</div>`);
  }
  return blocos.join("");
}

function renderDeps(pasta) {
  const d = depsCache[pasta];
  if (d === undefined) return `<button class="bt texto" ${attr({ acao: "deps", pasta })}>Ver espaço das dependências</button>`;
  if (d === null) return `<span class="girando"></span>`;
  if (!d.length) return "Sem node_modules ou .venv";
  return d.map((x) => `<div class="deps-item"><span class="mono">${esc(x.nome)}</span> ${bytes(x.bytes)}
    <button class="bt texto perigo" ${attr({ acao: "apagar-dep", caminho: x.caminho, nome: x.nome })}>Apagar</button></div>`).join("");
}

// --- docker --------------------------------------------------------------

function renderDocker() {
  const el = $("#p-docker");
  const dk = E.docker;
  if (!dk.instalado) { el.innerHTML = vazio("docker", "Docker não instalado", ""); return; }
  const nenhumRodando = !dk.containers.some((c) => c.estado === "running");
  const dica = dk.vmmem_mb != null
    ? `A VM do WSL está usando ${ram(dk.vmmem_mb)} de memória.${nenhumRodando && dk.vmmem_mb > 500 ? " Nenhum container rodando: desligar libera essa memória." : ""}`
    : "A VM do WSL não está rodando.";

  const containers = dk.containers.length ? `<div class="grupo">${dk.containers.map((c) => {
    const rodando = c.estado === "running";
    return `<div class="linha">
      <span class="ponto ${rodando ? "azul" : "cinza"}"></span>
      <div class="linha-corpo">
        <div class="linha-titulo">${esc(c.nome)}</div>
        <div class="linha-sub">${esc(c.imagem)}${c.projeto ? `<span class="p">·</span>${esc(c.projeto)}` : ""}<span class="p">·</span>${esc(c.status)}</div>
      </div>
      <div class="linha-fim">
        ${c.portas.map(([h]) => chipPorta(h)).join("")}
        <div class="acoes ocultas">
          ${ib("logs", { acao: "logs", tipo: "container", alvo: c.id, nome: c.nome }, "Logs")}
          ${rodando
            ? ib("reiniciar", { acao: "container", op: "reiniciar", id: c.id }, "Reiniciar") + ib("parar", { acao: "container", op: "parar", id: c.id }, "Parar", "perigo")
            : ib("play", { acao: "container", op: "iniciar", id: c.id }, "Iniciar")}
        </div>
      </div>
    </div>`;
  }).join("")}</div>` : `<div class="grupo"><div class="linha"><div class="linha-corpo linha-sub">${dk.ligado ? "Nenhum container." : "Ligue o Docker para ver os containers."}</div></div></div>`;

  let disco = "";
  if (dk.ligado) {
    const d = discoCache;
    disco = `<div class="titulo-secao">Espaço em disco
        <span class="sec">imagens, volumes e cache acumulam com o tempo</span>
        <div style="margin-left:auto" class="lin">
          <button class="bt texto" data-acao="docker-disco">${d ? "Atualizar" : "Analisar"}</button>
          <button class="bt texto perigo" data-acao="docker-limpar">Limpar…</button>
        </div></div>
      ${d === null ? `<div class="grupo"><div class="linha"><span class="girando"></span></div></div>` : d ? `<div class="grupo"><table class="tab">
        <thead><tr><th>Tipo</th><th class="num">Total</th><th class="num">Em uso</th><th class="num">Tamanho</th><th class="num">Recuperável</th></tr></thead><tbody>
        ${d.map((x) => `<tr><td>${esc(x.tipo)}</td><td class="num">${esc(x.total)}</td><td class="num">${esc(x.ativos)}</td><td class="num">${esc(x.tamanho)}</td><td class="num">${esc(x.recuperavel)}</td></tr>`).join("")}
      </tbody></table></div>` : ""}`;
  }

  el.innerHTML = `<div class="grupo"><div class="linha">
      <span class="ic" style="color:var(--azul);width:20px">${IC.docker}</span>
      <div class="linha-corpo"><div class="linha-titulo">Docker Desktop</div><div class="linha-sub">${esc(dica)}</div></div>
      <div class="linha-fim"><label class="chave" title="${dk.ligado ? "Desligar" : "Ligar"} o Docker Desktop">
        <input type="checkbox" data-acao="${dk.ligado ? "docker-desligar" : "docker-ligar"}" ${dk.ligado ? "checked" : ""}><span></span></label></div>
    </div></div>
    <div class="titulo-secao">Containers</div>${containers}${disco}`;
}

// --- ferramentas ---------------------------------------------------------

function renderFerramentas() {
  const el = $("#p-ferramentas");
  if (!E.ferramentas.length) {
    el.innerHTML = vazio("ferramentas", "Nenhuma ferramenta rodando", "Servidores MCP do Claude e afins aparecem aqui.");
    return;
  }
  el.innerHTML = `<p class="linha-sub" style="white-space:normal;margin:0 2px 4px;font-size:12px">Servidores MCP e ferramentas de apps como o Claude. Cada sessão aberta costuma ter a sua; as marcadas em laranja perderam o app que as abriu e só gastam memória.</p>`
    + E.ferramentas.map((f) => `<div class="bloco">
      <div class="titulo-secao">${esc(f.nome)} <span class="sec">${plural(f.instancias, "instância", "instâncias")} · ${ram(f.ram_mb)}</span>
        ${f.orfas ? `<span class="etq laranja">${plural(f.orfas, "órfã", "órfãs")}</span>` : ""}</div>
      <div class="grupo">${f.unidades.map((u) => `<div class="linha ${u.orfao ? "alerta" : ""}">
        <span class="ponto ${u.orfao ? "laranja" : "cinza"}"></span>
        <div class="linha-corpo">
          <div class="linha-titulo mono" title="${esc(u.cmd)}">${esc(u.nome)}</div>
          <div class="linha-sub">${u.orfao ? "sem dono" : `aberto por ${esc(u.origem)}`}<span class="p">·</span>desde ${esc(hora(u.inicio))}<span class="p">·</span>${ram(u.ram_mb)}<span class="p">·</span>PID ${u.pid}</div>
        </div>
        <div class="linha-fim">${u.portas.map(chipPorta).join("")}<div class="acoes ocultas">
          ${ib("parar", { acao: "encerrar", pid: u.pid, nome: u.nome, ferramenta: 1 }, "Encerrar", "perigo")}</div></div>
      </div>`).join("")}</div>
    </div>`).join("");
}

// --- hoje ----------------------------------------------------------------

async function renderHoje() {
  const el = $("#p-hoje");
  const itens = await api.historico();
  if (!itens.length) {
    el.innerHTML = vazio("hoje", "Nada registrado hoje", "O histórico é gravado enquanto o Argos está aberto.");
    return;
  }
  const por = {};
  for (const i of itens) por[i.projeto || "sem projeto"] = (por[i.projeto || "sem projeto"] || 0) + i.duracao;
  const ordem = Object.entries(por).sort((a, b) => b[1] - a[1]);
  const max = ordem[0][1] || 1;
  el.innerHTML = `
    <div class="titulo-secao">Tempo por projeto</div>
    <div class="grupo">${ordem.map(([p, s]) => `<div class="linha">
      <div class="linha-corpo"><div class="linha-titulo">${esc(p)}</div></div>
      <div class="linha-fim"><div class="barra-tempo"><i style="width:${Math.max(3, (s / max) * 100)}%"></i></div>
        <span class="linha-sub" style="width:84px;text-align:right">${duracao(s)}</span></div>
    </div>`).join("")}</div>
    <div class="titulo-secao">Linha do tempo</div>
    <div class="grupo">${itens.slice().reverse().map((i) => `<div class="linha">
      <span class="ponto ${i.rodando ? "" : "cinza"}"></span>
      <div class="linha-corpo"><div class="linha-titulo mono">${esc(i.nome)}</div>
        <div class="linha-sub">${esc(i.projeto || "sem projeto")}<span class="p">·</span>${esc(hora(i.inicio))}</div></div>
      <div class="linha-fim"><span class="linha-sub">${i.rodando ? "rodando · " : ""}${duracao(i.duracao)}</span></div>
    </div>`).join("")}</div>`;
}

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

function abrirLogs(tipo, alvo, nome) {
  logAtual = { tipo, alvo, nome, fim: -1, texto: "" };
  $("#log-titulo").textContent = nome;
  $("#log-sub").textContent = tipo === "container" ? "container · últimas 500 linhas" : "carregando…";
  $("#log").innerHTML = "";
  $("#log-busca").value = "";
  $("#log-erros").checked = false;
  $("#gaveta").hidden = false;
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

// --- alertas, folhas e avisos -------------------------------------------

function modal(html, aoAbrir) {
  return new Promise((resolve) => {
    const m = $("#modal"), f = $("#fundo");
    m.innerHTML = html;
    m.hidden = f.hidden = false;
    const fechar = (v) => { m.hidden = f.hidden = true; m.innerHTML = ""; document.removeEventListener("keydown", tecla); resolve(v); };
    const tecla = (e) => {
      if (e.key === "Escape") fechar(null);
      if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") m.querySelector("[data-padrao]")?.click();
    };
    document.addEventListener("keydown", tecla);
    f.onclick = () => fechar(null);
    m.querySelectorAll("[data-resp]").forEach((b) => b.addEventListener("click", () => fechar(b.dataset.resp === "nao" ? null : b.dataset.resp)));
    aoAbrir && aoAbrir(m, fechar);
    (m.querySelector("[data-foco]") || m.querySelector("[data-padrao]"))?.focus();
  });
}

// Alerta compacto no estilo do macOS: ícone, título, texto, botões empilhados
function confirmar(titulo, texto, botao = "Confirmar", perigo = true) {
  return modal(`<div class="dialogo">
    <div class="icone-app">&gt;_</div>
    <h3>${esc(titulo)}</h3><p>${texto}</p>
    <div class="botoes">
      <button class="bt ${perigo ? "vermelho" : "azul"}" data-resp="sim" data-padrao>${esc(botao)}</button>
      <button class="bt" data-resp="nao">Cancelar</button>
    </div></div>`);
}

function avisar(msg, erro = false, botao = null, opcoes = {}) {
  const d = document.createElement("div");
  d.className = "aviso";
  const cor = opcoes.cor || (erro ? "var(--vermelho)" : "var(--verde)");
  const titulo = opcoes.titulo ? `<b>${esc(opcoes.titulo)}</b>` : "";
  d.innerHTML = `<span class="ponto" style="background:${cor}"></span><span class="aviso-texto">${titulo}${esc(msg)}</span>`;
  if (botao) {
    const b = document.createElement("button");
    b.className = "bt azul";
    b.textContent = botao.texto;
    b.onclick = () => { d.remove(); botao.acao(); };
    d.appendChild(b);
  }
  const lista = $("#avisos");
  lista.appendChild(d);
  while (lista.children.length > 4) lista.firstChild.remove();
  setTimeout(() => d.remove(), opcoes.duracao || (botao ? 12000 : erro ? 7000 : 3200));
}

// Avisos que vêm do monitor (caiu, pronto, subindo…)
function avisarEvento(ev) {
  const cores = { erro: "var(--vermelho)", aviso: "var(--laranja)", info: "var(--verde)" };
  let botao = null;
  const a = ev.acao;
  if (a) botao = { texto: a.rotulo, acao: () => executarAcaoEvento(a) };
  else if (ev.url) botao = { texto: "Abrir", acao: () => api.abrir("url", ev.url) };
  else if (ev.id) botao = { texto: "Ver logs", acao: () => abrirLogs("processo", ev.id, ev.titulo.replace(/ (caiu|pronto).*$/, "")) };
  const progresso = ev.tipo === "progresso";
  avisar(ev.msg, ev.nivel === "erro", progresso ? null : botao, {
    titulo: progresso ? `${ev.titulo} · ` : `${ev.titulo}  `,
    cor: progresso ? "var(--azul)" : cores[ev.nivel],
    duracao: progresso ? 2500 : ev.nivel === "erro" ? 15000 : undefined,
  });
}

// Botões dos avisos do monitor (ex: "Parar" num servidor ocioso, "Pull" no Git)
async function executarAcaoEvento(a) {
  if (a.tipo === "encerrar") resultado(await api.encerrar(a.pid), ["matar", String(a.pid)]);
  else if (a.tipo === "git") resultado(await api.git(a.projeto, a.op));
  else if (a.tipo === "atualizar") resultado(await api.atualizar());
  else if (a.tipo === "log-arquivo") abrirLogs("arquivo", a.caminho, "Testes");
}

// Endereço com nome (http://projeto.localhost) para um host, se o proxy estiver ligado
function enderecoNome(host) {
  const px = E && E.proxy;
  if (!px || !px.porta || !(host in (px.rotas || {}))) return null;
  return `http://${host}${px.porta === 80 ? "" : ":" + px.porta}`;
}
const dns = (s) => s.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-|-$/g, "") || "projeto";

async function abrirTunel(porta) {
  const carregando = modal(`<div class="folha celular"><h3>Link público</h3><p>Abrindo o túnel… isso leva alguns segundos.</p>
    <div class="qr"><span class="girando" style="width:28px;height:28px"></span></div></div>`);
  const r = await api.tunel(+porta);
  $("#fundo").click();
  await carregando;
  if (r.falta_cloudflared) {
    const ok = await confirmar("Instalar o cloudflared?", "O link público usa o cloudflared, gratuito e oficial da Cloudflare. Ele será instalado pelo winget (aceitando a licença do pacote).", "Instalar", false);
    if (!ok) return;
    avisar("Instalando o cloudflared… pode levar um minuto.");
    const inst = await api.instalar_cloudflared();
    if (!inst.ok) return avisar(inst.msg, true);
    return abrirTunel(porta);
  }
  if (!r.ok) return avisar(r.msg, true, r.id ? { texto: "Ver logs", acao: () => abrirLogs("processo", r.id, `túnel :${porta}`) } : null);
  await modal(`<div class="folha celular">
    <h3>Link público</h3>
    <p>Qualquer pessoa com o link acessa a porta ${porta} enquanto o túnel estiver aberto.</p>
    <div class="qr">${r.svg || ""}</div>
    <div class="lin" style="justify-content:center"><code class="url">${esc(r.url)}</code>
      <button class="ib" data-acao="copiar" data-texto="${esc(r.url)}" title="Copiar">${IC.copiar}</button></div>
    <div class="rodape"><button class="bt vermelho" id="tn-fechar">Fechar túnel</button><button class="bt azul" data-resp="nao" data-padrao>OK</button></div>
  </div>`, (m, fechar) => {
    m.querySelector("#tn-fechar").onclick = async () => { fechar(null); resultado(await api.encerrar(r.pid)); };
  });
}

async function abrirCelular(porta, idUnidade) {
  const r = await api.celular(+porta);
  if (!r || !r.ok) return avisar(r ? r.msg : "Falhou.", true);
  // Mais de uma porta (ex: site + API): botões para trocar
  const u = idUnidade && E ? E.unidades.find((x) => x.id === idUnidade) : null;
  const opcoes = u && u.portas.length > 1 ? `<div class="segmentos">${u.portas.map((p) => {
    const t = u.portas_tipo?.[p];
    return `<button class="${p === +porta ? "ativo" : ""}" data-trocar="${p}">${p}${t ? ` · ${t === "site" ? "site" : "API"}` : ""}</button>`;
  }).join("")}</div>` : "";
  const tipo = u?.portas_tipo?.[+porta];
  const aviso = tipo === "api" ? `<p class="nota">Essa porta é a API. Para ver o site no celular, escolha a porta marcada como <b>site</b>.</p>` : "";
  await modal(`<div class="folha celular">
    <h3>Abrir no celular</h3>
    <p>Aponte a câmera do celular, conectado na mesma rede Wi-Fi.</p>
    ${opcoes}
    <div class="qr">${r.svg}</div>
    ${aviso}
    <div class="lin" style="justify-content:center"><code class="url">${esc(r.url)}</code>
      <button class="ib" data-acao="copiar" data-texto="${esc(r.url)}" title="Copiar endereço">${IC.copiar}</button></div>
    ${r.so_local ? `<div class="erro-grupo" style="margin-top:12px">Esse servidor só aceita conexões deste PC, então o celular não vai abrir. Para liberar: ${esc(r.dica).replace(/(ex: |use |com )(.+)$/, "$1<code>$2</code>")}.</div>` : ""}
    <p class="nota">Se não abrir, permita o programa no Firewall do Windows (redes privadas).</p>
    <div class="rodape"><button class="bt azul" data-resp="nao" data-padrao>OK</button></div>
  </div>`, (m, fechar) => {
    m.querySelectorAll("[data-trocar]").forEach((b) => b.addEventListener("click", () => {
      fechar(null);
      abrirCelular(+b.dataset.trocar, idUnidade);
    }));
  });
}

// Mostra o resultado de uma ação; se faltar permissão, oferece rodar como admin
function resultado(r, argsAdmin) {
  if (!r) return;
  if (r.msg) avisar(r.msg, !r.ok, r.admin && argsAdmin ? {
    texto: "Tentar como admin", acao: async () => resultado(await api.admin(argsAdmin)),
  } : null);
  setTimeout(ciclo, 300);
}

async function comCarregando(botao, fn) {
  const html = botao?.innerHTML;
  if (botao) { botao.disabled = true; botao.innerHTML = `<span class="girando"></span>`; }
  try { return await fn(); }
  finally { if (botao && botao.isConnected) { botao.disabled = false; botao.innerHTML = html; } }
}

// --- ações -------------------------------------------------------------

const ACOES = {
  aba: (d) => trocarAba(d.aba),
  abrir: async (d) => { const r = await api.abrir(d.tipo, d.alvo); if (r && !r.ok) avisar(r.msg, true); },
  logs: (d) => abrirLogs(d.tipo, d.alvo, d.nome),
  "log-fechar": () => { $("#gaveta").hidden = true; logAtual = null; },
  "log-copiar": async () => {
    const r = await api.copiar($("#log").innerText);
    avisar(r.ok ? "Log copiado." : r.msg, !r.ok);
  },
  copiar: async (d) => { const r = await api.copiar(d.texto); avisar(r.ok ? "Copiado." : r.msg, !r.ok); },
  celular: (d) => abrirCelular(d.porta, d.unidade),
  auto: async (d) => resultado(await api.auto(d.id, !!d.ligar)),
  "criar-grupo": async (d) => {
    const r = await api.criar_grupo(d.projeto);
    resultado(r);
    if (r.ok) setTimeout(() => renderProjetos(true), 800);
  },

  "jan-fechar": () => api.esconder(),
  "jan-minimizar": () => api.minimizar(),
  "jan-maximizar": () => api.maximizar(),

  "abrir-projeto": (d) => { projetoAberto = d.projeto; renderProjetos(); },
  "fechar-projeto": () => { projetoAberto = null; renderProjetos(); },

  reiniciar: async (d, b) => resultado(await comCarregando(b, () => api.reiniciar(+d.pid, d.ger || null)), ["reiniciar", d.pid]),
  "reiniciar-ger": async (d, b) => resultado(await comCarregando(b, () => api.reiniciar_gerenciado(d.id))),
  esquecer: async (d) => resultado(await api.esquecer(d.id)),
  encerrar: async (d, b) => {
    const extra = d.ferramenta ? " Se a sessão que usa essa ferramenta ainda estiver aberta, ela pode parar de funcionar." : "";
    if (!(await confirmar(`Encerrar ${d.nome}?`, `O processo ${esc(d.pid)} e os filhos dele serão encerrados.${extra}`, "Encerrar"))) return;
    resultado(await comCarregando(b, () => api.encerrar(+d.pid)), ["matar", d.pid]);
  },
  "encerrar-porta": async (d, b) => {
    if (!(await confirmar(`Encerrar ${d.nome}?`, `Ele está usando a porta ${esc(d.porta)}.`, "Encerrar"))) return;
    resultado(await comCarregando(b, () => api.encerrar_porta(+d.porta)), ["porta", d.porta]);
  },
  "parar-projeto": async (d, b) => {
    if (!(await confirmar(`Parar ${d.nome}?`, "Todos os processos e containers desse projeto serão parados.", "Parar tudo"))) return;
    resultado(await comCarregando(b, () => api.parar_projeto(d.nome)), ["parar", d.nome]);
  },
  "reiniciar-projeto": async (d, b) => resultado(await comCarregando(b, () => api.reiniciar_projeto(d.nome)), ["reiniciar", d.nome]),
  container: async (d, b) => resultado(await comCarregando(b, () => api.container(d.op, d.id))),

  iniciar: async (d, b) => {
    let r = await comCarregando(b, () => api.iniciar(d.projeto, d.chave, false));
    if (r && r.conflito) {
      const c = r.conflito;
      const ok = await confirmar("Porta em uso", `A porta ${c.porta} já está sendo usada por ${esc(c.dono)}${c.projeto ? ` (${esc(c.projeto)})` : ""}. Encerrar e iniciar mesmo assim?`, "Encerrar e iniciar");
      if (!ok) return;
      const e = await api.encerrar(c.pid);
      if (!e.ok) return resultado(e, ["matar", String(c.pid)]);
      r = await comCarregando(b, () => api.iniciar(d.projeto, d.chave, true));
    }
    resultado(r);
    if (r && r.ok && r.extra && r.extra.id) setTimeout(() => abrirLogs("processo", r.extra.id, r.msg.replace(/^Iniciado: /, "")), 400);
    if (r && r.ok) atualizarProjetosDepois();
  },
  subir: async (d, b) => resultado(await comCarregando(b, () => api.subir(d.projeto))),
  "iniciar-custom": async (d, b) => {
    const campo = document.querySelector(`[data-custom="${CSS.escape(d.projeto)}"]`);
    const sub = document.querySelector(`[data-custom-pasta="${CSS.escape(d.projeto)}"]`)?.value || "";
    const cmd = campo.value.trim();
    if (!cmd) { campo.focus(); return; }
    const r = await comCarregando(b, () => api.iniciar_personalizado(d.projeto, cmd, sub));
    resultado(r);
    if (r && r.ok) {
      campo.value = "";
      setTimeout(() => abrirLogs("processo", r.extra.id, sub ? `${sub}: ${cmd}` : cmd), 400);
      atualizarProjetosDepois();
    }
  },
  retomar: async (d, b) => resultado(await comCarregando(b, () => api.retomar(d.id || null))),
  "descartar-sessao": async (d) => resultado(await api.descartar_sessao(d.id)),
  "salvar-sessao": async () => resultado(await api.salvar_sessao()),
  tunel: (d) => abrirTunel(d.porta),
  "editar-porta": async (d) => {
    const r = await modal(`<div class="folha"><h3>Porta fixa</h3>
      <p>Esse comando sempre vai subir nessa porta. Deixe vazio para o Argos escolher sozinho.</p>
      <div class="form"><div class="grupo"><label class="item"><span class="rot">Porta</span>
        <input class="campo" id="pf-porta" type="number" min="1" max="65535" value="${esc(d.porta)}" data-foco></label></div></div>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="pf-ok" data-padrao>Salvar</button></div></div>`,
      (m, fechar) => { m.querySelector("#pf-ok").onclick = () => fechar({ porta: m.querySelector("#pf-porta").value }); });
    if (!r) return;
    resultado(await api.definir_porta(d.projeto, d.chave, r.porta ? +r.porta : null));
    renderProjetos(true);
  },
  git: async (d, b) => {
    const r = await comCarregando(b, () => api.git(d.projeto, d.op));
    resultado(r);
    if (r.ok) { delete extrasCache[d.projeto]; renderProjetos(true); }
  },
  "editar-env": async (d) => {
    const r = await api.ler_env(d.caminho);
    if (!r.ok) return avisar(r.msg, true);
    const nome = d.caminho.split("\\").pop();
    const resp = await modal(`<div class="folha env"><h3>${esc(nome)}</h3>
      <p>${esc(d.caminho)}</p>
      <textarea class="campo mono" id="env-texto" spellcheck="false" data-foco>${esc(r.texto)}</textarea>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="env-ok">Salvar</button></div></div>`,
      (m, fechar) => { m.querySelector("#env-ok").onclick = () => fechar({ texto: m.querySelector("#env-texto").value }); });
    if (!resp) return;
    resultado(await api.salvar_env(d.caminho, resp.texto));
    delete extrasCache[d.projeto];
    renderProjetos(true);
  },
  "completar-env": async (d) => {
    resultado(await api.completar_env(d.pasta));
    delete extrasCache[d.projeto];
    renderProjetos(true);
  },
  testar: async (d, b) => resultado(await comCarregando(b, () => api.testar(d.projeto, d.chave || null))),
  "log-teste": (d) => abrirLogs("arquivo", d.caminho, "Testes"),
  "procurar-atualizacao": async () => resultado(await api.atualizar()),
  "conectar-claude": async (d, b) => resultado(await comCarregando(b, () => api.instalar_mcp())),
  fixar: async (d) => { resultado(await api.fixar(d.projeto, d.chave || null)); renderProjetos(true); },
  "esquecer-recente": async (d) => { resultado(await api.esquecer_recente(d.projeto, d.chave)); renderProjetos(true); },
  "ocultar-comando": async (d) => { resultado(await api.ocultar_comando(d.projeto, d.chave)); renderProjetos(true); },
  "restaurar-comandos": async (d) => { resultado(await api.restaurar_comandos(d.projeto, d.chave || "")); renderProjetos(true); },
  "recarregar-projetos": () => { depsCache = {}; renderProjetos(true); },
  deps: async (d) => {
    depsCache[d.pasta] = null;
    atualizarDeps(d.pasta);
    depsCache[d.pasta] = await api.dependencias(d.pasta);
    atualizarDeps(d.pasta);
  },
  "apagar-dep": async (d, b) => {
    const p = d.caminho.split("\\").slice(-2, -1)[0];
    if (!(await confirmar(`Apagar ${d.nome}?`, `A pasta ${esc(p)}\\${esc(d.nome)} será apagada. Dá para recriar depois com npm install ou uv sync.`, "Apagar"))) return;
    resultado(await comCarregando(b, () => api.apagar_dependencia(d.caminho)));
    const pasta = d.caminho.slice(0, d.caminho.lastIndexOf("\\"));
    delete depsCache[pasta];
    ACOES.deps({ pasta });
  },

  "docker-ligar": async () => { avisar("Ligando o Docker Desktop… pode levar um minuto."); resultado(await api.docker_ligar()); },
  "docker-desligar": async () => {
    if (!(await confirmar("Desligar o Docker Desktop?", "Todos os containers param e a memória da VM é liberada.", "Desligar"))) { renderDocker(); return; }
    resultado(await api.docker_desligar());
  },
  "docker-disco": async () => { discoCache = null; renderDocker(); discoCache = await api.docker_disco(); renderDocker(); },
  "docker-limpar": async () => {
    const r = await modal(`<div class="folha"><h3>Limpar o Docker</h3>
      <p>Remove containers parados, imagens que nenhum container usa, redes sem uso e o cache de build. Imagens removidas são baixadas de novo quando precisar.</p>
      <div class="form"><div class="grupo"><label class="item"><span class="rot">Apagar também volumes sem uso<small>Dados de bancos de containers removidos são perdidos.</small></span>
        <span class="chave"><input type="checkbox" id="lim-vol"><span></span></span></label></div></div>
      <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt vermelho" id="lim-ok" data-padrao>Limpar</button></div></div>`,
      (m, fechar) => { m.querySelector("#lim-ok").onclick = () => fechar({ vol: m.querySelector("#lim-vol").checked }); });
    if (!r) return;
    avisar("Limpando… pode demorar.");
    resultado(await api.docker_limpar(r.vol));
    ACOES["docker-disco"]();
  },

  "modo-jogo": () => abrirModoJogo(),
  config: () => abrirConfig(),
  paleta: () => abrirPaleta(),
};

// O comando usado vira o principal: recarrega a lista em segundo plano
function atualizarProjetosDepois() {
  setTimeout(async () => {
    projetosCache = await api.projetos();
    if (aba === "projetos") renderProjetos();
  }, 1200);
}

function atualizarDeps(pasta) {
  const el = document.querySelector(`[data-deps="${CSS.escape(pasta)}"]`);
  if (el) el.innerHTML = renderDeps(pasta);
}

async function abrirModoJogo() {
  if (!E) return;
  const r = E.resumo;
  const resp = await modal(`<div class="folha"><h3>Modo jogo</h3>
    <p>Para tudo de desenvolvimento para liberar memória. As ferramentas do Claude não são tocadas.</p>
    <div class="chips"><span class="chip"><b>${r.processos}</b> processos</span><span class="chip"><b>${r.containers}</b> containers</span>
      ${E.docker.vmmem_mb ? `<span class="chip">WSL <b>${ram(E.docker.vmmem_mb)}</b></span>` : ""}</div>
    <div class="form"><div class="grupo">
      <label class="item"><span class="rot">Lembrar o que está rodando<small>Depois, "Retomar" sobe tudo de novo com um clique.</small></span><span class="chave"><input type="checkbox" id="mj-lembrar" checked><span></span></span></label>
      <label class="item"><span class="rot">Desligar o Docker Desktop</span><span class="chave"><input type="checkbox" id="mj-docker" checked><span></span></span></label>
      <label class="item"><span class="rot">Desligar o WSL inteiro<small>Fecha qualquer Linux aberto no WSL.</small></span><span class="chave"><input type="checkbox" id="mj-wsl"><span></span></span></label>
    </div></div>
    <div class="rodape"><button class="bt" data-resp="nao">Cancelar</button><button class="bt vermelho" id="mj-ok" data-padrao>Parar tudo</button></div></div>`,
    (m, fechar) => { m.querySelector("#mj-ok").onclick = () => fechar({ docker: m.querySelector("#mj-docker").checked, wsl: m.querySelector("#mj-wsl").checked, lembrar: m.querySelector("#mj-lembrar").checked }); });
  if (!resp) return;
  avisar("Parando tudo…");
  resultado(await api.modo_jogo(resp.docker, resp.wsl, resp.lembrar));
}
window.abrirModoJogo = abrirModoJogo;

async function abrirConfig() {
  const c = await api.config();
  const resp = await modal(`<div class="folha"><h3>Configurações</h3><p>Dados e logs ficam em ${esc(c.pasta_dados)}.</p>
    <div class="form">
      <div class="grupo"><div class="bloco-campo"><label>Pastas de projetos <small>uma por linha; cada subpasta vira um projeto</small></label>
        <textarea class="campo mono" id="cf-pastas" rows="2">${esc((c.pastas_projetos || []).join("\n"))}</textarea></div></div>
      <div class="grupo" style="margin-top:12px">
        <label class="item"><span class="rot">Iniciar com o Windows</span><span class="chave"><input type="checkbox" id="cf-init" ${c.inicializacao ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar sobre processos órfãos</span><span class="chave"><input type="checkbox" id="cf-orfaos" ${c.alerta_orfaos ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar quando algo rodar por mais de<small>horas · 0 desliga</small></span><input class="campo" id="cf-horas" type="number" min="0" step="0.5" value="${esc(c.alerta_horas)}"></label>
        <label class="item"><span class="rot">Atualizar a cada<small>segundos</small></span><input class="campo" id="cf-int" type="number" min="1" max="60" value="${esc(c.intervalo)}"></label>
        <label class="item"><span class="rot">Atalho para abrir o painel<small>vale depois de reiniciar o app</small></span><input class="campo" id="cf-atalho" value="${esc(c.atalho)}"></label>
      </div>
      <div class="grupo" style="margin-top:12px">
        <label class="item"><span class="rot">Portas fixas<small>cada comando sempre na mesma porta</small></span><span class="chave"><input type="checkbox" id="cf-portas" ${c.portas_fixas ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Endereços com nome<small>projeto.localhost · vale depois de reiniciar o app</small></span><span class="chave"><input type="checkbox" id="cf-proxy" ${c.proxy ? "checked" : ""}><span></span></span></label>
        <label class="item"><span class="rot">Avisar servidor sem uso por<small>horas · 0 desliga</small></span><input class="campo" id="cf-ocioso" type="number" min="0" step="0.5" value="${esc(c.ocioso_horas)}"></label>
        <label class="item"><span class="rot">Buscar novidades do Git a cada<small>minutos · 0 desliga</small></span><input class="campo" id="cf-git" type="number" min="0" value="${esc(c.git_fetch_minutos)}"></label>
      </div>
      <div class="grupo" style="margin-top:12px">
        <div class="item"><span class="rot">Argos ${esc(c.versao)}<small>procura versões novas na pasta dist do projeto (OneDrive)</small></span>
          <button class="bt" data-acao="procurar-atualizacao">Atualizar</button></div>
        <div class="item"><span class="rot">Ferramenta do Claude (MCP)<small>deixa o Claude Code ver e controlar o Argos</small></span>
          <button class="bt" data-acao="conectar-claude">Conectar</button></div>
      </div>
    </div>
    <div class="rodape"><button class="bt texto perigo" id="cf-sair" style="margin-right:auto">Sair do Argos</button>
      <button class="bt" data-resp="nao">Cancelar</button><button class="bt azul" id="cf-ok" data-padrao>Salvar</button></div></div>`,
    (m, fechar) => {
      m.querySelector("#cf-sair").onclick = () => { fechar(null); api.sair(); };
      m.querySelector("#cf-ok").onclick = () => fechar({
        pastas_projetos: m.querySelector("#cf-pastas").value.split("\n").map((s) => s.trim()).filter(Boolean),
        intervalo: Math.max(1, +m.querySelector("#cf-int").value || 3),
        alerta_horas: Math.max(0, +m.querySelector("#cf-horas").value || 0),
        atalho: m.querySelector("#cf-atalho").value.trim(),
        alerta_orfaos: m.querySelector("#cf-orfaos").checked,
        inicializacao: m.querySelector("#cf-init").checked,
        portas_fixas: m.querySelector("#cf-portas").checked,
        proxy: m.querySelector("#cf-proxy").checked,
        ocioso_horas: Math.max(0, +m.querySelector("#cf-ocioso").value || 0),
        git_fetch_minutos: Math.max(0, Math.round(+m.querySelector("#cf-git").value || 0)),
      });
    });
  if (!resp) return;
  resultado(await api.salvar_config(resp));
  CFG = await api.config();
  projetosCache = null;
  if (aba === "projetos") renderProjetos(true);
}

function trocarAba(nova) {
  aba = nova;
  document.querySelectorAll("#menu button").forEach((b) => b.classList.toggle("ativo", b.dataset.aba === nova));
  document.querySelectorAll("[data-painel]").forEach((s) => (s.hidden = s.dataset.painel !== nova));
  $("#conteudo").scrollTop = 0;
  if (E) renderBarra();
  if (nova === "projetos") renderProjetos();
  else if (nova === "hoje") renderHoje();
  else if (E) render();
}

// --- paleta de comandos (Ctrl+K) ----------------------------------------

const normalizar = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

function itensPaleta() {
  const it = [];
  const add = (titulo, sub, icone, f) => it.push({ titulo, sub, icone, f });
  if (E) {
    for (const a of E.ativos.filter((a) => a.nome)) {
      add(`Parar ${a.nome}`, "projeto rodando", "parar", () => ACOES["parar-projeto"]({ nome: a.nome }));
      add(`Reiniciar ${a.nome}`, "projeto rodando", "reiniciar", () => ACOES["reiniciar-projeto"]({ nome: a.nome }));
    }
    for (const u of E.unidades.filter((u) => u.categoria !== "ferramenta")) {
      const onde = u.projeto || "sem projeto";
      if (u.gerenciado) add(`Logs: ${u.nome}`, onde, "logs", () => abrirLogs("processo", u.gerenciado, u.nome));
      for (const p of u.portas) {
        const t = u.portas_tipo?.[p];
        const rot = t === "site" ? "site " : t === "api" ? "API " : "";
        add(`Abrir ${rot}localhost:${p}`, `${onde} · ${u.nome}`, "rodando", () => api.abrir("url", `http://localhost:${p}`));
        if (t !== "api") add(`Celular: ${rot}localhost:${p}`, `${onde} · QR code`, "celular", () => abrirCelular(p, u.id));
      }
    }
    for (const c of E.docker.containers.filter((c) => c.estado === "running")) {
      add(`Logs: ${c.nome}`, "container", "logs", () => abrirLogs("container", c.id, c.nome));
    }
  }
  for (const p of projetosCache || []) {
    p.comandos.forEach((c) => add(c.tipo === "grupo" ? `Subir tudo: ${p.nome}` : c.sub ? `${c.sub}: ${c.rotulo}` : c.rotulo,
      `iniciar ${p.nome}`, "play", () => ACOES.iniciar({ projeto: p.nome, chave: c.chave })));
    add(`VS Code: ${p.nome}`, "abrir projeto", "codigo", () => api.abrir("vscode", p.pasta));
    add(`Terminal: ${p.nome}`, "abrir na pasta", "terminal", () => api.abrir("terminal", p.pasta));
    add(`Pasta: ${p.nome}`, "abrir no Explorer", "pasta", () => api.abrir("pasta", p.pasta));
  }
  if (E && E.sessao) add("Retomar sessão salva", `${E.sessao.processos + E.sessao.containers} itens · ${hora(E.sessao.quando)}`, "retomar", () => ACOES.retomar({ id: E.sessao.id }));
  add("Salvar sessão agora", "lembrar o que está rodando", "retomar", () => ACOES["salvar-sessao"]());
  if (E) {
    for (const [host, porta] of Object.entries((E.proxy && E.proxy.rotas) || {})) {
      if (/^\d/.test(host)) continue;
      add(`Abrir ${host}`, `porta ${porta}`, "mundo", () => api.abrir("url", enderecoNome(host)));
    }
    for (const u of E.unidades.filter((u) => u.categoria !== "ferramenta" && u.portas.length)) {
      add(`Link público: ${u.projeto || u.nome}`, `túnel para a porta ${portaSite(u)}`, "mundo", () => abrirTunel(portaSite(u)));
    }
  }
  for (const p of (projetosCache || []).filter((p) => p.tem_testes)) {
    add(`Testar ${p.nome}`, "rodar os testes", "teste", () => ACOES.testar({ projeto: p.nome }));
  }
  ABAS.forEach((a) => add(`Ir para ${a.rot}`, "seção", a.id, () => trocarAba(a.id)));
  if (E && E.docker.instalado) {
    if (E.docker.ligado) add("Desligar o Docker Desktop", "docker", "docker", () => ACOES["docker-desligar"]());
    else add("Ligar o Docker Desktop", "docker", "docker", () => ACOES["docker-ligar"]());
  }
  add("Modo jogo", "parar tudo e liberar memória", "jogo", () => abrirModoJogo());
  add("Configurações", "Argos", "config", () => abrirConfig());
  return it;
}

function filtrarPaleta(itens, q) {
  const palavras = normalizar(q).split(/\s+/).filter(Boolean);
  if (!palavras.length) return itens.slice(0, 40);
  return itens
    .map((i) => {
      const t = normalizar(i.titulo), s = normalizar(i.sub);
      if (!palavras.every((p) => t.includes(p) || s.includes(p))) return null;
      const nota = (t.startsWith(palavras[0]) ? 0 : 1) + (palavras.every((p) => t.includes(p)) ? 0 : 1);
      return [nota, i];
    })
    .filter(Boolean)
    .sort((a, b) => a[0] - b[0])
    .slice(0, 40)
    .map(([, i]) => i);
}

async function abrirPaleta() {
  if ($("#paleta")) return;
  const caixa = document.createElement("div");
  caixa.id = "paleta";
  caixa.innerHTML = `<div class="paleta-fundo"></div><div class="paleta" role="dialog" aria-label="Comandos">
    <label class="paleta-busca">${IC.busca}<input placeholder="Iniciar, parar, abrir, logs…" spellcheck="false"></label>
    <div class="paleta-lista" role="listbox"></div></div>`;
  document.body.appendChild(caixa);
  const input = caixa.querySelector("input"), lista = caixa.querySelector(".paleta-lista");
  let itens = itensPaleta(), vis = [], sel = 0;

  const desenhar = () => {
    vis = filtrarPaleta(itens, input.value);
    sel = Math.min(sel, Math.max(0, vis.length - 1));
    lista.innerHTML = vis.length ? vis.map((i, n) => `<div class="paleta-item ${n === sel ? "sel" : ""}" data-n="${n}" role="option">
      <span class="ic">${IC[i.icone] || ""}</span><span class="t">${esc(i.titulo)}</span><span class="s">${esc(i.sub)}</span></div>`).join("")
      : `<div class="paleta-vazio">Nada encontrado</div>`;
    lista.querySelector(".sel")?.scrollIntoView({ block: "nearest" });
  };
  const fechar = () => caixa.remove();
  const executar = (n) => { const i = vis[n]; fechar(); if (i) i.f(); };

  input.addEventListener("input", () => { sel = 0; desenhar(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); desenhar(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); desenhar(); }
    else if (e.key === "Enter") { e.preventDefault(); executar(sel); }
    else if (e.key === "Escape") { e.preventDefault(); fechar(); }
  });
  lista.addEventListener("mousemove", (e) => {
    const el = e.target.closest(".paleta-item");
    if (el && +el.dataset.n !== sel) { sel = +el.dataset.n; lista.querySelectorAll(".paleta-item").forEach((x, n) => x.classList.toggle("sel", n === sel)); }
  });
  lista.addEventListener("click", (e) => { const el = e.target.closest(".paleta-item"); if (el) executar(+el.dataset.n); });
  caixa.querySelector(".paleta-fundo").addEventListener("click", fechar);
  desenhar();
  input.focus();
  if (!projetosCache) {
    projetosCache = await api.projetos();
    if (caixa.isConnected) { itens = itensPaleta(); desenhar(); }
  }
}

// --- eventos -----------------------------------------------------------

document.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-acao]");
  if (!el || el.disabled || el.tagName === "INPUT") return;
  // Botões dentro de uma linha clicável não expandem a linha
  if (el.dataset.acao === "abrir-projeto" && ev.target.closest("button, input, select")) return;
  ev.preventDefault();
  const f = ACOES[el.dataset.acao];
  if (f) f(el.dataset, el.tagName === "BUTTON" ? el : null);
});

// Chaves (switch) disparam a ação ao mudar
document.addEventListener("change", async (ev) => {
  const el = ev.target;
  if (el.dataset.gitBranch) {
    const nome = el.dataset.gitBranch;
    const r = await api.git(nome, "checkout", el.value);
    resultado(r);
    delete extrasCache[nome];
    renderProjetos(true);
    return;
  }
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
