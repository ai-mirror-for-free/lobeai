import os
import psycopg2
from dotenv import load_dotenv
from tools.LoggerManager import LoggerManager

class DatabaseManager:
    """管理 PostgreSQL 数据库的操作类"""

    def __init__(self, env_path=".env", db_name="oneapi"):
        load_dotenv(env_path)
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.user = os.getenv("DB_USERNAME")
        self.password = os.getenv("DB_PASSWORD")
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
    """管理 new-api 数据库的操作类"""
    def __init__(self, env_path=".env", db_name="oneapi"):
        super().__init__(env_path, db_name)


class OpenWebUIDatabaseManager(DatabaseManager):
    """管理 open-webui 数据库的操作类"""
    def __init__(self, env_path=".env", db_name="openwebui"):
        super().__init__(env_path, db_name)
    
    def get_all_users(self):
        """获取所有用户"""
        command = 'select id,name,email,role,settings from "user"'
        return self.execute_query(command)
