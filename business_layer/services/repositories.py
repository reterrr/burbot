from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import SQLModel, col

from business_layer.schemas.models import (
    BusinessModel,
    BusinessModelRevision,

    BusinessEntity,
    BusinessEntityVersion,

    BusinessEntityField,
    BusinessEntityFieldVersion,

    BusinessEntityRelation,
    BusinessEntityRelationVersion,

    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)

from business_layer.schemas.models.dtos import (
    BusinessModelFilter,
    BusinessModelAdd,
    BusinessModelUpdate,

    BusinessModelRevisionFilter,
    BusinessModelRevisionAdd,
    BusinessModelRevisionUpdate,

    BusinessEntityFilter,
    BusinessEntityAdd,
    BusinessEntityUpdate,

    BusinessEntityVersionFilter,
    BusinessEntityVersionAdd,
    BusinessEntityVersionUpdate,

    BusinessEntityFieldFilter,
    BusinessEntityFieldAdd,
    BusinessEntityFieldUpdate,

    BusinessEntityFieldVersionFilter,
    BusinessEntityFieldVersionAdd,
    BusinessEntityFieldVersionUpdate,

    BusinessEntityRelationFilter,
    BusinessEntityRelationAdd,
    BusinessEntityRelationUpdate,

    BusinessEntityRelationVersionFilter,
    BusinessEntityRelationVersionAdd,
    BusinessEntityRelationVersionUpdate,

    BusinessObjectFilter,
    BusinessObjectAdd,
    BusinessObjectUpdate,

    BusinessObjectFieldFilter,
    BusinessObjectFieldAdd,
    BusinessObjectFieldUpdate,

    BusinessObjectFieldValueFilter,
    BusinessObjectFieldValueAdd,
    BusinessObjectFieldValueUpdate,
)

ModelT = TypeVar("ModelT", bound=SQLModel)
FilterT = TypeVar("FilterT", bound=SQLModel)
AddT = TypeVar("AddT", bound=SQLModel)
UpdateT = TypeVar("UpdateT", bound=SQLModel)


