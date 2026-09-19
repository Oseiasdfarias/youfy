from __future__ import annotations

from dataclasses import dataclass

from .evaluate import Metrics


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promote: bool
    reason: str
    challenger_f1: float
    champion_f1: float | None


def should_promote(
    challenger: Metrics,
    champion: Metrics | None,
    *,
    margin: float = 0.005,
    floor: float = 0.40,
) -> PromotionDecision:
    """Gate de promoção da spec, §5.1.

    A margem existe para não trocar o campeão por ruído de seed: um ganho de
    0,4 p.p. entre duas execuções não é melhoria, e promover em cima disso
    envenena toda comparação futura.
    """
    desafiante = challenger.macro_f1

    if champion is None:
        aprovado = desafiante >= floor
        return PromotionDecision(
            promote=aprovado,
            reason=(
                f"sem campeao; macro_f1={desafiante:.4f} "
                f"{'atinge' if aprovado else 'nao atinge'} o piso de {floor:.4f}"
            ),
            challenger_f1=desafiante,
            champion_f1=None,
        )

    vigente = champion.macro_f1
    exigido = vigente + margin
    aprovado = desafiante >= exigido
    return PromotionDecision(
        promote=aprovado,
        reason=(
            f"macro_f1={desafiante:.4f} contra campeao={vigente:.4f}; "
            f"{'supera' if aprovado else 'nao supera'} a margem de {margin:.4f} "
            f"(exigido >= {exigido:.4f})"
        ),
        challenger_f1=desafiante,
        champion_f1=vigente,
    )
