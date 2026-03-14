from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from src.domain.persistence.config import (
    create_item_category,
    get_user_categories,
    delete_item_category,
    configure_category,
    create_system_role,
    get_all_system_roles,
    assign_user_role
)
from src.api.routes.auth import get_current_user_email

router = APIRouter(prefix="/config", tags=["Configuration & Admin Backoffice"])

# --- Models ---
class ItemCategoryCreate(BaseModel):
    name: str
    base_unit: str
    supports_atomic: bool
    description: Optional[str] = ""
    parent_name: Optional[str] = None

class ItemCategoryConfigUpdate(BaseModel):
    supports_atomic_sizing: Optional[bool] = None
    units: Optional[List[str]] = None

class ItemCategoryResponse(BaseModel):
    name: str
    description: str
    created_at: Optional[str] = None
    parent_name: Optional[str] = None
    is_default: bool = False
    supports_atomic_sizing: bool = False
    base_unit: str = "Unit"
    units: List[str] = []

class SystemRoleCreate(BaseModel):
    name: str
    permissions: List[str] = []

class SystemRoleResponse(BaseModel):
    name: str
    permissions: List[str]

class UserRoleAssign(BaseModel):
    email: str
    role_name: str

# --- Endpoints: ITEM CATEGORIES ---

@router.post("/categories", response_model=ItemCategoryResponse)
async def api_create_category(category: ItemCategoryCreate, user_email: str = Depends(get_current_user_email)):
    """Create a new item category for the frontend configuration, assigned to the user."""
    try:
        created = create_item_category(
            category.name, 
            category.base_unit, 
            category.supports_atomic, 
            category.description, 
            category.parent_name, 
            user_email
        )
        if not created:
            raise HTTPException(status_code=400, detail="Failed to create category.")
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=List[ItemCategoryResponse])
async def api_get_categories(user_email: str = Depends(get_current_user_email)):
    """Retrieve all configured item categories for the user (including defaults)."""
    try:
        categories = get_user_categories(user_email)
        for c in categories:
            if 'created_at' in c and c['created_at']:
                c['created_at'] = str(c['created_at'])
        return categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/categories/{category_name}/config")
async def api_configure_category(category_name: str, config: ItemCategoryConfigUpdate, user_email: str = Depends(get_current_user_email)):
    """Upsert user-specific parameters for a category."""
    config_dict = config.model_dump(exclude_unset=True) if hasattr(config, 'model_dump') else config.dict(exclude_unset=True)
    result = configure_category(user_email, category_name, config_dict)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to update configuration.")
    return result

@router.delete("/categories/{category_name}")
async def api_delete_category(category_name: str, user_email: str = Depends(get_current_user_email)):
    """Removes a specific category."""
    # (Optional) Add a check to ensure user owns the category before deleting it.
    success = delete_item_category(category_name)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found or could not be deleted.")
    return {"message": f"Category {category_name} deleted."}

# --- Endpoints: ROLES ---

@router.post("/roles", response_model=SystemRoleResponse)
async def api_create_role(role: SystemRoleCreate):
    """Create a new system role."""
    try:
        created = create_system_role(role.name, role.permissions)
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/roles", response_model=List[SystemRoleResponse])
async def api_get_roles():
    """Retrieve all system roles."""
    try:
        return get_all_system_roles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/assign-role")
async def api_assign_role(assignment: UserRoleAssign):
    """Assigns a system role to a user."""
    try:
        success = assign_user_role(assignment.email, assignment.role_name)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to assign role.")
        return {"message": f"Assigned role {assignment.role_name} to user {assignment.email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
