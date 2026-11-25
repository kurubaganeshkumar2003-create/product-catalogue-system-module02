from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator

ALLOWED_STOCK = {"IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK"}
ALLOWED_STATUS = {"DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"}


class ProductCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stock_status: str = Field(default="IN_STOCK")
    status: str = Field(default="ACTIVE")
    image_url: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None

    @field_validator("external_id", "title", "brand")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank")
        return cleaned

    @field_validator("stock_status")
    @classmethod
    def validate_stock(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in ALLOWED_STOCK:
            raise ValueError(f"stock_status must be one of {ALLOWED_STOCK}")
        return val

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in ALLOWED_STATUS:
            raise ValueError(f"status must be one of {ALLOWED_STATUS}")
        return val


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    stock_status: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None
    slug: str = Field(..., min_length=1, max_length=120)