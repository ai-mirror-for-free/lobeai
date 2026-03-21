import os
import psycopg2
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import secrets
import string

# 导入NewApiDatabaseManager
from tools.DbScript import NewApiDatabaseManager

load_dotenv()


class RedemptionCode(BaseModel):
    id: int
    email: Optional[str]
    exchange_code: str
    is_exchange: bool
    created_time: Optional[datetime]
    exchange_time: Optional[datetime]
    plan: str


class GenerateRedemptionRequest(BaseModel):
    count: int
    plan: str


class RedemptionService:
    def __init__(self):
        self.db = NewApiDatabaseManager()

    def generate_unique_code(self, length: int = 16) -> str:
        """生成唯一的兑换码"""
        characters = string.ascii_uppercase + string.digits  # A-Z, 0-9
        while True:
            code = ''.join(secrets.choice(characters) for _ in range(length))
            if self.is_code_unique(code):
                return code

    def is_code_unique(self, code: str) -> bool:
        """检查兑换码是否唯一"""
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM public.exchange WHERE exchange_code = %s", (code,))
                result = cursor.fetchone()
                return result is None
        finally:
            self.db.disconnect()

    def batch_generate_redemption_codes(self, count: int, plan: str) -> List[str]:
        """
        批量生成兑换码
        :param count: 生成数量
        :param plan: 套餐类型
        :return: 生成的兑换码列表
        """
        if count <= 0:
            raise ValueError("生成数量必须大于0")
        
        # 先生成所有唯一的兑换码
        generated_codes = []
        attempts = 0
        max_attempts = count * 10  # 最大尝试次数
        
        while len(generated_codes) < count and attempts < max_attempts:
            code = self.generate_unique_code()
            if code not in generated_codes:  # 确保本次生成的码也是唯一的
                generated_codes.append(code)
            attempts += 1
        
        if len(generated_codes) < count:
            raise ValueError(f"未能生成足够的唯一兑换码，仅生成了 {len(generated_codes)} 个")
        
        # 将所有兑换码一次性插入数据库
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                # 使用批量插入语句
                insert_query = """
                INSERT INTO public.exchange (email, exchange_code, is_exchange, created_time, exchange_time, plan)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                # 准备批量插入的数据
                insert_data = []
                now = datetime.now()
                for code in generated_codes:
                    insert_data.append((
                        None,           # email 为空
                        code,           # 生成的兑换码
                        False,          # is_exchange 为 false
                        now,            # 当前时间为创建时间
                        None,           # exchange_time 为空
                        plan            # 套餐类型
                    ))
                
                # 执行批量插入
                cursor.executemany(insert_query, insert_data)
                self.db.conn.commit()
                
                return generated_codes
                
        except Exception as e:
            self.db.conn.rollback()
            raise e
        finally:
            self.db.disconnect()

    def batch_delete_redemption_codes(self, code_ids: List[int]) -> int:
        """
        批量删除兑换码
        :param code_ids: 要删除的兑换码ID列表
        :return: 删除的记录数量
        """
        if not code_ids:
            return 0
            
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                # 构造SQL语句，使用IN子句来匹配要删除的ID
                placeholders = ','.join(['%s'] * len(code_ids))
                delete_query = f"DELETE FROM public.exchange WHERE id IN ({placeholders})"
                cursor.execute(delete_query, code_ids)
                
                deleted_count = cursor.rowcount
                self.db.conn.commit()
                
                return deleted_count
                
        except Exception as e:
            self.db.conn.rollback()
            raise e
        finally:
            self.db.disconnect()

    def redeem_code(self, code: str, email: str) -> RedemptionCode:
        """
        兑换兑换码，更新用户email并将兑换标志设为True
        :param code: 兑换码
        :param email: 用户邮箱（唯一键）
        :return: 更新后的兑换码对象
        """
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                # 查询兑换码是否存在且未被兑换
                select_query = """
                SELECT id, email, exchange_code, is_exchange, created_time, exchange_time, plan
                FROM public.exchange 
                WHERE exchange_code = %s
                FOR UPDATE
                """
                cursor.execute(select_query, (code,))
                result = cursor.fetchone()
                
                if result is None:
                    raise ValueError("兑换码不存在")
                
                # 检查是否已被兑换
                if result[3]:  # is_exchange 字段
                    raise ValueError("兑换码已被兑换")
                
                # 获取plan类型
                plan = result[6]
                
                # 更新兑换码状态，将email设为email
                update_query = """
                UPDATE public.exchange 
                SET email = %s, is_exchange = true, exchange_time = %s
                WHERE exchange_code = %s
                RETURNING id, email, exchange_code, is_exchange, created_time, exchange_time, plan
                """
                cursor.execute(update_query, (email, datetime.now(), code))
                updated_result = cursor.fetchone()
                
                # 根据plan类型给用户充值相应额度
                quota_amount = self._get_quota_by_plan(plan)
                self._recharge_user_quota(email, plan, quota_amount)
                
                self.db.conn.commit()
                
                if updated_result is None:
                    raise ValueError("更新失败")
                
                return RedemptionCode(
                    id=updated_result[0],
                    email=updated_result[1],
                    exchange_code=updated_result[2],
                    is_exchange=updated_result[3],
                    created_time=updated_result[4],
                    exchange_time=updated_result[5],
                    plan=updated_result[6]
                )
                
        except Exception as e:
            self.db.conn.rollback()
            raise e
        finally:
            self.db.disconnect()

    def _get_quota_by_plan(self, plan: str) -> int:
        """
        根据plan类型返回对应的额度
        """
        plan_quotas = {
            "vip": 500000,      # 500K
            "svip": 1000000,    # 1000K
            "至尊版": 5000000    # 5000K
        }
        
        return plan_quotas.get(plan, 0)

    def _recharge_user_quota(self, email: str, plan: str, quota_amount: int):
        """
        为用户充值额度，根据email更新用户信息
        """
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                # 更新用户额度，参考CreaterUsers.py中的SQL语句
                # insert into users_center (name, email, plan_level, plan_price, days_left, quota_left, recharge, token) values (%s, %s, %s, %s, %s, %s, %s, %s)
                
                # 首先检查用户是否存在
                check_user_query = "SELECT COUNT(*) FROM users_center WHERE email = %s"
                cursor.execute(check_user_query, (email,))
                user_exists = cursor.fetchone()[0] > 0
                
                if user_exists:
                    # 用户存在，更新现有记录
                    update_user_quota_query = """
                    UPDATE users_center 
                    SET quota_left = quota_left + %s, 
                        recharge = recharge + %s,
                        plan_level = %s
                    WHERE email = %s
                    """
                    cursor.execute(update_user_quota_query, (quota_amount, quota_amount, plan, email))
                else:
                    # 用户不存在，可能需要先注册用户或者报错
                    raise ValueError(f"用户不存在: {email}")
                
                # self.db.conn.commit()
        except Exception as e:
            raise e
        # finally:
        #     self.db.disconnect()

    def get_redemption_codes(self, limit: int = 100, offset: int = 0) -> List[RedemptionCode]:
        """
        获取兑换码列表
        """
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                query = """
                SELECT id, email, exchange_code, is_exchange, created_time, exchange_time, plan
                FROM public.exchange
                ORDER BY created_time DESC
                LIMIT %s OFFSET %s
                """
                cursor.execute(query, (limit, offset))
                rows = cursor.fetchall()

                redemption_codes = []
                for row in rows:
                    redemption_codes.append(RedemptionCode(
                        id=row[0],
                        email=row[1],
                        exchange_code=row[2],
                        is_exchange=row[3],
                        created_time=row[4],
                        exchange_time=row[5],
                        plan=row[6]
                    ))
                return redemption_codes
        finally:
            self.db.disconnect()

    def get_redemption_codes_count(self) -> int:
        """
        获取兑换码总数
        """
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                query = "SELECT COUNT(*) FROM public.exchange"
                cursor.execute(query)
                count = cursor.fetchone()[0]
                return count
        finally:
            self.db.disconnect()

    def get_filtered_redemption_codes(
        self,
        limit: int = 100,
        offset: int = 0,
        is_exchanged: Optional[bool] = None,
        plan: Optional[str] = None
    ) -> List[RedemptionCode]:
        """
        获取筛选后的兑换码列表
        """
        self.db.connect()
        try:
            with self.db.conn.cursor() as cursor:
                # 构建查询条件
                query = "SELECT id, email, exchange_code, is_exchange, created_time, exchange_time, plan FROM public.exchange"
                conditions = []
                params = []

                if is_exchanged is not None:
                    conditions.append("is_exchange = %s")
                    params.append(is_exchanged)

                if plan:
                    conditions.append("plan = %s")
                    params.append(plan)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY created_time DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                redemption_codes = []
                for row in rows:
                    redemption_codes.append(RedemptionCode(
                        id=row[0],
                        email=row[1],
                        exchange_code=row[2],
                        is_exchange=row[3],
                        created_time=row[4],
                        exchange_time=row[5],
                        plan=row[6]
                    ))
                return redemption_codes
        finally:
            self.db.disconnect()