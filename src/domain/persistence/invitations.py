from src.services.database import get_db_driver
import uuid
import logging

logger = logging.getLogger(__name__)

def create_invitation(inviter_email: str, invitee_email: str, role_name: str) -> dict:
    """Creates a pending invitation for a user to join the inviter's context with a specific role."""
    query = """
    MATCH (inviter:User {email: $inviter_email})
    MERGE (invitee:User {email: $invitee_email})
    MERGE (inviter)-[rel:INVITED_USER]->(invitee)
    SET rel.role = $role,
        rel.status = 'PENDING',
        rel.invitation_id = $id,
        rel.created_at = datetime()
    RETURN { id: rel.invitation_id, role: rel.role, status: rel.status, invitee_email: invitee.email } as invitation
    """
    id = str(uuid.uuid4())
    db = get_db_driver()
    try:
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, inviter_email=inviter_email, invitee_email=invitee_email, role=role_name, id=id).single())
            return record["invitation"] if record else None
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        return None

def get_pending_invitations(user_email: str) -> list:
    """Gets all pending invitations for a specific user."""
    query = """
    MATCH (inviter:User)-[rel:INVITED_USER {email: $email, status: 'PENDING'}]->(u:User {email: $email})
    RETURN { 
        id: rel.id, 
        inviter_name: inviter.name, 
        inviter_email: inviter.email, 
        role: rel.role, 
        created_at: rel.created_at 
    } as invitation
    """
    # Wait, the relationship is (inviter)-[:INVITED_USER]->(invitee)
    query = """
    MATCH (inviter:User)-[rel:INVITED_USER]->(u:User {email: $email})
    WHERE rel.status = 'PENDING'
    RETURN { 
        id: coalesce(rel.invitation_id, 'missing-id'), 
        inviter_name: coalesce(inviter.name, inviter.email, 'System'), 
        inviter_email: coalesce(inviter.email, 'unknown@system'), 
        role: coalesce(rel.role, 'Member'), 
        created_at: rel.created_at 
    } as invitation
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            return session.execute_read(lambda tx: [dict(rec["invitation"]) for rec in tx.run(query, email=user_email)])
    except Exception as e:
        logger.error(f"Error fetching invitations: {e}")
        return []

def accept_invitation(user_email: str, invitation_id: str) -> bool:
    """Accepts an invitation and converts it to a HAS_ROLE relationship."""
    query = """
    MATCH (inviter:User)-[rel:INVITED_USER {invitation_id: $id}]->(u:User {email: $email})
    MATCH (r:Role {name: rel.role})
    OPTIONAL MATCH (inviter)-[:OWNS_SHOP]->(s:Shop)
    
    // 1. Mark invitation as ACCEPTED
    SET rel.status = 'ACCEPTED', rel.accepted_at = datetime()
    
    // 2. Grant the role
    MERGE (u)-[:HAS_ROLE]->(r)
    
    // 3. Link to Shop (if inviter has one)
    FOREACH (shop IN CASE WHEN s IS NOT NULL THEN [s] ELSE [] END |
        MERGE (u)-[:WORKS_AT]->(shop)
    )
    
    RETURN u, r
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, email=user_email, id=invitation_id).single())
            return True if record else False
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        return False
