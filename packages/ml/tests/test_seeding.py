import random

import numpy as np
import torch
from youfy_ml.seeding import seeded_generator, set_seed


def test_semeia_as_tres_fontes_de_aleatoriedade():
    set_seed(42)
    trio_a = (random.random(), float(np.random.rand()), float(torch.rand(1)))
    set_seed(42)
    trio_b = (random.random(), float(np.random.rand()), float(torch.rand(1)))
    assert trio_a == trio_b


def test_generator_semeado_e_reprodutivel():
    a = torch.randperm(100, generator=seeded_generator(3))
    b = torch.randperm(100, generator=seeded_generator(3))
    assert torch.equal(a, b)


def test_liga_algoritmos_deterministicos():
    set_seed(1)
    assert torch.are_deterministic_algorithms_enabled()
