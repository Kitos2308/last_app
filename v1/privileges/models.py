from typing import Optional, List, Any

from pydantic import BaseModel, validator


class CardModel(BaseModel):
    def __init__(self, **data: Any):
        for key in self.__private_attributes__.keys():
            self.__setattr__(key, data.get(key[1:]))
        super().__init__(**data)

    class Config:
        underscore_attrs_are_private = True
        fields = {'card_type': 'type'}

    @validator('masked_bin', pre=True)
    def expire_date_validator(cls, v):
        return v[-4:]

    id: int
    masked_bin: Optional[str]
    card_type: Optional[str]
    _hash_value: str
    _binding_id: str

    @property
    def hash_value(self):
        return self._hash_value

    @property
    def binding_id(self):
        return self._binding_id


class CardsModel(BaseModel):
    cards: List[CardModel]
