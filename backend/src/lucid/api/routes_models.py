"""Model catalogue for the picker."""

from fastapi import APIRouter

from lucid.api.deps import CatalogDep
from lucid.api.schemas import ModelOptionOut, ModelsResponse

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelsResponse)
async def list_models(catalog: CatalogDep) -> ModelsResponse:
    """Models the UI may offer, with the default selection."""
    return ModelsResponse(
        items=[
            ModelOptionOut(
                id=option.id,
                label=option.label,
                provider=option.provider,
                model=option.model,
            )
            for option in catalog.options
        ],
        default_id=catalog.default_id,
    )
