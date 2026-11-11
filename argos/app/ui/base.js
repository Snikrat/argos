"use strict";
// Utilitários, ícones, ponte com o Python, estado e ciclo de atualização.

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
    colunas: s('<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M12 5v14"/>'),
    mais: s('<path d="M12 5v14M5 12h14"/>'),
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
      historico_semana: async () => [{ projeto: "loja", dias: [0, 7200, 14400, 3600, 0, 21600, 9000], total: 55800 },
        { projeto: "clinica", dias: [3600, 0, 0, 10800, 5400, 0, 1800], total: 21600 }],
      servicos: async () => [{ nome: "db", tipo: "docker", rodando: true, depois: [] },
        { nome: "server", tipo: "processo", rodando: true, depois: ["db"] }, { nome: "web", tipo: "processo", rodando: false, depois: ["server"] }],
      buscar_logs: async (p, t) => [{ id: "aaa111", nome: "web: npm run dev", vivo: true, tipo: "processo", total: 2,
        linhas: [`[vite] ${t}: failed to resolve import "./Carrinho"`, `${t} ao recarregar src/App.tsx`] }],
      sessoes: async () => [
        { id: "p1", nome: "trabalho", motivo: "manual", quando: Date.now() / 1000 - 86400, retomada: true, falhas: [], processos: 3, containers: 1, projetos: ["clinica", "loja"] },
        { id: "s1", nome: "", motivo: "modo jogo", quando: Date.now() / 1000 - 3600, retomada: false, falhas: ["loja-db-1"], processos: 2, containers: 1, projetos: ["loja"] }],
      config: async () => dados.config || {},
      dependencias: async () => [{ nome: "node_modules", caminho: "x\\node_modules", bytes: 412000000 }],
      docker_disco: async () => [{ tipo: "Imagens", total: 12, ativos: 2, tamanho: "8.4GB", recuperavel: "6.1GB (72%)" }],
      logs: async (t, a, desde) => desde > 0 ? { texto: "", fim: desde, vivo: true } :
        { texto: "\x1b[2m=== argos: npm run dev ===\x1b[0m\n\n  \x1b[32m\x1b[1mVITE\x1b[0m \x1b[32mv5.4.2\x1b[0m  ready in \x1b[1m312\x1b[0m ms\n\n  \x1b[32m➜\x1b[0m  \x1b[1mLocal\x1b[0m:   \x1b[36mhttp://localhost:\x1b[1m5173\x1b[0m\x1b[36m/\x1b[0m\n", fim: 200, vivo: true },
      maximizar: async () => false,
      git_branches: async () => ({ atual: "main", locais: ["main", "feature/login"],
        remotas: [{ nome: "feature/pagamento", remoto: "origin", ref: "origin/feature/pagamento" }, { nome: "fix/agenda", remoto: "origin", ref: "origin/fix/agenda" }] }),
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
      <button class="ib" data-acao="sessoes" title="Sessões e perfis: salvar e retomar conjuntos de projetos">${IC.retomar}</button>
      <button class="ib" data-acao="modo-jogo" title="Modo jogo: para tudo e libera memória">${IC.jogo}</button>`;
  }
}

// Troca só os blocos que mudaram. Redesenhar tudo a cada ciclo fazia os botões
// "piscarem" debaixo do mouse e derrubava a dica e o foco do teclado.
let ultimaAcao = 0;
function aplicarBlocos(el, partes) {
  partes.forEach((html, i) => {
    const atual = el.children[i];
    if (atual && atual._html === html) return;
    // Com o mouse em cima, espera alguns ciclos (a não ser que o usuário tenha acabado de agir)
    const parado = Date.now() - ultimaAcao > 8000;
    if (atual && atual._html && parado && atual.matches(":hover") && (atual._adiado = (atual._adiado || 0) + 1) <= 4) return;
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    const novo = t.content.firstElementChild;
    novo._html = html;
    if (atual) atual.replaceWith(novo); else el.appendChild(novo);
  });
  while (el.children.length > partes.length) el.lastElementChild.remove();
}
