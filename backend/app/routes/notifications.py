"""
backend/app/routes/notifications.py — Phase 6
─────────────────────────────────────────────────────────────────
GET    /notifications
PATCH  /notifications/{id}/read
PATCH  /notifications/read-all
DELETE /notifications/{id}

All require JWT (get_current_user). Every query is scoped to
current_user.id — a user can never see, mark-read, or delete
another user's notifications, and no route trusts a user_id
supplied by the client.
─────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import NotificationTable, UserTable
from app.services.auth import get_current_user

router = APIRouter()


def _notif_to_dict(n: NotificationTable) -> dict:
    return {
        "id":             n.id,
        "opportunity_id": n.opportunity_id,
        "type":           n.type,
        "title":          n.title,
        "message":        n.message,
        "match_score":    n.match_score,
        "is_read":        bool(n.is_read),
        "created_at":     n.created_at.isoformat() if n.created_at else None,
    }


@router.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    """Newest first. Only this user's notifications."""
    rows = (
        db.query(NotificationTable)
        .filter(NotificationTable.user_id == current_user.id)
        .order_by(NotificationTable.created_at.desc())
        .all()
    )
    notifications = [_notif_to_dict(n) for n in rows]
    unread_count = sum(1 for n in notifications if not n["is_read"])
    return {
        "count": len(notifications),
        "unread_count": unread_count,
        "notifications": notifications,
    }


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    notif = (
        db.query(NotificationTable)
        .filter(
            NotificationTable.id == notification_id,
            NotificationTable.user_id == current_user.id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update notification")

    return {"success": True, "id": notification_id, "is_read": True}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    rows = (
        db.query(NotificationTable)
        .filter(
            NotificationTable.user_id == current_user.id,
            NotificationTable.is_read == 0,
        )
        .all()
    )
    for n in rows:
        n.is_read = 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update notifications")

    return {"success": True, "updated": len(rows)}


@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    notif = (
        db.query(NotificationTable)
        .filter(
            NotificationTable.id == notification_id,
            NotificationTable.user_id == current_user.id,
        )
        .first()
    )
    if not notif:
        return {"success": False, "message": "Notification not found", "id": notification_id}

    try:
        db.delete(notif)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not delete notification")

    return {"success": True, "id": notification_id}
