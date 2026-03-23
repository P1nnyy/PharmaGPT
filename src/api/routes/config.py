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
from src.services.database import get_db_driver

async def admin_required(user_email: str = Depends(get_current_user_email)):
    """Dependency to enforce Admin role."""
    driver = get_db_driver()
    query = "MATCH (u:User {email: $email})-[:HAS_ROLE]->(r:Role) RETURN r.name as role"
    with driver.session() as session:
        result = session.execute_read(lambda tx: tx.run(query, email=user_email).single())
        if not result or result["role"] != "Admin":
            raise HTTPException(status_code=403, detail="Not authorized. Admin role required.")
    return user_email

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

class RoleCreate(BaseModel):
    name: str
    permissions: List[str] = []

class RoleResponse(BaseModel):
    name: str
    permissions: List[str]

class UserRoleAssign(BaseModel):
    email: str
    role_name: str

# --- Endpoints: ITEM CATEGORIES ---

@router.post("/categories", response_model=ItemCategoryResponse)
async def api_create_category(category: ItemCategoryCreate, user_email: str = Depends(admin_required)):
    """Create a new item category for the frontend configuration, assigned to the user. (Admin Only)"""
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
        
        # Stringify created_at for Pydantic validation
        if 'created_at' in created and created['created_at']:
            created['created_at'] = str(created['created_at'])
            
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
async def api_configure_category(category_name: str, config: ItemCategoryConfigUpdate, user_email: str = Depends(admin_required)):
    """Upsert user-specific parameters for a category. (Admin Only)"""
    config_dict = config.model_dump(exclude_unset=True) if hasattr(config, 'model_dump') else config.dict(exclude_unset=True)
    result = configure_category(user_email, category_name, config_dict)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to update configuration.")
    return result

@router.delete("/categories/{category_name}")
async def api_delete_category(category_name: str, user_email: str = Depends(admin_required)):
    """Removes a specific category. (Admin Only)"""
    success = delete_item_category(category_name)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found or could not be deleted.")
    return {"message": f"Category {category_name} deleted."}

# --- Endpoints: ROLES ---

@router.post("/roles", response_model=RoleResponse)
async def api_create_role(role: RoleCreate, admin_email: str = Depends(admin_required)):
    """Create a new system role. (Admin Only)"""
    try:
        created = create_system_role(role.name, role.permissions)
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/roles", response_model=List[RoleResponse])
async def api_get_roles(user_email: str = Depends(get_current_user_email)):
    """Retrieve all system roles."""
    try:
        return get_all_system_roles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/assign-role")
async def api_assign_role(assignment: UserRoleAssign, admin_email: str = Depends(admin_required)):
    """Assigns a system role to a user. (Admin Only)"""
    try:
        success = assign_user_role(assignment.email, assignment.role_name)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to assign role.")
        return {"message": f"Assigned role {assignment.role_name} to user {assignment.email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
