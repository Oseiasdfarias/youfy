from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature, Track

log = structlog.get_logger()

NOMES = ("train", "val", "test")


@dataclass(frozen=True, slots=True)
class TrackRef:
    track_id: str
    artist_id: str
    genre: str


@dataclass
class Splits:
    train: list[str] = field(default_factory=list)
    val: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"train": self.train, "val": self.val, "test": self.test}


def make_splits(
    refs: list[TrackRef],
    *,
    seed: int,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> Splits:
    """Particiona por artista, estratificando por gênero.

    Guloso por déficit: cada artista vai para o split que está mais abaixo da
    sua cota naquele gênero. A disjunção de artista sai por construção, já que
    um artista é atribuído uma única vez.
    """
    rng = random.Random(seed)
    saida = Splits()
    destinos = {"train": saida.train, "val": saida.val, "test": saida.test}

    por_genero: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in refs:
        por_genero[r.genre][r.artist_id].append(r.track_id)

    for genero in sorted(por_genero):
        artistas = por_genero[genero]
        total_do_genero = sum(len(v) for v in artistas.values())
        alvos = {nome: total_do_genero * p for nome, p in zip(NOMES, ratios)}
        atual = {nome: 0 for nome in NOMES}

        # Embaralha com a seed e depois ordena por tamanho. O sort do Python e
        # estavel, entao o embaralhamento sobrevive como criterio de desempate.
        ordem = sorted(artistas)
        rng.shuffle(ordem)
        ordem.sort(key=lambda a: -len(artistas[a]))

        for artista in ordem:
            escolhido = max(NOMES, key=lambda nome: (alvos[nome] - atual[nome], nome))
            faixas = sorted(artistas[artista])
            destinos[escolhido].extend(faixas)
            atual[escolhido] += len(faixas)

    for nome in NOMES:
        destinos[nome].sort()
    return saida


def splits_dir(data_dir: Path, spec: FeatureSpec) -> Path:
    return data_dir / "splits" / spec.fingerprint()


def run_split(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    seed: int = 42,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> Splits:
    linhas = session.execute(
        select(Track.id, Track.artist_id, Track.top_genre)
        .join(Feature, Feature.track_id == Track.id)
        .where(Feature.spec_fingerprint == spec.fingerprint())
        .where(Feature.status == "ok")
        .where(Track.top_genre.is_not(None))
    ).all()
    refs = [TrackRef(tid, aid, genero) for tid, aid, genero in linhas]

    splits = make_splits(refs, seed=seed, ratios=ratios)
    destino = splits_dir(data_dir, spec)
    destino.mkdir(parents=True, exist_ok=True)
    for nome, ids in splits.as_dict().items():
        (destino / f"{nome}.json").write_text(
            json.dumps({"seed": seed, "fingerprint": spec.fingerprint(), "track_ids": ids}, indent=2)
        )

    log.info(
        "split.concluido",
        seed=seed,
        train=len(splits.train),
        val=len(splits.val),
        test=len(splits.test),
    )
    return splits
