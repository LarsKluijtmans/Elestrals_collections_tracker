"""Saved views — story 021.

A saved view is a named filter set, sort and density. The interesting constraint is that the stored
filters must be *the same shape the URL serialises*, so a view and a shared link cannot drift into
meaning different things. `FilterSet` owns that shape; this only stores and returns it.

Round-tripping through `FilterSet` on the way in is what enforces it: a request that tries to store
an unrecognised filter has the unrecognised part dropped at save time rather than at apply time, so
what a view restores is exactly what it stored.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.saved_view import DENSITIES, SavedView
from .collection_filters import DEFAULT_SORT, SORTS, FilterSet, InvalidFilter
from .inventory_service import InventoryError

MAX_VIEWS_PER_USER = 50


class ViewNotFound(InventoryError):
    code = "saved_view_not_found"
    status = 404


class DuplicateViewName(InventoryError):
    code = "saved_view_name_taken"
    status = 409


class TooManyViews(InventoryError):
    code = "too_many_saved_views"
    status = 400


class SavedViewService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_sub: str) -> list[SavedView]:
        return list(
            self._db.scalars(
                select(SavedView)
                .where(SavedView.user_sub == user_sub)
                .order_by(SavedView.name.asc())
            )
        )

    def create(
        self, user_sub: str, *, name: str, filters: FilterSet,
        sort: str = DEFAULT_SORT, density: str = "comfortable",
    ) -> SavedView:
        name = (name or "").strip()
        if not name:
            raise InvalidFilter("a view needs a name")
        self._validate(sort, density)

        if len(self.list_for_user(user_sub)) >= MAX_VIEWS_PER_USER:
            raise TooManyViews(f"at most {MAX_VIEWS_PER_USER} saved views")
        if self._by_name(user_sub, name) is not None:
            # Caught here rather than left to the unique constraint, so the caller gets a 409 with
            # a sentence rather than an IntegrityError with a constraint name in it.
            raise DuplicateViewName(f"you already have a view called {name!r}")

        view = SavedView(
            user_sub=user_sub, name=name, filters=filters.to_json(),
            sort=sort, density=density,
        )
        self._db.add(view)
        self._db.commit()
        return view

    def update(
        self, user_sub: str, view_id: str, *, name: str | None = None,
        filters: FilterSet | None = None, sort: str | None = None, density: str | None = None,
    ) -> SavedView:
        view = self.get(user_sub, view_id)

        if name is not None:
            name = name.strip()
            if not name:
                raise InvalidFilter("a view needs a name")
            clash = self._by_name(user_sub, name)
            if clash is not None and clash.id != view.id:
                raise DuplicateViewName(f"you already have a view called {name!r}")
            view.name = name

        if sort is not None or density is not None:
            self._validate(sort or view.sort, density or view.density)
        if sort is not None:
            view.sort = sort
        if density is not None:
            view.density = density
        if filters is not None:
            view.filters = filters.to_json()

        self._db.commit()
        return view

    def get(self, user_sub: str, view_id: str) -> SavedView:
        """Owner-scoped, and a miss is a 404 — never a 403. Same rule as every other user-owned
        row: distinguishing "gone" from "not yours" is an enumeration oracle."""
        view = self._db.scalar(
            select(SavedView).where(
                SavedView.user_sub == user_sub, SavedView.id == view_id
            )
        )
        if view is None:
            raise ViewNotFound(view_id)
        return view

    def delete(self, user_sub: str, view_id: str) -> None:
        view = self.get(user_sub, view_id)
        self._db.delete(view)
        self._db.commit()

    def _by_name(self, user_sub: str, name: str) -> SavedView | None:
        return self._db.scalar(
            select(SavedView).where(SavedView.user_sub == user_sub, SavedView.name == name)
        )

    @staticmethod
    def _validate(sort: str, density: str) -> None:
        if sort not in SORTS:
            raise InvalidFilter(f"unknown sort {sort!r}")
        if density not in DENSITIES:
            raise InvalidFilter(f"unknown density {density!r}")
