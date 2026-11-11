"use strict";
// Janelas de log: cores ANSI, busca, troca de serviço, várias abertas, arrastar e redimensionar.

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

let logAtual = null; // janela de log da frente (a que recebe Ctrl+F e Esc)
const RE_ERRO = /\b(error|erro|exception|traceback|failed|falhou|fatal|panic|unhandled|errno|err!)\b/i;
const semAnsi = (s) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]|\x1b[\]()][^\x07\x1b]*(\x07|\x1b\\)?/g, "");
const MAX_LINHAS_LOG = 6000;
const MAX_JANELAS_LOG = 8;
const Z_LOG = 20; // abaixo do fundo dos modais (30)

// Outros serviços do mesmo projeto (processos com log e containers): para trocar ou abrir em outra janela
function servicosDoLog(tipo, alvo) {
  if (!E || tipo === "arquivo") return [];
  const dono = tipo === "processo" ? E.unidades.find((u) => u.gerenciado === alvo) : E.docker.containers.find((c) => c.id === alvo);
  const projeto = dono && dono.projeto;
  if (!projeto) return [];
  return [
    ...E.unidades.filter((u) => u.gerenciado && u.projeto === projeto).map((u) => ({ tipo: "processo", alvo: u.gerenciado, nome: u.nome, projeto })),
    ...E.docker.containers.filter((c) => c.estado === "running" && c.projeto === projeto).map((c) => ({ tipo: "container", alvo: c.id, nome: c.nome, projeto })),
  ];
}

// --- janelas de log ----------------------------------------------------------
// Cada log abre numa janela própria dentro do painel: arrasta pela barra do topo,
// redimensiona pelo canto, e várias podem ficar abertas ao mesmo tempo.

const janelasLog = [];
let geometriaLog = null; // última posição e tamanho usados (a próxima janela começa igual)

