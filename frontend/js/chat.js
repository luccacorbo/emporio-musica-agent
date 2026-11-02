const ENDPOINT = "/api/chat";
const SAUDACAO = "Olá, como posso ajudar?";

// Uma conversa nova a cada carregamento da página: o que se vê na tela é o que o servidor lembra.
const conversaId = (crypto.randomUUID?.() ?? `c-${Date.now()}-${Math.random().toString(16).slice(2)}`);

const lista = document.getElementById("mensagens");
const form = document.getElementById("form");
const campo = document.getElementById("texto");
const botao = form.querySelector("button");

function adicionar(texto, tipo) {
  const el = document.createElement("div");
  el.className = `msg ${tipo}`;
  el.textContent = texto; // textContent (nunca innerHTML): a resposta não pode injetar HTML
  lista.appendChild(el);
  lista.scrollTop = lista.scrollHeight;
  return el;
}

function mostrarDigitando() {
  const el = document.createElement("div");
  el.className = "msg agente digitando";
  el.innerHTML = "<span></span><span></span><span></span>"; // HTML fixo, sem dados externos
  lista.appendChild(el);
  lista.scrollTop = lista.scrollHeight;
  return el;
}

function bloquear(ocupado) {
  campo.disabled = ocupado;
  botao.disabled = ocupado;
  if (!ocupado) campo.focus();
}

async function enviar(texto) {
  adicionar(texto, "cliente");
  bloquear(true);
  const digitando = mostrarDigitando();
  try {
    const resp = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensagem: texto, conversa_id: conversaId }),
    });
    const dados = await resp.json().catch(() => ({}));
    digitando.remove();
    if (resp.ok) {
      adicionar(dados.resposta, "agente");
    } else {
      const detalhe = typeof dados.detail === "string"
        ? dados.detail
        : "Não consegui processar essa mensagem. Tente de novo.";
      adicionar(detalhe, "agente erro");
    }
  } catch {
    digitando.remove();
    adicionar("Não consegui falar com o servidor. Confira a conexão e tente de novo.", "agente erro");
  } finally {
    bloquear(false);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const texto = campo.value.trim();
  if (!texto) return;
  campo.value = "";
  enviar(texto);
});

adicionar(SAUDACAO, "agente");