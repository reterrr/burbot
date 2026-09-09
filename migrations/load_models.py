def _load_business_models() -> None:
    from business_layer.schemas import models as _models  # noqa: F401


def load_models() -> None:
    _load_business_models()
    from sources.schemas import models as _source_models  # noqa: F401
