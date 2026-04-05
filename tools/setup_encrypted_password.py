"""
密码加密设置工具
用于生成加密密钥、加密密码

密钥通过环境变量注入，适用于本地开发和服务器部署
"""
import sys
import os
from dotenv import load_dotenv
from tools.password_encryption import (
    generate_encryption_key,
    encrypt_password,
)


def main():
    print("=== 密码加密设置工具 ===\n")

    # 检查是否已有密钥
    load_dotenv()
    existing_key = os.environ.get("ENCRYPTION_KEY")

    if existing_key:
        print(f"检测到环境变量中有密钥: {existing_key[:20]}...")
        print("\n请选择密钥来源:")
        print("1. 使用现有密钥")
        print("2. 生成新密钥（覆盖现有密钥）")
        choice = input("请输入选项 (1/2): ").strip()

        if choice == "1":
            key = existing_key
        elif choice == "2":
            key = generate_encryption_key()
            print(f"\n生成的新密钥: {key}")
            print("注意: 需要重新加密所有密码")
        else:
            print("无效选项，退出")
            sys.exit(1)
    else:
        # 生成新密钥
        key = generate_encryption_key()
        print(f"生成的新密钥: {key}")

    # 加密多个密码
    passwords_to_encrypt = [
        ("ADMIN_PASSWORD_ENCRYPTED", "Open WebUI 管理员密码"),
        ("DB_PASSWORD_ENCRYPTED", "数据库密码"),
        ("NEWAPI_PASSWORD_ENCRYPTED", "New API 密码"),
    ]

    print("\n请输入要加密的密码（直接回车跳过）：\n")

    encrypted_results = {}

    for env_var, desc in passwords_to_encrypt:
        password = input(f"{desc}: ").strip()

        if password:
            encrypted_password = encrypt_password(password, key)
            encrypted_results[env_var] = encrypted_password
            print(f"  ✓ 已加密\n")

    # 显示结果
    if encrypted_results:
        print("\n" + "="*50)
        print("=== 加密结果 ===")
        print("="*50)

        for env_var, encrypted_value in encrypted_results.items():
            print(f"\n{env_var}={encrypted_value}")

        # 验证解密
        from tools.password_encryption import decrypt_password
        print("\n" + "="*50)
        print("=== 验证解密 ===")
        print("="*50)

        for env_var, encrypted_value in encrypted_results.items():
            try:
                decrypted = decrypt_password(encrypted_value, key)
                print(f"{env_var}: ✓ 解密成功")
            except Exception as e:
                print(f"{env_var}: ✗ 解密失败 - {e}")

        print("\n" + "="*50)
        print("=== 部署指南 ===")
        print("="*50)

        print("\n【环境变量配置】")
        print("\n1. 在 .env 文件中配置:")
        print("   ```")
        print(f"   ENCRYPTION_KEY={key}")
        for env_var, encrypted_value in encrypted_results.items():
            print(f"   {env_var}={encrypted_value}")
        print("   ```")

        print("\n2. 或通过命令行环境变量注入:")
        print("   ```bash")
        print(f"   export ENCRYPTION_KEY=\"{key}\"")
        for env_var, encrypted_value in encrypted_results.items():
            print(f"   export {env_var}=\"{encrypted_value}\"")
        print("   python your_script.py")
        print("   ```")

        print("\n3. 使用 systemd 服务:")
        print("   在服务文件中添加:")
        print("   ```ini")
        print(f"   Environment=\"ENCRYPTION_KEY={key}\"")
        for env_var, encrypted_value in encrypted_results.items():
            print(f"   Environment=\"{env_var}={encrypted_value}\"")
        print("   ```")

        print("\n提示: 详细的部署文档请查看 docs/SERVER_DEPLOYMENT.md")

        if existing_key and existing_key != key:
            print("\n⚠️  注意: 如果之前使用过旧密钥，需要重新加密所有密码")
    else:
        print("\n未输入任何密码，设置取消")


if __name__ == "__main__":
    main()
