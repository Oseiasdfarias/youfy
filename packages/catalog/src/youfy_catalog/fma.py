from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class FmaTrackRow:
    track_id: int
    title: str
    genre_top: str | None
    duration_s: float
    artist_id: int
    artist_name: str
    subset: str

def read_tracks_csv(path: Path, subset: str | None = None) -> list[FmaTrackRow]:
    """Lê o `tracks.csv` do FMA, que traz cabeçalho de dois níveis."""
    raw = pd.read_csv(path, index_col=0, header=[0, 1], low_memory=False)
    linhas: list[FmaTrackRow] = []
    for track_id, r in raw.iterrows():
        subset_da_linha = str(r[("set", "subset")])
        if subset is not None and subset_da_linha != subset:
            continue
        genero = r[("track", "genre_top")]
        linhas.append(
            FmaTrackRow(
                track_id=int(track_id),
                title=str(r[("track", "title")]),
                genre_top=None if _vazio(genero) else str(genero),
                duration_s=float(r[("track", "duration")]),
                artist_id=int(r[("artist", "id")]),
                artist_name=str(r[("artist", "name")]),
                subset=subset_da_linha,
            )
        )
    return linhas

def audio_path_for(track_id: int, audio_root: Path, ext: str = ".mp3") -> Path:
    """O FMA particiona os arquivos em pastas de mil: 001005 vive em `001/`."""
    return audio_root / f"{track_id // 1000:03d}" / f"{track_id:06d}{ext}"

def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor == ""
