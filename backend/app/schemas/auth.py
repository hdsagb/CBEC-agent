from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    """自助注册请求。

    不接收 role：注册接口只能创建 merchandiser 账号，
    admin / customs 需通过运维脚本 app.scripts.create_user 预置，
    避免任何人自助提权。
    """

    username: str
    password: str
    display_name: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    status: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
