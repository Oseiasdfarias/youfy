from __future__ import annotations

import os
import random

import numpy as np
import torch


def set_seed(seed: int) -> None:
    """Semeia tudo e liga algoritmos determinísticos.

    Sem isso o critério de reprodutibilidade da spec (±0,002 de macro-F1) não
    se sustenta: a ordem do dataloader e os kernels do cuDNN variam entre
    execuções e a métrica se move sozinha.
    """
    # Exigido pelo cuBLAS quando algoritmos determinísticos estão ligados.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def seeded_generator(seed: int) -> torch.Generator:
    g = torch.Generator()
    g.manual_seed(seed)
    return g


def worker_init(worker_id: int) -> None:
    semente = torch.initial_seed() % 2**32
    np.random.seed(semente + worker_id)
    random.seed(semente + worker_id)
