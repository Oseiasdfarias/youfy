"""Construtor de acervo sintetico com a forma do FMA, incluindo o cabecalho de 2 niveis.

Vive em `src/`, nao em `tests/`, porque e importado por testes de outros
pacotes -- `packages/catalog/tests/` nao e um pacote importavel.

Usa .wav em vez de .mp3 porque o `soundfile` escreve wav de forma confiável em
qualquer plataforma; a extensão é parâmetro do leitor, então o formato do teste
não vaza para produção.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf


@dataclass(frozen=True)
class FixtureTrack:
    track_id: int
    artist_id: int
    artist_name: str
    genre_top: str | None
    corrompido: bool = False

def build_fma_fixture(root: Path, faixas: list[FixtureTrack], sr: int = 22050) -> Path:
    meta_dir = root / "fma_metadata"
    audio_dir = root / "fma_small"
    meta_dir.mkdir(parents=True, exist_ok=True)

    colunas = pd.MultiIndex.from_tuples([
        ("set", "subset"), ("track", "title"), ("track", "genre_top"),
        ("track", "duration"), ("artist", "id"), ("artist", "name"),
    ])
    linhas = []
    for f in faixas:
        pasta = audio_dir / f"{f.track_id // 1000:03d}"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{f.track_id:06d}.wav"
        if f.corrompido:
            destino.write_bytes(b"RIFF" + b"\x00lixo" * 40)
        else:
            t = np.linspace(0.0, 1.0, sr, endpoint=False)
            sf.write(destino, np.sin(2 * np.pi * 440.0 * t).astype(np.float32), sr)
        genero = "" if f.genre_top is None else f.genre_top
        linhas.append(["small", f"Faixa {f.track_id}", genero, 1.0,
                       f.artist_id, f.artist_name])

    df = pd.DataFrame(linhas, columns=colunas, index=[f.track_id for f in faixas])
    df.index.name = "track_id"
    df.to_csv(meta_dir / "tracks.csv")
    return root
