"use strict";
// Peças comuns das listas e a aba Rodando.

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
      ${(s.falhas || []).length ? `<span class="etq vermelho" title="${esc(s.falhas.join("\n"))}">${plural(s.falhas.length, "não subiu", "não subiram")}</span>` : ""}
      <button class="bt texto" ${attr({ acao: "descartar-sessao", id: s.id })}>Descartar</button>
      <button class="bt azul" ${attr({ acao: "retomar", id: s.id })}>${(s.falhas || []).length ? "Tentar de novo" : "Retomar"}</button></div>`);
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
    partes.push(`<div class="bloco"><div class="titulo-secao">Parados recentemente</div>
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
      </div>`).join("")}</div></div>`);
  }

  const soltas = E.portas.filter((p) => !p.unidade && p.tipo !== "container");
  if (soltas.length) {
    partes.push(`<div class="bloco"><div class="titulo-secao">Outras portas abertas</div>
      <div class="grupo">${soltas.map((p) => `<div class="linha">
        <span class="ponto cinza"></span>
        <div class="linha-corpo"><div class="linha-titulo">${esc(p.programa)}</div>
          <div class="linha-sub">PID ${p.pid}<span class="p">·</span>${esc(p.acesso)}</div></div>
        <div class="linha-fim">${chipPorta(p.porta)}<div class="acoes ocultas">
          ${ib("parar", { acao: "encerrar-porta", porta: p.porta, nome: p.programa }, "Encerrar", "perigo")}</div></div>
      </div>`).join("")}</div></div>`);
  }

  aplicarBlocos($("#p-rodando"), partes);
}
