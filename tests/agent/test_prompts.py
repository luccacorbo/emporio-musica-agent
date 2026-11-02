from datetime import datetime

from src.agent.prompts import FUSO, build_system_prompt, contexto_temporal, loja_aberta


def _dt(dia: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, dia, h, m, tzinfo=FUSO)  # 01/11/2026 é domingo


def test_sabado_de_manha_aberta():
    assert loja_aberta(_dt(7, 10))
    assert "até 13:00" in contexto_temporal(_dt(7, 10))


def test_sabado_depois_das_13_fechada_e_volta_segunda():
    assert not loja_aberta(_dt(7, 14))
    assert "segunda-feira às 09:00" in contexto_temporal(_dt(7, 14))


def test_domingo_fechada_volta_amanha():
    assert not loja_aberta(_dt(1, 12))
    assert "amanhã às 09:00" in contexto_temporal(_dt(1, 12))


def test_sexta_as_18_ja_esta_fechada():
    assert not loja_aberta(_dt(6, 18))
    assert "amanhã às 09:00" in contexto_temporal(_dt(6, 18))  # sábado


def test_segunda_antes_de_abrir_volta_hoje():
    assert "hoje às 09:00" in contexto_temporal(_dt(2, 8, 59))


def test_prompt_sem_ferramentas_do_chat_de_terminal_tem_persona_e_horario():
    prompt = build_system_prompt(_dt(2, 10))
    assert "Empório da Música" in prompt and "Agora:" in prompt
    assert "REGRAS DE ATENDIMENTO" not in prompt