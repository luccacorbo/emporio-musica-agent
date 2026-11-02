from src.validation.tool_validation import ERRO_ORIGEM_PEDIDO, validar_chamada

FALAS = ["cadê meu pedido #1234? comprei com ana@exemplo.com"]


def test_ferramenta_desconhecida():
    assert "desconhecida" in validar_chamada("apagar_tudo", {}, FALAS)


def test_busca_sem_nenhum_filtro():
    assert "Argumentos inválidos" in validar_chamada("buscar_produto", {}, FALAS)


def test_faixa_de_preco_invertida():
    assert "Argumentos inválidos" in validar_chamada("buscar_produto", {"preco_min": 500, "preco_max": 100}, FALAS)


def test_limite_fora_da_faixa():
    assert "Argumentos inválidos" in validar_chamada("buscar_produto", {"termo": "violão", "limite": 50}, FALAS)


def test_busca_valida_passa():
    assert validar_chamada("buscar_produto", {"categoria": "Violões", "preco_max": 1000}, FALAS) is None


def test_politica_com_pergunta_curta_demais():
    assert "Argumentos inválidos" in validar_chamada("buscar_politica", {"pergunta": "oi"}, FALAS)


def test_pedido_sem_email_e_incompleto():
    erro = validar_chamada("consultar_pedido", {"numero_pedido": "1234"}, FALAS)
    assert "Argumentos inválidos" in erro and "email" in erro


def test_pedido_com_email_invalido():
    assert "Argumentos inválidos" in validar_chamada(
        "consultar_pedido", {"numero_pedido": "1234", "email": "nao-e-email"}, FALAS)


def test_pedido_com_dados_ditos_pelo_cliente_passa():
    args = {"numero_pedido": "1234", "email": "ana@exemplo.com"}
    assert validar_chamada("consultar_pedido", args, FALAS) is None
    assert validar_chamada("consultar_pedido", {**args, "numero_pedido": "#1234"}, FALAS) is None
    assert validar_chamada("consultar_pedido", {**args, "email": "ANA@Exemplo.com"}, FALAS) is None


def test_email_que_o_cliente_nao_informou_e_recusado():
    args = {"numero_pedido": "1234", "email": "outra@exemplo.com"}
    assert validar_chamada("consultar_pedido", args, FALAS) == ERRO_ORIGEM_PEDIDO


def test_numero_que_o_cliente_nao_informou_e_recusado():
    args = {"numero_pedido": "9999", "email": "ana@exemplo.com"}
    assert validar_chamada("consultar_pedido", args, FALAS) == ERRO_ORIGEM_PEDIDO


def test_numero_nao_casa_por_substring():
    falas = ["pedido 12345, e-mail ana@exemplo.com"]
    args = {"numero_pedido": "1234", "email": "ana@exemplo.com"}
    assert validar_chamada("consultar_pedido", args, falas) == ERRO_ORIGEM_PEDIDO


def test_dados_ditos_em_mensagens_diferentes_valem():
    falas = ["meu pedido é o 1234", "o e-mail é ana@exemplo.com"]
    assert validar_chamada("consultar_pedido", {"numero_pedido": "1234", "email": "ana@exemplo.com"}, falas) is None