class BaseRepository(
    Generic[
        ModelT,
        FilterT,
        AddT,
        UpdateT,
    ]
):
    model: type[ModelT]

    def __init__(
            self,
            session: AsyncSession,
    ):
        self._session = session

    def _build_condition(
            self,
            filter_: FilterT,
    ) -> ColumnElement[bool]:
        conditions: list[ColumnElement[bool]] = []

        data = filter_.model_dump(
            exclude_unset=True,
        )

        if not data:
            raise ValueError(
                "At least one search field is required"
            )

        for field_name, value in data.items():
            attribute = getattr(
                self.model,
                field_name,
            )

            column = col(attribute)

            if value is None:
                conditions.append(
                    column.is_(None)
                )
            else:
                conditions.append(
                    column == value
                )

        return and_(*conditions)

    async def get(
            self,
            id: int,
    ) -> ModelT | None:
        return await self._session.get(
            self.model,
            id,
        )

    async def list(
            self,
            *,
            offset: int = 0,
            limit: int = 100,
    ) -> list[ModelT]:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        id_attribute = getattr(
            self.model,
            "id",
        )

        stmt = (
            select(self.model)
            .order_by(
                col(id_attribute)
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.scalars(
            stmt
        )

        return list(
            result.all()
        )

    async def count(self) -> int:
        stmt = select(
            func.count()
        ).select_from(
            self.model
        )

        result = await self._session.scalar(
            stmt
        )

        return result or 0

    async def search(
            self,
            filters: list[FilterT],
    ) -> list[ModelT]:
        if not filters:
            return []

        conditions = [
            self._build_condition(filter_)
            for filter_ in filters
        ]

        stmt = (
            select(self.model)
            .where(
                or_(*conditions)
            )
        )

        result = await self._session.scalars(
            stmt
        )

        return list(
            result.all()
        )

    async def add(
            self,
            model: AddT,
    ) -> int:
        data = model.model_dump(
            exclude_unset=True,
        )

        db_model = self.model(
            **data
        )

        self._session.add(
            db_model
        )

        await self._session.flush()

        id_ = getattr(
            db_model,
            "id",
            None,
        )

        if id_ is None:
            raise RuntimeError(
                f"{self.model.__name__} "
                f"did not receive an id after flush"
            )

        return id_

    async def update(
            self,
            id: int,
            model: UpdateT,
    ) -> ModelT:
        db_model = await self._session.get(
            self.model,
            id,
        )

        if db_model is None:
            raise LookupError(
                f"{self.model.__name__} "
                f"{id} not found"
            )

        data = model.model_dump(
            exclude_unset=True,
        )

        for field_name, value in data.items():
            setattr(
                db_model,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(
            db_model
        )

        return db_model

    async def delete(
            self,
            id: int,
    ) -> None:
        db_model = await self._session.get(
            self.model,
            id,
        )

        if db_model is None:
            raise LookupError(
                f"{self.model.__name__} "
                f"{id} not found"
            )

        await self._session.delete(
            db_model
        )

        await self._session.flush()


# ============================================================
# BusinessModel
# ============================================================

class BusinessModelRepository(
    BaseRepository[
        BusinessModel,
        BusinessModelFilter,
        BusinessModelAdd,
        BusinessModelUpdate,
    ]
):
    model = BusinessModel


# ============================================================
# BusinessModelRevision
# ============================================================

class BusinessModelRevisionsRepository(
    BaseRepository[
        BusinessModelRevision,
        BusinessModelRevisionFilter,
        BusinessModelRevisionAdd,
        BusinessModelRevisionUpdate,
    ]
):
    model = BusinessModelRevision


# ============================================================
# BusinessEntity
# ============================================================

class BusinessEntityRepository(
    BaseRepository[
        BusinessEntity,
        BusinessEntityFilter,
        BusinessEntityAdd,
        BusinessEntityUpdate,
    ]
):
    model = BusinessEntity


# ============================================================
# BusinessEntityVersion
# ============================================================

class BusinessEntityVersionsRepository(
    BaseRepository[
        BusinessEntityVersion,
        BusinessEntityVersionFilter,
        BusinessEntityVersionAdd,
        BusinessEntityVersionUpdate,
    ]
):
    model = BusinessEntityVersion


# ============================================================
# BusinessEntityField
# ============================================================

class BusinessEntityFieldsRepository(
    BaseRepository[
        BusinessEntityField,
        BusinessEntityFieldFilter,
        BusinessEntityFieldAdd,
        BusinessEntityFieldUpdate,
    ]
):
    model = BusinessEntityField


# ============================================================
# BusinessEntityFieldVersion
# ============================================================

class BusinessEntityFieldVersionsRepository(
    BaseRepository[
        BusinessEntityFieldVersion,
        BusinessEntityFieldVersionFilter,
        BusinessEntityFieldVersionAdd,
        BusinessEntityFieldVersionUpdate,
    ]
):
    model = BusinessEntityFieldVersion


# ============================================================
# BusinessEntityRelation
# ============================================================

class BusinessEntityRelationsRepository(
    BaseRepository[
        BusinessEntityRelation,
        BusinessEntityRelationFilter,
        BusinessEntityRelationAdd,
        BusinessEntityRelationUpdate,
    ]
):
    model = BusinessEntityRelation


# ============================================================
# BusinessEntityRelationVersion
# ============================================================

class BusinessEntityRelationVersionsRepository(
    BaseRepository[
        BusinessEntityRelationVersion,
        BusinessEntityRelationVersionFilter,
        BusinessEntityRelationVersionAdd,
        BusinessEntityRelationVersionUpdate,
    ]
):
    model = BusinessEntityRelationVersion


# ============================================================
# BusinessObject
# ============================================================

class BusinessObjectRepository(
    BaseRepository[
        BusinessObject,
        BusinessObjectFilter,
        BusinessObjectAdd,
        BusinessObjectUpdate,
    ]
):
    model = BusinessObject


# ============================================================
# BusinessObjectField
# ============================================================

class BusinessObjectFieldsRepository(
    BaseRepository[
        BusinessObjectField,
        BusinessObjectFieldFilter,
        BusinessObjectFieldAdd,
        BusinessObjectFieldUpdate,
    ]
):
    model = BusinessObjectField


# ============================================================
# BusinessObjectFieldValue
# ============================================================

class BusinessObjectFieldsValuesRepository(
    BaseRepository[
        BusinessObjectFieldValue,
        BusinessObjectFieldValueFilter,
        BusinessObjectFieldValueAdd,
        BusinessObjectFieldValueUpdate,
    ]
):
    model = BusinessObjectFieldValue
