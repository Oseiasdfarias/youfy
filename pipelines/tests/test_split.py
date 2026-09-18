from hypothesis import given, settings
from hypothesis import strategies as st
from youfy_pipelines.split import TrackRef, make_splits


def _refs(por_artista: dict[str, tuple[str, int]]) -> list[TrackRef]:
    saida = []
    for artista, (genero, n) in por_artista.items():
        saida += [TrackRef(f"t:{artista}:{i}", artista, genero) for i in range(n)]
    return saida


def test_nenhum_artista_cruza_splits():
    refs = _refs({f"a{i}": ("Rock" if i % 2 else "Jazz", 3) for i in range(40)})
    s = make_splits(refs, seed=7)
    por_split = {
        nome: {r.artist_id for r in refs if r.track_id in set(ids)}
        for nome, ids in s.as_dict().items()
    }
    assert por_split["train"] & por_split["test"] == set()
    assert por_split["train"] & por_split["val"] == set()
    assert por_split["val"] & por_split["test"] == set()


def test_toda_faixa_e_atribuida_exatamente_uma_vez():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(30)})
    s = make_splits(refs, seed=1)
    todos = s.train + s.val + s.test
    assert len(todos) == len(refs)
    assert set(todos) == {r.track_id for r in refs}


def test_e_deterministico_para_a_mesma_seed():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(30)})
    assert make_splits(refs, seed=42).as_dict() == make_splits(refs, seed=42).as_dict()


def test_seeds_diferentes_produzem_particoes_diferentes():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(60)})
    assert make_splits(refs, seed=1).as_dict() != make_splits(refs, seed=2).as_dict()


def test_proporcoes_ficam_perto_do_alvo_com_artistas_suficientes():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(100)})
    s = make_splits(refs, seed=3, ratios=(0.7, 0.15, 0.15))
    total = len(refs)
    assert abs(len(s.train) / total - 0.70) < 0.10
    assert abs(len(s.test) / total - 0.15) < 0.10


@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=59),          # índice do artista
            st.sampled_from(["Rock", "Jazz", "Folk"]),        # gênero
            st.integers(min_value=1, max_value=5),            # faixas do artista
        ),
        min_size=20,
        max_size=60,
    )
)
def test_propriedade_disjuncao_de_artista_vale_para_qualquer_acervo(tuplas):
    """A disjunção não pode depender da forma do acervo — é invariante."""
    por_artista: dict[str, tuple[str, int]] = {}
    for idx, genero, n in tuplas:
        por_artista.setdefault(f"a{idx}", (genero, n))
    refs = _refs(por_artista)
    s = make_splits(refs, seed=11)
    indice = {r.track_id: r.artist_id for r in refs}
    conjuntos = [{indice[i] for i in ids} for ids in s.as_dict().values()]
    for i in range(len(conjuntos)):
        for j in range(i + 1, len(conjuntos)):
            assert conjuntos[i] & conjuntos[j] == set()
