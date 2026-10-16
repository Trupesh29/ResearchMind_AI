from pydantic import BaseModel, Field, field_validator, model_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    description: str | None = Field(default=None, max_length=2000, description="Optional description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Workspace name cannot be empty or whitespace only.")
        if len(trimmed) > 255:
            raise ValueError("Workspace name cannot exceed 255 characters.")
        return trimmed


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Workspace name cannot be empty or whitespace only.")
        if len(trimmed) > 255:
            raise ValueError("Workspace name cannot exceed 255 characters.")
        return trimmed

    @model_validator(mode="after")
    def validate_has_update(self) -> "WorkspaceUpdate":
        if self.name is None and self.description is None:
            raise ValueError("At least one field ('name' or 'description') must be provided for update.")
        return self


class ActiveIndexInfo(BaseModel):
    model_name: str
    version: int = 1


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: str
    paper_count: int = 0
    ready_count: int = 0

    model_config = {"from_attributes": True}


class WorkspaceDetailResponse(WorkspaceResponse):
    active_index: ActiveIndexInfo | None = None


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    next_cursor: str | None = None
    total_count: int = 0
