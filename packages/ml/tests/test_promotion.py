import pytest
from youfy_ml.evaluate import Metrics
from youfy_ml.promotion import should_promote


def _m(f1: float) -> Metrics:
    return Metrics(macro_f1=f1, accuracy=f1, per_class_f1={}, confusion=[])


def test_sem_campeao_promove_acima_do_piso():
    d = should_promote(_m(0.41), None)
    assert d.promote is True
    assert d.champion_f1 is None
    assert "piso" in d.reason


def test_sem_campeao_rejeita_abaixo_do_piso():
    assert should_promote(_m(0.39), None).promote is False


def test_sem_campeao_o_piso_e_inclusivo():
    assert should_promote(_m(0.40), None).promote is True


def test_promove_quando_supera_o_campeao_pela_margem():
    assert should_promote(_m(0.705), _m(0.70)).promote is True


def test_rejeita_empate_com_o_campeao():
    d = should_promote(_m(0.70), _m(0.70))
    assert d.promote is False
    assert "margem" in d.reason


def test_rejeita_ganho_dentro_da_margem():
    """0,4 p.p. de ganho é ruído de seed, não melhoria. Promover aqui trocaria
    o campeão por acaso e envenenaria toda comparação futura."""
    assert should_promote(_m(0.704), _m(0.70)).promote is False


def test_a_margem_e_inclusiva_no_limite_exato():
    assert should_promote(_m(0.705), _m(0.700)).promote is True


def test_rejeita_quando_pior_que_o_campeao():
    assert should_promote(_m(0.60), _m(0.70)).promote is False


def test_com_campeao_o_piso_nao_se_aplica():
    """Campeão fraco não trava a sucessão: o critério passa a ser relativo."""
    assert should_promote(_m(0.31), _m(0.30)).promote is True


def test_decisao_carrega_os_dois_numeros_para_o_relatorio():
    d = should_promote(_m(0.80), _m(0.70))
    assert d.challenger_f1 == pytest.approx(0.80)
    assert d.champion_f1 == pytest.approx(0.70)


def test_margem_e_piso_sao_configuraveis():
    assert should_promote(_m(0.71), _m(0.70), margin=0.05).promote is False
    assert should_promote(_m(0.50), None, floor=0.60).promote is False
