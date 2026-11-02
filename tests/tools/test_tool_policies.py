import pytest
from pydantic import ValidationError

from src.rag.models import PolicyChunk
from src.tools.policies import BuscaPoliticaInput, buscar_politica

CHUNK = PolicyChunk(text="Devolução em até 7 dias corridos.", page=4,
                    section="4. Trocas > 4.1 Arrependimento", section_id="4.1", score=0.9)


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks, self.perguntas = chunks, []

    def search(self, question):
        self.perguntas.append(question)
        return self.chunks


def test_devolve_trechos_com_fonte():
    r = buscar_politica(FakeRetriever([CHUNK]), BuscaPoliticaInput(pergunta="posso devolver?"))
    assert r.trechos[0].texto == CHUNK.text
    assert r.trechos[0].fonte == CHUNK.source


def test_pergunta_e_limpa_antes_de_buscar():
    retriever = FakeRetriever([CHUNK])
    buscar_politica(retriever, BuscaPoliticaInput(pergunta="  posso devolver?  "))
    assert retriever.perguntas == ["posso devolver?"]


def test_sem_trechos_orienta_a_nao_inventar():
    r = buscar_politica(FakeRetriever([]), BuscaPoliticaInput(pergunta="regra inexistente"))
    assert r.trechos == [] and "não invente" in r.mensagem.lower()


@pytest.mark.parametrize("pergunta", ["", "  ", "a", "x" * 501])
def test_pergunta_invalida(pergunta):
    with pytest.raises(ValidationError):
        BuscaPoliticaInput(pergunta=pergunta)