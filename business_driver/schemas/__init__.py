"""Business schema package.

The v2 logical meta/data model lives in :mod:`business_driver.schemas.meta`.
The pre-v2 API models remain available from their explicit modules
(`schemas.api`, `schemas.entities`, `schemas.enums`) during migration.
"""

from business_driver.schemas import meta

__all__ = ["meta"]
