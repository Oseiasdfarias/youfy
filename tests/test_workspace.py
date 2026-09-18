import importlib


def test_os_tres_pacotes_sao_importaveis():
    for mod in ("youfy_audio", "youfy_catalog", "youfy_pipelines"):
        assert importlib.import_module(mod) is not None

def test_audio_nao_importa_catalog_nem_pipelines():
    """A fronteira do pacote `audio` é verificada, não confiada."""
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1] / "packages/audio/src"
    fontes = "\n".join(p.read_text() for p in raiz.rglob("*.py"))
    assert "youfy_catalog" not in fontes
    assert "youfy_pipelines" not in fontes
