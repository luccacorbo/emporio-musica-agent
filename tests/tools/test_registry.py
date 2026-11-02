import json

from src.tools.registry import Ferramentas


class RetrieverFalso:
    def search(self, _pergunta):
        return []


def _ferramentas(fake_repos):
    return Ferramentas(fake_repos, RetrieverFalso())


def test_specs_expoem_as_quatro_ferramentas(fake_repos):
    nomes = {s["function"]["name"] for s in _ferramentas(fake_repos).specs}
    assert nomes == {"buscar_produto", "consultar_disponibilidade", "consultar_pedido", "buscar_politica"}


def test_specs_no_formato_openai(fake_repos):
    for spec in _ferramentas(fake_repos).specs:
        assert spec["type"] == "function"
        assert spec["function"]["description"]
        assert spec["function"]["parameters"]["type"] == "object"


def test_schema_simplificado_sem_anyof_nem_title(fake_repos):
    texto = json.dumps(_ferramentas(fake_repos).specs)
    assert "anyOf" not in texto and '"title"' not in texto and '"default": null' not in texto


def test_campos_opcionais_nao_sao_obrigatorios(fake_repos):
    busca = next(s for s in _ferramentas(fake_repos).specs if s["function"]["name"] == "buscar_produto")
    params = busca["function"]["parameters"]
    assert params["properties"]["preco_max"]["type"] == "number"
    assert "preco_max" not in params.get("required", [])


def test_executar_pedido_inexistente_devolve_json(fake_repos):
    saida = _ferramentas(fake_repos).executar("consultar_pedido", {"numero_pedido": "X999", "email": "a@exemplo.com"})
    assert json.loads(saida)["encontrado"] is False


def test_executar_politica_sem_trechos_orienta_a_nao_inventar(fake_repos):
    saida = json.loads(_ferramentas(fake_repos).executar("buscar_politica", {"pergunta": "posso devolver?"}))
    assert saida["trechos"] == [] and "Não invente" in saida["mensagem"]