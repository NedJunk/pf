from typing import Optional


def select_expert(context: dict, registry: list[str]) -> Optional[str]:
    """Return the name of the most relevant expert, or None.

    Args:
        context: dict with keys history_tail (list[str]), goals (list[str]),
                 project_map (list[str])
        registry: list of registered expert names to choose from

    Raises NotImplementedError until routing logic is implemented (Epic 4).
    """
    raise NotImplementedError(
        "Routing logic not yet implemented. "
        "See docs/superpowers/specs/2026-04-27-expert-selection-eval-design.md"
    )
