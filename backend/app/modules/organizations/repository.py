from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.organizations.model import Department


def list_departments(db: Session) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name, Department.id)).all())


def get_department(db: Session, department_id: str) -> Department | None:
    return db.get(Department, department_id)


def department_user_count(db: Session, department_id: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(User).where(User.department_id == department_id))
        or 0
    )


def get_department_ids_in_subtree(db: Session, root_id: str) -> set[str]:
    departments = db.execute(select(Department.id, Department.parent_id)).all()
    children: dict[str, list[str]] = {}
    for department_id, parent_id in departments:
        if parent_id is not None:
            children.setdefault(parent_id, []).append(department_id)
    result = {root_id}
    pending = [root_id]
    while pending:
        current = pending.pop()
        for child_id in children.get(current, []):
            if child_id not in result:
                result.add(child_id)
                pending.append(child_id)
    return result
