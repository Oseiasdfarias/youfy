class NoProductionModel(Exception):
    """Nao ha versao sob o alias de producao para o modelo pedido."""


class FeatureSpecMismatch(Exception):
    """A FeatureSpec do artefato diverge da config do featurizer."""
