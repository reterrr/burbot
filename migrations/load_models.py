def _load_business_models() -> None:
    from business_layer.schemas import models as _models  # noqa: F401


def load_models() -> None:
    _load_business_models()
    from sources.schemas.models import register_evidence_references

    # Import Layer 3 here when implemented, before completing its reference cycle.
    register_evidence_references()
