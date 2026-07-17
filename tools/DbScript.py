import os
import psycopg2
from dotenv import load_dotenv
from tools.LoggerManager import LoggerManager
from tools.password_encryption import get_decrypted_password

class DatabaseManager:
    """管理 PostgreSQL 数据库的操作类

    支持多实例 (例如 LOCAL 副本 NewAPI): 通过显式参数或 DB_*_LOCAL env
    override 默认连接。fallback 链 (按字段独立): 显式参数 > *_LOCAL env > 默认 env
    """

    def __init__(self, env_path=".env", db_name="oneapi",
                 db_host=None, db_port=None, db_user=None, db_password=None):
        load_dotenv(env_path)
        # host/port/user 任一字段允许单独 override
        self.host = db_host or os.getenv("DB_HOST_LOCAL") or os.getenv("DB_HOST", "localhost")
        self.port = db_port or os.getenv("DB_PORT_LOCAL") or os.getenv("DB_PORT", "5432")
        self.user = db_user or os.getenv("DB_USERNAME_LOCAL") or os.getenv("DB_USERNAME")
        # 密码: 显式传入的 password 直接用 (不二次解密); 否则优先 LOCAL 密文, 再回退默认
        if db_password is not None:
            self.password = db_password
        else:
            local_enc = os.getenv("DB_PASSWORD_ENCRYPTED_LOCAL")
            self.password = (
                get_decrypted_password("DB_PASSWORD_ENCRYPTED_LOCAL")
                if local_enc
                else get_decrypted_password("DB_PASSWORD_ENCRYPTED")
            )
        self.dbname = db_name
        self.conn = None
        self.logger = LoggerManager()

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                dbname=self.dbname
            )
            self.logger.info("数据库连接成功")
        except Exception as e:
            self.logger.error(f"连接数据库失败: {e}")
            self.conn = None

    def disconnect(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.logger.info("数据库连接已关闭")

    def execute_query(self, sql, params=None):
        """执行查询语句 (SELECT)"""
        if not self.conn:
            self.connect()
            if not self.conn:
                return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                results = cur.fetchall()
                return results
        except Exception as e:
            self.logger.error(f"查询执行失败: {e}")
            return None

    def execute_command(self, sql, params=None):
        """执行更新语句 (INSERT, UPDATE, DELETE)"""
        if not self.conn:
            self.connect()
            if not self.conn:
                return False

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                self.conn.commit()
                self.logger.info("命令执行成功")
                return True
        except Exception as e:
            self.logger.error(f"命令执行失败: {e}")
            self.conn.rollback()
            return False
        

class NewApiDatabaseManager(DatabaseManager):
    """管理 new-api 数据库的操作类

    支持多 NewAPI 实例: 通过显式参数或 DB_*_LOCAL env 切换到 LOCAL 副本的连接。
    """
    def __init__(self, env_path=".env", db_name="oneapi",
                 db_host=None, db_port=None, db_user=None, db_password=None):
        super().__init__(
            env_path, db_name,
            db_host=db_host, db_port=db_port,
            db_user=db_user, db_password=db_password,
        )


class OpenWebUIDatabaseManager(DatabaseManager):
    """管理 open-webui 数据库的操作类"""
    def __init__(self, env_path=".env", db_name="openwebui"):
        super().__init__(env_path, db_name)
    
    def get_all_users(self):
        """获取所有用户"""
        command = 'select id,name,email,role,settings from "user"'
        return self.execute_query(command)
