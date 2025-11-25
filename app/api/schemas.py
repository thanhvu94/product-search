from pydantic import BaseModel
from typing import Optional

class ProductMetadata(BaseModel):
    id: Optional[str] = None
    gender: Optional[str] = None
    masterCategory: Optional[str] = None
    subCategory: Optional[str] = None
    articleType: Optional[str] = None
    baseColour: Optional[str] = None
    season: Optional[str] = None
    year: Optional[int] = None
    usage: Optional[str] = None
    productDisplayName: Optional[str] = None