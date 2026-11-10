"use strict";
// Aba Hoje: histórico do dia e da semana.

// --- hoje ----------------------------------------------------------------

let periodoHoje = "hoje";
const seletorPeriodo = () => `<div class="segmentos" style="margin:0 0 14px">
  <button class="${periodoHoje === "hoje" ? "ativo" : ""}" data-acao="periodo" data-periodo="hoje">Hoje</button>
  <button class="${periodoHoje === "semana" ? "ativo" : ""}" data-acao="periodo" data-periodo="semana">7 dias</button></div>`;

async function renderSemana() {
  const el = $("#p-hoje");
  const linhas = await api.historico_semana();
  if (!linhas.length) { el.innerHTML = seletorPeriodo() + vazio("hoje", "Nada nos últimos 7 dias", "O histórico é gravado enquanto o Argos está aberto."); return; }
  const dias = [...Array(7)].map((_, n) => new Date(Date.now() - (6 - n) * 86400000).toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", ""));
  const max = Math.max(...linhas.flatMap((l) => l.dias), 1);
  el.innerHTML = `${seletorPeriodo()}<div class="titulo-secao">Tempo por projeto, por dia</div>
    <div class="grupo">${linhas.map((l) => `<div class="linha">
      <div class="linha-corpo"><div class="linha-titulo">${esc(l.projeto)}</div><div class="linha-sub">${duracao(l.total)} na semana</div></div>
      <div class="linha-fim"><div class="semana">${l.dias.map((s, n) => `<div class="dia" title="${esc(dias[n])}: ${s >= 60 ? duracao(s) : "nada"}">
        <i style="height:${s >= 60 ? Math.max(8, (s / max) * 100) : 0}%"></i><span>${esc(dias[n][0].toUpperCase())}</span></div>`).join("")}</div></div>
    </div>`).join("")}</div>`;
}

async function renderHoje() {
  if (periodoHoje === "semana") return renderSemana();
  const el = $("#p-hoje");
  const itens = await api.historico();
  if (!itens.length) {
    el.innerHTML = seletorPeriodo() + vazio("hoje", "Nada registrado hoje", "O histórico é gravado enquanto o Argos está aberto.");
    return;
  }
  const por = {};
  for (const i of itens) por[i.projeto || "sem projeto"] = (por[i.projeto || "sem projeto"] || 0) + i.duracao;
  const ordem = Object.entries(por).sort((a, b) => b[1] - a[1]);
  const max = ordem[0][1] || 1;
  el.innerHTML = `${seletorPeriodo()}
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
