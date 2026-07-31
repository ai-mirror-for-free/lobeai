from services.NewAPIClient import NewAPIClient
from fastapi import HTTPException, Depends
from tools.RequestVaild import AdminAuthRequest

# NewAPI 管理员 role 值
ADMIN_ROLE = 100


async def get_admin_client(request: AdminAuthRequest) -> NewAPIClient:
    """
    FastAPI 依赖函数：验证管理员身份并返回已认证的 NewAPIClient 实例

    用法:
        @app.post("/api/admin/...")
        async def some_admin_endpoint(admin_client: NewAPIClient = Depends(get_admin_client)):
            # 直接使用 admin_client
            ...

    Args:
        request: 包含 username 和 password 的请求体

    Returns:
        已登录的 NewAPIClient 实例

    Raises:
        HTTPException: 非管理员用户或认证失败时抛出
    """
    admin_client = NewAPIClient()
    try:
        admin_client.session.headers.pop("New-Api-User", None)
        admin_client.session.cookies.clear()
        resp = admin_client.session.post(
            f"{admin_client.base_url}/api/user/login",
            json={"username": request.username, "password": request.password},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise HTTPException(status_code=401, detail=data.get("message", "登录失败"))
        user_data = data.get("data", {})
        # 兼容新版 new-api（嵌套 user 对象）和老版（直接平铺 id/role）
        user_obj = user_data.get("user") or user_data
        user_id = user_obj.get("id")
        user_role = user_obj.get("role")

        # 验证是否为管理员
        if user_role != ADMIN_ROLE:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：需要管理员权限（role={ADMIN_ROLE}），当前用户 id={user_id} role={user_role}。"
                   f"若 role 应为 {ADMIN_ROLE} 而显示 None，请检查 new-api 登录响应结构。"
            )

        access_token = user_data.get("access_token")
        if access_token:
            admin_client.session.headers.update(
                {"Authorization": f"Bearer {access_token}"}
            )
        elif user_id:
            # 兼容老版（无 access_token 回退 New-Api-User header）
            admin_client.session.headers.update({"New-Api-User": str(user_id)})
        return admin_client
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"管理员认证失败: {e}")