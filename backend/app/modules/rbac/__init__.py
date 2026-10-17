"""RBAC 权限管理模块：角色 / 权限 / 角色-权限关联。

注意：本包 __init__ 不 import api（api 会反向 import core.auth，造成循环导入）；
api 由 main.py 直接 `from app.modules.rbac.api import router` 挂载。
"""
