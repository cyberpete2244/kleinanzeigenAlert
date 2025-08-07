from contextlib import contextmanager
from typing import Dict, Any, List, TypeVar, Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from ebayAlert import create_logger
from ebayAlert.db.db import Session_klein
from ebayAlert.models.sqlmodel import Base, Search, SearchType

log = create_logger(__name__)

Model = TypeVar("Model", bound=Base)


@contextmanager
def get_session():
    session = Session_klein()
    try:
        yield session
    except Exception as e:
        session.rollback()
        log.error(e)
    else:
        session.commit()
    # finally:
    #     session.close()


class CRUDBase:
    def __init__(self, model):
        self.model = model

    def get_all(self, db: Session) -> Optional[List[Model]]:
        results = db.execute(select(self.model).order_by(
            self.model.search_type.asc(), self.model.price_low.desc(), self.model.price_target.desc()
                                                         )).scalars().all()
        return results

    def get_by_key(self, key_mapping: Dict[str, str], db: Session) -> Optional[Model]:
        clean_dict = self._get_clean_dict(key_mapping)
        if not clean_dict:
            return
        results = db.execute(select(self.model).filter_by(**clean_dict).limit(1)).first()
        if results:
            return results[0]

    def get_all_matching(self, key_mapping: Dict[str, str], db: Session) -> Optional[Model]:
        clean_dict = self._get_clean_dict(key_mapping)
        if not clean_dict:
            return
        results = db.execute(select(self.model).filter_by(**clean_dict)).scalars().all()
        return results

    def create(self, items: Dict[str, Any], db: Session) -> Optional[Model]:
        clean_dict = self._get_clean_dict(items)
        if not clean_dict:
            return
        item = self.model(**clean_dict)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update(self, items: Dict[str, Any], db: Session) -> Optional[Model]:
        identifier = items.get("identifier")
        clean_dict = self._get_clean_dict(items)
        if not clean_dict:
            return
        item = self.model(**clean_dict)
        for x in items:
            if x != "identifier" and x != identifier:
                db.query(self.model)\
                    .filter(getattr(self.model, identifier) == getattr(item, identifier))\
                    .update({x: getattr(item, x)})
                db.commit()
        return item

    def remove(self, id: int, db: Session) -> Optional[bool]:
        item = db.get(self.model, id)
        if item:
            db.delete(item)
            db.commit()
            return True

    def clear_database(self, db: Session) -> None:
        db.execute(delete(self.model).where(self.model.id >= 0).execution_options(synchronize_session="fetch"))
        db.commit()

    def _get_clean_dict(self, obj_in: Dict[str, str]):
        new_object = {}
        for key, value in obj_in.items():
            if key in self.model.__dict__.keys():
                new_object[key] = value
        return new_object


crud_search = CRUDBase(Search)
crud_search_type = CRUDBase(SearchType)
