"""Product roles. Exactly one system admin, appointed only by manage.py."""

from __future__ import annotations

ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_OPS_ADMIN = "ops_admin"
ROLE_USER = "user"
ROLE_VIP = "vip"

ASSIGNABLE_ROLES = frozenset({ROLE_OPS_ADMIN, ROLE_VIP, ROLE_USER})
STAFF_ROLES = frozenset({ROLE_SYSTEM_ADMIN, ROLE_OPS_ADMIN})

ROLE_LABELS = {
    ROLE_SYSTEM_ADMIN: "系统管理员",
    ROLE_OPS_ADMIN: "运维管理员",
    ROLE_USER: "普通用户",
    ROLE_VIP: "VIP",
}


def is_staff_role(role: str | None) -> bool:
    return role in STAFF_ROLES


def is_system_admin_role(role: str | None) -> bool:
    return role == ROLE_SYSTEM_ADMIN
