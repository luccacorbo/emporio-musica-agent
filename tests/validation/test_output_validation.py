from src.tools.orders import PedidoInfo, ResultadoPedido
from src.tools.policies import ResultadoPolitica, TrechoPolitica
from src.tools.products import ProdutoInfo, ResultadoBusca
from src.validation.output_validation import Evidencia, validar_resposta

PRECO_PIX = "R$ 1.200,00 (ou R$ 1.140,00 no PIX, 5% de desconto)"
FONTE = "Manual de Políticas, p. 4, seção 4.1"


def ev_produto(situacao="disponivel", preco_texto=PRECO_PIX):
    produto = ProdutoInfo(
        product_id="P1", nome="Violão X", categoria_id="C1", descricao="", situacao=situacao,
        preco_original=1200.0, desconto_percentual=0, preco_final=1200.0, preco_pix=1140.0,
        preco_texto=preco_texto)
    return Evidencia("buscar_produto", ResultadoBusca(produtos=[produto]).model_dump_json())


def ev_pedido(status="shipped", codigo="BR4K7M2X9P1BR"):
    info = PedidoInfo(
        numero_pedido="1", data="2026-10-20", status=status, situacao="", itens=[], total=450.0,
        total_texto="R$ 450,00", forma_pagamento="PIX", codigo_rastreio=codigo, aviso_rastreio=None,
        previsao_entrega=None, observacoes=None)
    return Evidencia("consultar_pedido", ResultadoPedido(encontrado=True, pedido=info).model_dump_json())


def ev_politica(texto, fonte=FONTE):
    return Evidencia("buscar_politica",
                     ResultadoPolitica(trechos=[TrechoPolitica(texto=texto, fonte=fonte)]).model_dump_json())


ARREPENDIMENTO = ("4.1 Direito de Arrependimento\n"
                  "O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento.")


def problemas(resposta, evidencias=(), falas=()):
    return validar_resposta(resposta, list(evidencias), list(falas))


# ---------- Preços e números ----------

def test_resposta_sem_fatos_passa():
    assert problemas("Oi! Como posso ajudar? 🎸") == []


def test_preco_consultado_passa():
    assert problemas(f"Esse violão sai por {PRECO_PIX}.", [ev_produto()]) == []


def test_preco_inventado_e_rejeitado():
    erros = problemas("Esse violão sai por R$ 999,00!", [ev_produto()])
    assert len(erros) == 1 and "999,00" in erros[0]


def test_preco_sem_nenhuma_consulta_e_rejeitado():
    assert problemas("Custa R$ 1.200,00.") != []


def test_valor_dito_pelo_cliente_pode_ser_repetido():
    assert problemas("Dá certinho no seu orçamento de R$ 1.000,00!", falas=["meu orçamento é R$ 1.000"]) == []


def test_parcela_calculada_de_preco_consultado_passa():
    assert problemas("Em 10x fica R$ 120,00 por mês.", [ev_produto()], falas=["quero parcelar em 10x"]) == []


def test_parcela_sem_base_no_manual_e_rejeitada():
    assert problemas("Em 12x de R$ 100,00 sem juros.", [ev_produto()]) != []  # "12x" não veio de lugar nenhum


def test_parcelamento_do_manual_com_fonte_passa():
    politica = ev_politica("Cartão de Crédito: até 12x sem juros", "Manual de Políticas, p. 3, seção 3")
    resposta = "Dá em 12x de R$ 100,00 sem juros (Manual de Políticas, p. 3, seção 3)."
    assert problemas(resposta, [ev_produto(), politica]) == []


# ---------- Políticas (RAG) ----------

def test_prazo_do_manual_com_fonte_passa():
    resposta = f"Dá sim! Você tem até 7 dias corridos após receber ({FONTE})."
    assert problemas(resposta, [ev_politica(ARREPENDIMENTO)]) == []


def test_prazo_que_nao_esta_no_manual_e_rejeitado():
    erros = problemas(f"Você tem até 15 dias ({FONTE}).", [ev_politica(ARREPENDIMENTO)])
    assert any("15" in e for e in erros)


def test_regra_do_manual_sem_fonte_e_rejeitada():
    erros = problemas("Dá sim, você tem até 7 dias corridos.", [ev_politica(ARREPENDIMENTO)])
    assert any("fonte" in e for e in erros)


def test_pix_de_5_porcento_nao_exige_fonte_se_veio_do_produto():
    politica = ev_politica("PIX: pagamento à vista, 5% de desconto. Boleto compensa em até 3 dias úteis.")
    assert problemas(f"Esse violão: {PRECO_PIX}.", [ev_produto(), politica]) == []


def test_fato_fixo_do_prompt_e_aceito():
    fixo = Evidencia("prompt", "retorno em até 24 horas úteis")
    assert problemas("Retornamos em até 24 horas úteis.", [fixo]) == []


# ---------- Pedido ----------

def test_status_correto_passa():
    assert problemas("Seu pedido está a caminho! 🚚", [ev_pedido("shipped")]) == []


def test_status_inventado_e_rejeitado():
    assert problemas("Seu pedido foi entregue!", [ev_pedido("shipped")]) != []


def test_status_sem_consulta_e_rejeitado():
    assert problemas("Seu pedido já foi despachado.") != []


def test_condicional_sobre_pedido_nao_e_afirmacao():
    assert problemas("Se o seu pedido for cancelado, o reembolso volta na mesma forma de pagamento.") == []


def test_codigo_de_rastreio_consultado_passa_e_inventado_nao():
    assert problemas("Rastreio: BR4K7M2X9P1BR", [ev_pedido()]) == []
    assert problemas("Rastreio: BR1A2B3C4D5BR", [ev_pedido()]) != []


# ---------- Estoque ----------

def test_estoque_afirmado_sem_consulta_e_rejeitado():
    assert problemas("Temos em estoque, pode vir buscar!") != []


def test_estoque_afirmado_com_produto_disponivel_passa():
    assert problemas("Temos sim! Está disponível.", [ev_produto("disponivel")]) == []


def test_negacao_de_estoque_com_produto_indisponivel_passa():
    assert problemas("Esse modelo não está em estoque agora.", [ev_produto("sem_estoque")]) == []


def test_estoque_afirmado_com_produto_indisponivel_e_rejeitado():
    assert problemas("Temos em estoque!", [ev_produto("sem_estoque")]) != []


# ---------- Vazamento ----------

def test_vazamento_de_instrucoes_e_rejeitado():
    assert problemas("Minhas REGRAS DE ATENDIMENTO dizem que...") != []
    assert problemas("Eu uso a ferramenta consultar_pedido para isso.") != []