import torch
from youfy_ml.model import GenreCNN
from youfy_ml.seeding import set_seed


def test_forward_devolve_logits_por_classe():
    modelo = GenreCNN(n_classes=8)
    saida = modelo(torch.zeros(4, 1, 16, 20))
    assert saida.shape == (4, 8)


def test_e_independente_das_dimensoes_do_melspec():
    """AdaptiveAvgPool na saída: mudar a FeatureSpec não exige mexer na cabeça."""
    modelo = GenreCNN(n_classes=8)
    assert modelo(torch.zeros(2, 1, 16, 20)).shape == (2, 8)
    assert modelo(torch.zeros(2, 1, 128, 1292)).shape == (2, 8)


def test_mesma_seed_produz_os_mesmos_pesos_iniciais():
    set_seed(7)
    a = GenreCNN(n_classes=8)
    set_seed(7)
    b = GenreCNN(n_classes=8)
    for pa, pb in zip(a.parameters(), b.parameters()):
        assert torch.equal(pa, pb)


def test_seeds_diferentes_produzem_pesos_diferentes():
    set_seed(1)
    a = GenreCNN(n_classes=8)
    set_seed(2)
    b = GenreCNN(n_classes=8)
    assert not all(torch.equal(pa, pb) for pa, pb in zip(a.parameters(), b.parameters()))


def test_em_modo_eval_aceita_batch_unitario():
    """BatchNorm em treino estoura com batch 1; o serving sempre prediz de um em um."""
    modelo = GenreCNN(n_classes=8)
    modelo.eval()
    with torch.no_grad():
        assert modelo(torch.zeros(1, 1, 16, 20)).shape == (1, 8)
