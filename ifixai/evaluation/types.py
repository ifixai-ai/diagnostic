from pydantic import BaseModel


class ModelDescriptor(BaseModel):

    model_config = {"protected_namespaces": ()}

    provider: str
    model_id: str
    version: str
    family: str | None = None
