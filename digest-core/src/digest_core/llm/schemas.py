from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Item(BaseModel):
    title: str
    owners_masked: List[str] = Field(default_factory=list)
    due: Optional[str] = None
    evidence_id: str
    confidence: float
    source_ref: Dict[str, Any]

class Section(BaseModel):
    title: str
    items: List[Item]

class Digest(BaseModel):
    digest_date: str
    trace_id: str
    sections: List[Section]