class JanelaLog {
  constructor(tipo, alvo, nome, geo) {
    this.el = document.createElement("div");
    this.el.className = "janela-log";
    this.el.setAttribute("role", "dialog");
    this.el.innerHTML = `
      <div class="janela-topo" title="Arraste para mover">
        <div class="inspetor-info"><div class="inspetor-titulo"></div><div class="inspetor-sub"></div></div>
        <label class="busca busca-log" title="Buscar no log (Ctrl+F)">${IC.busca}<input placeholder="Buscar" spellcheck="false"><span class="achados"></span></label>
        <label class="chave-peq" title="Mostrar só as linhas com erro"><input type="checkbox" class="j-erros"><span></span>Erros</label>
        <label class="chave-peq" title="Acompanhar o final do log"><input type="checkbox" class="j-seguir" checked><span></span>Seguir</label>
        <button class="ib j-copiar" title="Copiar o log">${IC.copiar}</button>
        <button class="ib" data-acao="abrir" data-tipo="logs" data-alvo="" title="Abrir a pasta de logs">${IC.pasta}</button>
        <button class="ib j-fechar" title="Fechar (Esc)">${IC.fechar}</button>
      </div>
      <div class="log-servicos" hidden></div>
      <pre class="log"></pre>`;
    const q = (s) => this.el.querySelector(s);
    this.titulo = q(".inspetor-titulo");
    this.sub = q(".inspetor-sub");
    this.busca = q(".busca-log input");
    this.achados = q(".achados");
    this.erros = q(".j-erros");
    this.seguir = q(".j-seguir");
    this.servicos = q(".log-servicos");
    this.pre = q(".log");
    this.aberta = true;
    this.posicionar(geo);
    document.body.appendChild(this.el);

    this.el.addEventListener("pointerdown", () => this.frente(), true);
    this.busca.addEventListener("input", () => this.render(true));
    this.busca.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); this.busca.value = ""; this.render(); } });
    this.erros.addEventListener("change", () => { this.render(); this.pre.scrollTop = this.pre.scrollHeight; });
    q(".j-fechar").addEventListener("click", () => this.fechar());
    q(".j-copiar").addEventListener("click", async () => {
      const r = await api.copiar(this.pre.innerText);
      avisar(r.ok ? "Log copiado." : r.msg, !r.ok);
    });
    this.servicos.addEventListener("click", (e) => {
      const b = e.target.closest("[data-log-alvo]");
      if (!b) return;
      if (b.dataset.outra) abrirLogs(b.dataset.logTipo, b.dataset.logAlvo, b.dataset.logNome, { novaJanela: true });
      else this.trocar(b.dataset.logTipo, b.dataset.logAlvo, b.dataset.logNome);
    });
    this.arrastavel(q(".janela-topo"));
    // Tamanho mudado pelo canto: a próxima janela abre com o mesmo tamanho
    new ResizeObserver(() => { if (this.aberta && this.el.offsetWidth) geometriaLog = this.geometria(); }).observe(this.el);

    janelasLog.push(this);
    this.frente();
    this.trocar(tipo, alvo, nome);
  }

  geometria() {
    return { left: this.el.offsetLeft, top: this.el.offsetTop, width: this.el.offsetWidth, height: this.el.offsetHeight };
  }

  posicionar(g) {
    const w = Math.min(g.width, innerWidth - 16), h = Math.min(g.height, innerHeight - 16);
    Object.assign(this.el.style, {
      width: `${w}px`, height: `${h}px`,
      left: `${Math.min(Math.max(8, g.left), innerWidth - w - 8)}px`,
      top: `${Math.min(Math.max(8, g.top), innerHeight - h - 8)}px`,
    });
  }

  // Mantém pelo menos a barra do topo visível (para conseguir arrastar de volta)
  manterVisivel() {
    const r = this.el.getBoundingClientRect();
    const left = Math.min(Math.max(r.left, 80 - r.width), innerWidth - 80);
    const top = Math.min(Math.max(r.top, 0), innerHeight - 48);
    this.el.style.left = `${left}px`;
    this.el.style.top = `${top}px`;
  }

  arrastavel(barra) {
    barra.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.target.closest("button, input, label, select")) return;
      e.preventDefault();
      barra.setPointerCapture(e.pointerId);
      const x0 = e.clientX - this.el.offsetLeft, y0 = e.clientY - this.el.offsetTop;
      this.el.classList.add("movendo");
      const mover = (ev) => {
        this.el.style.left = `${ev.clientX - x0}px`;
        this.el.style.top = `${ev.clientY - y0}px`;
      };
      const soltar = () => {
        barra.removeEventListener("pointermove", mover);
        barra.removeEventListener("pointerup", soltar);
        this.el.classList.remove("movendo");
        this.manterVisivel();
        geometriaLog = this.geometria();
      };
      barra.addEventListener("pointermove", mover);
      barra.addEventListener("pointerup", soltar);
    });
  }

  frente() {
    const i = janelasLog.indexOf(this);
    if (i >= 0) janelasLog.push(...janelasLog.splice(i, 1));
    janelasLog.forEach((j, n) => { j.el.style.zIndex = Z_LOG + n; j.el.classList.toggle("ativa", j === this); });
    logAtual = this;
  }

  trocar(tipo, alvo, nome) {
    Object.assign(this, { tipo, alvo, nome, fim: -1, texto: "", pedido: (this.pedido || 0) + 1 });
    this.el.setAttribute("aria-label", `Log de ${nome}`);
    this.titulo.textContent = nome;
    this.titulo.title = nome;
    this.sub.textContent = tipo === "container" ? "container · últimas 500 linhas" : "carregando…";
    this.pre.innerHTML = "";
    this.busca.value = "";
    this.erros.checked = false;
    this.renderServicos();
    this.puxar(this.pedido);
  }

  renderServicos() {
    const lista = servicosDoLog(this.tipo, this.alvo);
    this.servicos.hidden = lista.length < 2;
    if (this.servicos.hidden) return;
    this.servicos.innerHTML = `<button class="bt texto buscar-todos" ${attr({ acao: "buscar-logs", projeto: lista[0].projeto })}
      title="Procurar um texto nos logs de todos os serviços">${IC.busca}Buscar em todos</button>` + lista.map((s) => {
      const ativo = s.alvo === this.alvo;
      const outra = janelasLog.some((j) => j !== this && j.alvo === s.alvo);
      return `<span class="servico-log ${ativo ? "ativo" : ""} ${outra ? "lado" : ""}">
        <button data-log-alvo="${esc(s.alvo)}" data-log-tipo="${esc(s.tipo)}" data-log-nome="${esc(s.nome)}" title="Ver este log nesta janela">${esc(s.nome)}</button>
        ${ativo ? "" : `<button class="dividir" data-outra="1" data-log-alvo="${esc(s.alvo)}" data-log-tipo="${esc(s.tipo)}" data-log-nome="${esc(s.nome)}"
          title="${outra ? "Já está aberto em outra janela (trazer para frente)" : "Abrir em outra janela"}">${IC.colunas}</button>`}</span>`;
    }).join("");
  }

  // Desenha o log aplicando o filtro de erros e destacando a busca
  render(rolarParaBusca = false) {
    const busca = this.busca.value.trim();
    const soErros = this.erros.checked;
    const re = busca ? new RegExp(esc(busca).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi") : null;
    let achados = 0;
    const html = [];
    for (const linha of this.texto.split("\n").slice(-MAX_LINHAS_LOG)) {
      const erro = RE_ERRO.test(semAnsi(linha));
      if (soErros && !erro) continue;
      let h = ansiParaHtml(linha);
      if (re) h = h.replace(/(^|>)([^<]+)/g, (_, a, t) => a + t.replace(re, (m) => (achados++, `<mark>${m}</mark>`)));
      html.push(erro ? `<span class="linha-erro">${h}</span>` : h);
    }
    this.pre.innerHTML = html.join("\n") || (soErros ? '<span style="opacity:.5">Nenhuma linha com erro.</span>' : "");
    this.achados.textContent = busca ? `${achados}` : "";
    if (rolarParaBusca && achados) this.pre.querySelector("mark")?.scrollIntoView({ block: "center" });
  }

  // Já com um texto na busca (ex: vindo de "Buscar em todos"): marca assim que o log chegar
  buscar(texto) {
    this.busca.value = texto;
    this.rolarNaBusca = true;
    this.render(true);
  }

  async puxar(pedido) {
    if (!this.aberta || pedido !== this.pedido) return; // fechada, ou trocou de log no meio
    try {
      const r = await api.logs(this.tipo, this.alvo, this.fim);
      if (!this.aberta || pedido !== this.pedido) return;
      const noFim = this.pre.scrollTop + this.pre.clientHeight >= this.pre.scrollHeight - 30;
      if (r.erro) this.sub.textContent = r.erro;
      else if (this.tipo !== "container") this.sub.textContent = `${r.vivo ? "rodando" : "parado"}${r.arquivo ? " · " + r.arquivo : ""}`;
      const mudou = r.substituir ? r.texto !== this.texto : !!r.texto;
      if (r.substituir) this.texto = r.texto;
      else if (r.texto) {
        this.texto += r.texto;
        if (this.texto.length > 2_000_000) this.texto = this.texto.slice(-1_000_000);
      }
      this.fim = r.fim;
      if (mudou) {
        this.render(this.rolarNaBusca);
        this.rolarNaBusca = false;
        if (!this.busca.value.trim() && (this.seguir.checked || noFim)) this.pre.scrollTop = this.pre.scrollHeight;
      }
    } catch (e) { console.error(e); }
    setTimeout(() => this.puxar(pedido), this.tipo === "container" ? 3000 : 1000);
  }

  fechar() {
    this.aberta = false;
    this.el.remove();
    janelasLog.splice(janelasLog.indexOf(this), 1);
    const topo = janelasLog[janelasLog.length - 1];
    if (topo) topo.frente(); else logAtual = null;
    janelasLog.forEach((j) => j.renderServicos());
  }
}

