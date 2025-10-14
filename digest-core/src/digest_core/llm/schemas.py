from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Legacy v1 models
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
    schema_version: str = "1.0"
    prompt_version: str
    digest_date: str
    trace_id: str
    sections: List[Section]


# Enhanced v2 models
class ActionItem(BaseModel):
    """Action item with evidence and quote."""
    title: str = Field(description="Brief action title")
    description: str = Field(description="Detailed description")
    evidence_id: str = Field(description="Evidence ID reference")
    quote: str = Field(description="1-2 sentence quote from evidence")
    due_date: Optional[str] = Field(None, description="ISO-8601 date or 'today'/'tomorrow'")
    due_date_normalized: Optional[str] = Field(None, description="ISO-8601 with TZ America/Sao_Paulo")
    due_date_label: Optional[str] = Field(None, description="'today'/'tomorrow' if applicable")
    actors: List[str] = Field(default_factory=list, description="People involved")
    confidence: str = Field(description="High/Medium/Low")
    response_channel: Optional[str] = Field(None, description="email/slack/meeting")


class DeadlineMeeting(BaseModel):
    """Deadline or meeting with evidence."""
    title: str
    evidence_id: str
    quote: str
    date_time: str = Field(description="ISO-8601 with TZ")
    date_label: Optional[str] = Field(None, description="'today'/'tomorrow' if applicable")
    location: Optional[str] = None
    participants: List[str] = Field(default_factory=list)


class RiskBlocker(BaseModel):
    """Risk or blocker with evidence."""
    title: str
    evidence_id: str
    quote: str
    severity: str = Field(description="High/Medium/Low")
    impact: str


class FYIItem(BaseModel):
    """FYI item with evidence."""
    title: str
    evidence_id: str
    quote: str
    category: Optional[str] = None


class EnhancedDigest(BaseModel):
    """Enhanced digest with structured sections and evidence references."""
    schema_version: str = Field(default="2.0")
    prompt_version: str
    digest_date: str
    trace_id: str
    timezone: str = Field(default="America/Sao_Paulo")
    
    # Structured sections
    my_actions: List[ActionItem] = Field(default_factory=list)
    others_actions: List[ActionItem] = Field(default_factory=list)
    deadlines_meetings: List[DeadlineMeeting] = Field(default_factory=list)
    risks_blockers: List[RiskBlocker] = Field(default_factory=list)
    fyi: List[FYIItem] = Field(default_factory=list)
    
    # Markdown summary (generated after JSON)
    markdown_summary: Optional[str] = Field(None, description="Brief markdown summary")
