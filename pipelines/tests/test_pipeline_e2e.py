"""Atravessa ingest → featurize → split num micro-dump.

É o teste que pega o que os unitários não pegam: incompatibilidade entre
estágios e mudança de formato de artefato.
"""
import json

from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.featurize import run_featurize
from youfy_pipelines.ingest import run_ingest
from youfy_pipelines.split import run_split, splits_dir

GENEROS = ["Rock", "Jazz", "Folk"]

def _micro_dump(tmp_path):
    faixas = []
    track_id = 2
    for g, genero in enumerate(GENEROS):
        for a in range(8):                       # 8 artistas por gênero
            for _ in range(3):                   # 3 faixas por artista
                faixas.append(FixtureTrack(track_id, g * 100 + a, f"Artista {g}-{a}", genero))
                track_id += 1
    faixas.append(FixtureTrack(track_id, 999, "Artista Ruim", "Rock", corrompido=True))
    build_fma_fixture(tmp_path, faixas)
    return len(faixas)

def test_pipeline_completo_no_micro_dump(session, tmp_path):
    total = _micro_dump(tmp_path)
    data_dir = tmp_path / "data"
    spec = FeatureSpec(n_mels=16, n_frames=20)

    ingest = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert ingest.total == total
    assert ingest.failed == 1
    assert ingest.ingested == total - 1

    feat = run_featurize(session, data_dir=data_dir, spec=spec)
    session.flush()
    assert feat.computed == ingest.ingested
    assert feat.failed == 0

    splits = run_split(session, data_dir=data_dir, spec=spec, seed=42)
    assert len(splits.train) + len(splits.val) + len(splits.test) == ingest.ingested

    for nome, ids in splits.as_dict().items():
        payload = json.loads((splits_dir(data_dir, spec) / f"{nome}.json").read_text())
        assert payload["fingerprint"] == spec.fingerprint()
        assert payload["track_ids"] == ids

    # O invariante que mais importa, verificado tambem no encadeamento real.
    dono = {t.id: t.artist_id for t in session.query(Track).all()}
    conjuntos = [{dono[i] for i in ids} for ids in splits.as_dict().values()]
    assert conjuntos[0] & conjuntos[1] == set()
    assert conjuntos[0] & conjuntos[2] == set()
    assert conjuntos[1] & conjuntos[2] == set()

def test_pipeline_e_retomavel_a_partir_de_qualquer_estagio(session, tmp_path):
    _micro_dump(tmp_path)
    data_dir = tmp_path / "data"
    spec = FeatureSpec(n_mels=16, n_frames=20)

    run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    run_featurize(session, data_dir=data_dir, spec=spec)
    session.flush()

    # Reexecutar tudo não deve refazer trabalho nem mudar o resultado.
    segunda_feat = run_featurize(session, data_dir=data_dir, spec=spec)
    assert segunda_feat.computed == 0
    a = run_split(session, data_dir=data_dir, spec=spec, seed=42).as_dict()
    b = run_split(session, data_dir=data_dir, spec=spec, seed=42).as_dict()
    assert a == b
