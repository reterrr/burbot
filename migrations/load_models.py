def _load_business_models() -> None:
    from business_layer.schemas import models as _b_models  # noqa: F401


def _load_sources_models() -> None:
    from sources.schemas import models as _src_models  # noqa


def _load_tasks_models() -> None:
    from tasks.schemas import models as _tasks_models  # noqa


def load_models() -> None:
    _load_business_models()
    _load_sources_models()
    _load_tasks_models()

# Import Layer 3 here when implemented, before completing its reference cycle.
# register_evidence_references()
