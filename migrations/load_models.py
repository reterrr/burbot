def _load_business_models() -> None:
    from business_layer.schemas import models as _b_models  # noqa: F401


def _load_sources_models() -> None:
    from sources.schemas import models as _src_models  # noqa: F401


def _load_tasks_models() -> None:
    from tasks.schemas import models as _tasks_models  # noqa: F401


def _load_extraction_models() -> None:
    from extraction.schemas import models as _extraction_models  # noqa: F401


def load_models() -> None:
    _load_business_models()
    _load_sources_models()
    _load_tasks_models()
    _load_extraction_models()

    # Layer 2 owns the observation pointers but Layer 3 owns the target table.
    # Complete that reference cycle only after all models are registered.
    from sources.schemas.models import register_evidence_references

    if not register_evidence_references():
        raise RuntimeError("Layer 3 field_observations model was not registered")
