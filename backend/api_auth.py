"""
认证相关API
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from database import get_db, User, Task
import uuid
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

router = APIRouter(prefix="/auth", tags=["认证"])

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # 实际应用中应该使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2密码承载令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# 工具函数
def verify_password(plain_password, hashed_password):
    """验证密码"""
    # 由于我们暂时使用明文密码，这里直接比较
    # 实际应用中应该使用 pwd_context.verify(plain_password, hashed_password)
    return plain_password == hashed_password

def get_password_hash(password):
    """获取密码哈希值"""
    # 实际应用中应该使用 pwd_context.hash(password)
    return password

def create_access_token(data: dict, expires_delta: timedelta = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# API端点
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.user_id, "is_admin": user.is_admin}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "is_admin": user.is_admin
        }
    }

@router.post("/register")
async def register(
    username: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db)
):
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    new_user = User(
        user_id=str(uuid.uuid4()),
        username=username,
        password=get_password_hash(password),
        is_admin=False  # 注册的用户默认为非管理员
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "success": True,
        "message": "注册成功",
        "user": {
            "user_id": new_user.user_id,
            "username": new_user.username,
            "is_admin": new_user.is_admin
        }
    }

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at
    }

@router.get("/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    """获取任务列表"""
    tasks = db.query(Task).all()
    return {
        "tasks": [
            {
                "task_id": task.task_id,
                "task_name": task.task_name,
                "description": task.description,
                "is_default": task.is_default,
                "created_at": task.created_at
            }
            for task in tasks
        ]
    }


# 用户管理API（仅管理员可访问）
@router.get("/users")
async def get_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户列表（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    users = db.query(User).all()
    return {
        "users": [
            {
                "user_id": user.user_id,
                "username": user.username,
                "is_admin": user.is_admin,
                "created_at": user.created_at
            }
            for user in users
        ]
    }

@router.post("/users")
async def create_user(
    username: str = Body(...),
    password: str = Body(...),
    is_admin: bool = Body(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建用户（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    new_user = User(
        user_id=str(uuid.uuid4()),
        username=username,
        password=get_password_hash(password),
        is_admin=is_admin
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "success": True,
        "message": "用户创建成功",
        "user": {
            "user_id": new_user.user_id,
            "username": new_user.username,
            "is_admin": new_user.is_admin
        }
    }

@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    username: str = Body(None),
    password: str = Body(None),
    is_admin: bool = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改用户（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 查找用户
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新用户信息
    if username:
        # 检查新用户名是否已存在
        existing_user = db.query(User).filter(User.username == username, User.user_id != user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = username
    
    if password:
        user.password = get_password_hash(password)
    
    if is_admin is not None:
        user.is_admin = is_admin
    
    db.commit()
    db.refresh(user)
    
    return {
        "success": True,
        "message": "用户更新成功",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "is_admin": user.is_admin
        }
    }

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除用户（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 查找用户
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不允许删除管理员用户
    if user.is_admin:
        raise HTTPException(status_code=400, detail="不能删除管理员用户")
    
    db.delete(user)
    db.commit()
    
    return {
        "success": True,
        "message": "用户删除成功"
    }


# 任务管理API（仅管理员可访问）
@router.post("/tasks")
async def create_task(
    task_name: str = Body(...),
    description: str = Body(None),
    is_default: bool = Body(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建任务（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 检查任务名是否已存在
    existing_task = db.query(Task).filter(Task.task_name == task_name).first()
    if existing_task:
        raise HTTPException(status_code=400, detail="任务名已存在")
    
    # 如果设置为默认任务，将其他任务的默认标志设置为False
    if is_default:
        db.query(Task).update({Task.is_default: False})
    
    # 创建新任务
    new_task = Task(
        task_id=str(uuid.uuid4()),
        task_name=task_name,
        description=description,
        is_default=is_default
    )
    
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    return {
        "success": True,
        "message": "任务创建成功",
        "task": {
            "task_id": new_task.task_id,
            "task_name": new_task.task_name,
            "description": new_task.description,
            "is_default": new_task.is_default
        }
    }

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task_name: str = Body(None),
    description: str = Body(None),
    is_default: bool = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改任务（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 查找任务
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新任务信息
    if task_name:
        # 检查新任务名是否已存在
        existing_task = db.query(Task).filter(Task.task_name == task_name, Task.task_id != task_id).first()
        if existing_task:
            raise HTTPException(status_code=400, detail="任务名已存在")
        task.task_name = task_name
    
    if description is not None:
        task.description = description
    
    if is_default is not None:
        if is_default:
            # 将其他任务的默认标志设置为False
            db.query(Task).update({Task.is_default: False})
        task.is_default = is_default
    
    db.commit()
    db.refresh(task)
    
    return {
        "success": True,
        "message": "任务更新成功",
        "task": {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "description": task.description,
            "is_default": task.is_default
        }
    }

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除任务（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    
    # 查找任务
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 不允许删除默认任务
    if task.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认任务")
    
    db.delete(task)
    db.commit()
    
    return {
        "success": True,
        "message": "任务删除成功"
    }
