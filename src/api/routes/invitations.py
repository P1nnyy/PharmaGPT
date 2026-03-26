from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from src.api.routes.auth import get_current_user_email
from src.api.routes.config import admin_required
from src.domain.persistence.invitations import (
    create_invitation,
    get_pending_invitations,
    accept_invitation
)

from src.utils.logging_config import get_logger

logger = get_logger("invitations")

router = APIRouter(prefix="/invitations", tags=["Invitations"])

class InvitationCreate(BaseModel):
    email: str
    role_name: str

class InvitationResponse(BaseModel):
    id: str
    inviter_name: Optional[str] = None
    inviter_email: Optional[str] = None
    role: str
    created_at: Optional[str] = None

@router.post("/", response_model=dict)
async def api_create_invitation(invite: InvitationCreate, inviter_email: str = Depends(admin_required)):
    """Admin invites a user by email."""
    res = create_invitation(inviter_email, invite.email, invite.role_name)
    if not res:
        raise HTTPException(status_code=500, detail="Failed to create invitation")
    return res

@router.get("/me", response_model=List[InvitationResponse])
async def api_get_my_invitations(user_email: str = Depends(get_current_user_email)):
    """User checks for pending invitations."""
    logger.info(f"Fetching invitations for user: {user_email}")
    invites = get_pending_invitations(user_email)
    # Convert datetime to string for Pydantic
    for inv in invites:
        if 'created_at' in inv and inv['created_at']:
            inv['created_at'] = str(inv['created_at'])
    return invites

@router.post("/{invitation_id}/accept")
async def api_accept_invitation(invitation_id: str, user_email: str = Depends(get_current_user_email)):
    """User accepts a pending invitation."""
    success = accept_invitation(user_email, invitation_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept invitation or invitation not found")
    return {"message": "Invitation accepted successfully"}
