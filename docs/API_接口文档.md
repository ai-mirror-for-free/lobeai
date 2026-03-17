# LobeAI API 接口文档

## 概述

LobeAI API 提供用户注册和验证功能。本文档仅介绍用户认证相关的两个核心接口。

**基础 URL**: `http://localhost:25141` 或生产环境 URL

---

## 1. 发送邮箱验证码

### 端点信息

- **HTTP 方法**: `POST`
- **路径**: `/api/send-verification-code`
- **认证**: 不需要
- **内容类型**: `application/json`

### 请求体

| 参数名 | 类型 | 必需 | 描述 |
|--------|------|------|------|
| `email` | string | ✓ | 有效的邮箱地址 |

### 请求示例

```bash
curl -X POST "http://localhost:25141/api/send-verification-code" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

```json
{
  "email": "user@example.com"
}
```

### 响应

#### 成功响应 (200 OK)

```json
{
  "message": "验证码已发送，请检查邮箱"
}
```

#### 错误响应

| 状态码 | 描述 | 响应示例 |
|--------|------|--------|
| 400 | 邮箱格式无效 | `{"detail": "Invalid email format"}` |
| 500 | 服务器错误 / 邮件发送失败 | `{"message": "发送发送失败: {error message}"}` |

### 工作流程

1. 用户输入有效的邮箱地址
2. 系统调用此接口发送验证码
3. 验证码通过邮件发送至用户邮箱（有效期通常为 10 分钟）
4. 用户获取邮箱中的验证码
5. 在注册时使用该验证码

### 说明

- 验证码是一次性使用的，请妥善保管
- 同一邮箱在短时间内多次请求验证码可能会被限流
- 请确保邮箱地址正确，否则无法收到验证码

---

## 2. 用户注册

### 端点信息

- **HTTP 方法**: `POST`
- **路径**: `/api/register`
- **认证**: 不需要
- **内容类型**: `application/json`

### 请求体

| 参数名 | 类型 | 必需 | 描述 |
|--------|------|------|------|
| `username` | string | ✓ | 用户名（用于登录） |
| `password` | string | ✓ | 密码（建议至少 8 字符，包含大小写字母和数字） |
| `email` | string | ✓ | 有效的邮箱地址 |
| `verification_code` | string | ✓ | 通过 `/api/send-verification-code` 获取的验证码 |
| `aff_code` | string | ✗ | 推荐码（可选，用于佣金追踪） |

### 请求示例

```bash
curl -X POST "http://localhost:25141/api/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "SecurePassword123",
    "email": "john@example.com",
    "verification_code": "123456",
    "aff_code": "referrer123"
  }'
```

```json
{
  "username": "john_doe",
  "password": "SecurePassword123",
  "email": "john@example.com",
  "verification_code": "123456",
  "aff_code": "referrer123"
}
```

### 响应

#### 成功响应 (200 OK)

```json
{
  "status": "success",
  "message": "用户注册成功",
  "user_id": "user_123456",
  "username": "john_doe",
  "email": "john@example.com",
  "token": "QzLBUzx76YHpSZyUO4PksCUOxiO3VFc6oJpl27d6bTyZRcsN"
}
```

#### 错误响应

| 状态码 | 场景 | 响应示例 |
|--------|------|--------|
| 400 | 邮箱格式无效 | `{"detail": "Invalid email format"}` |
| 400 | 验证码错误或已过期 | `{"message": "验证码错误或已过期"}` |
| 400 | 用户名已存在 | `{"message": "用户名已被注册"}` |
| 400 | 邮箱已存在 | `{"message": "该邮箱已被注册"}` |
| 400 | 密码强度不足 | `{"message": "密码强度不足"}` |
| 500 | 服务器错误 | `{"message": "注册失败: {error message}"}` |

### 工作流程

1. 用户首先调用 `/api/send-verification-code` 获取验证码
2. 用户从邮箱中获取验证码
3. 用户提交注册请求，包含用户名、密码、邮箱和验证码
4. 系统验证所有信息的有效性
5. 如果验证通过，创建新用户账户
6. 返回用户 ID 和初始 API token

### 账户创建说明

- 注册成功后，系统会自动为用户创建初始 API Token
- 该 Token 可直接用于后续的 API 认证
- 用户名和邮箱必须全局唯一
- 密码建议遵循以下规则：
  - 至少 8 个字符
  - 至少包含 1 个大写字母
  - 至少包含 1 个小写字母
  - 至少包含 1 个数字

### 推荐码说明

- `aff_code` 是可选参数，用于联盟营销追踪
- 如果提供了有效的推荐码，新用户和推荐者都可能获得相应的奖励
- 推荐码由邀请者提供

---

## 完整注册流程示例

### 步骤 1: 发送验证码

```bash
curl -X POST "http://localhost:25141/api/send-verification-code" \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com"}'
```

**响应**:
```json
{
  "message": "验证码已发送，请检查邮箱"
}
```

### 步骤 2: 用户从邮箱获取验证码
用户检查邮箱，获取验证码（例如：`123456`）

### 步骤 3: 提交注册信息

```bash
curl -X POST "http://localhost:25141/api/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "SecurePassword123",
    "email": "john@example.com",
    "verification_code": "123456"
  }'
```

**响应**:
```json
{
  "status": "success",
  "message": "用户注册成功",
  "user_id": "user_123456",
  "username": "john_doe",
  "email": "john@example.com",
  "token": "QzLBUzx76YHpSZyUO4PksCUOxiO3VFc6oJpl27d6bTyZRcsN"
}
```

---

## 错误处理

所有错误响应都会返回以下格式之一：

### 格式 1: Pydantic 验证错误
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "invalid email address",
      "type": "value_error.email"
    }
  ]
}
```

### 格式 2: 业务逻辑错误
```json
{
  "message": "具体的错误描述"
}
```

### 常见错误代码

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| `Invalid email format` | 邮箱格式不正确 | 检查邮箱格式是否有效 |
| `验证码错误或已过期` | 验证码不正确或已超时 | 重新请求验证码 |
| `用户名已被注册` | 用户名已存在 | 选择其他用户名 |
| `该邮箱已被注册` | 邮箱已关联到其他账户 | 使用其他邮箱或找回密码 |

---

## 最佳实践

1. **安全性**
   - 密码应该在客户端加密后再发送
   - 避免在日志中记录完整的密码或验证码
   - 使用 HTTPS 加密所有请求

2. **用户体验**
   - 在发送验证码前验证邮箱格式
   - 向用户显示验证码的有效期
   - 提供重新发送验证码的选项
   - 在注册失败时提供清晰的错误提示

3. **API 调用**
   - 实现适当的重试机制
   - 为验证码请求实现速率限制（例如每分钟最多 3 次）
   - 缓存验证码的有效期信息

---

## 技术支持

如有问题，请联系技术支持团队或查阅项目 GitHub 页面：
- 项目地址: https://github.com/QuantumNous/new-api
- API 文档: https://apifox.newapi.ai/
