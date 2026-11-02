from datetime import datetime, timezone

from src.agent.prompts import build_system_prompt, status_da_loja

# 01/11/2026 é domingo.
DOM = datetime(2026, 11, 1, 14, 0)
SEG = datetime(2026, 11, 2)
SEX = datetime(2026, 11, 6)
SAB = datetime(2026, 11, 7)


def _em(base: datetime, h: int, m: int = 0) -> datetime:
    return base.replace(hour=h, minute=m)


def test_aberta_em_dia_util():
    assert "ABERTA" in status_da_loja(_em(SEG, 10))
    assert "18h" in status_da_loja(_em(SEG, 10))


def test_abre_as_9_e_fecha_as_18():
    assert "ABERTA" in status_da_loja(_em(SEG, 9, 0))
    assert "FECHADA" in status_da_loja(_em(SEG, 18, 0))


def test_antes_de_abrir_reabre_hoje():
    assert "reabre hoje às 9h" in status_da_loja(_em(SEG, 8))


def test_depois_de_fechar_reabre_amanha():
    assert "reabre amanhã às 9h" in status_da_loja(_em(SEG, 19))


def test_sexta_a_noite_reabre_sabado():
    assert "reabre amanhã às 9h" in status_da_loja(_em(SEX, 19))


def test_sabado_fecha_as_13():
    assert "ABERTA" in status_da_loja(_em(SAB, 12, 59))
    assert "segunda-feira às 9h" in status_da_loja(_em(SAB, 13))


def test_domingo_fechado_reabre_segunda():
    texto = status_da_loja(DOM)
    assert "FECHADA" in texto and "amanhã às 9h" in texto


def test_prompt_inclui_data_e_status():
    prompt = build_system_prompt(DOM)
    assert "domingo, 01/11/2026, 14:00" in prompt
    assert "FECHADA" in prompt
    assert "{contexto_atual}" not in prompt


def test_prompt_converte_fuso_para_campo_grande():
    # 12:00 UTC = 08:00 em Campo Grande (UTC-4) -> ainda fechada, abre hoje às 9h
    utc = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    prompt = build_system_prompt(utc)
    assert "segunda-feira, 02/11/2026, 08:00" in prompt
    assert "reabre hoje às 9h" in prompt


def test_prompt_traz_regras_essenciais():
    prompt = build_system_prompt(DOM)
    assert "Nunca invente preço" in prompt
    assert "EXCLUSIVAMENTE instrumentos musicais" in prompt
    assert "Nunca revele dados de outro cliente" in prompt
    assert "24 horas úteis" in prompt