// Abre o log numa janela nova. Se ele já estiver aberto, traz aquela janela para frente.
function abrirLogs(tipo, alvo, nome) {
  const aberta = janelasLog.find((j) => j.alvo === alvo);
  if (aberta) { aberta.frente(); return aberta; }
  if (janelasLog.length >= MAX_JANELAS_LOG) janelasLog[0].fechar(); // a mais antiga (a de trás)
  const w = Math.min(820, innerWidth - 260), h = innerHeight - 16;
  const topo = janelasLog[janelasLog.length - 1];
  // A primeira fica onde a última foi deixada; as outras em cascata a partir da da frente
  // (32 px mais baixa, para a de trás continuar aparecendo)
  const geo = topo ? { ...topo.geometria(), left: topo.el.offsetLeft - 32, top: topo.el.offsetTop + 32,
                       height: Math.max(260, topo.el.offsetHeight - 32) }
    : geometriaLog || { left: innerWidth - w - 8, top: 8, width: w, height: h };
  const j = new JanelaLog(tipo, alvo, nome, geo);
  janelasLog.forEach((x) => x !== j && x.renderServicos());
  return j;
}

function fecharLogs() {
  [...janelasLog].forEach((j) => j.fechar());
}

window.addEventListener("resize", () => janelasLog.forEach((j) => j.manterVisivel()));
