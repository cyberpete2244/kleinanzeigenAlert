from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.util import NoneType

from ebAlert.crud.base import CRUBBase
from ebAlert.ebayscrapping.ebayclass import EbayItem
from ebAlert.models.sqlmodel import EbayPost


class CRUDPost(CRUBBase):

    def add_items_to_db(self, items: List[EbayItem], db: Session, link_id: int, write_database=True) -> List[EbayItem]:
        new_items = []
        print(f'Found {str(len(items))} items.', end=' ')
        somethingchangedindb = False
        dbchangeslog = ""
        for item in items:
            db_result = self.get_by_key({"post_id": str(item.id)}, db)
            if not db_result:
                # new article
                somethingchangedindb = True
                dbchangeslog += "C"
                if write_database:
                    self.create({"post_id": str(item.id), "price": item.price, "link_id": link_id, "title": item.title}, db=db)
                new_items.append(item)
            else:
                # transition to saving link id in offers
                if type(getattr(db_result, "link_id")) is NoneType:
                    somethingchangedindb = True
                    dbchangeslog += "u"
                    if write_database:
                        self.update({"identifier": "post_id", "post_id": item.id, "link_id": link_id}, db=db)
                # there was a different price before, update it and inform
                old_price = str(getattr(db_result, "price"))
                if old_price != item.price:
                    somethingchangedindb = True
                    dbchangeslog += 'U'
                    if write_database:
                        self.update({"identifier": "post_id", "post_id": item.id, "price": item.price}, db=db)
                    item.old_price = old_price
                    new_items.append(item)
        if somethingchangedindb is True:
            print("Changes in DB:", dbchangeslog, end='')
        else:
            print('Nothing new for DB.', end='')
        return new_items


crud_post = CRUDPost(EbayPost)
