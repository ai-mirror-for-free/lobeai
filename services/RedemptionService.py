import os
import psycopg2
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import secrets
import string
from dateutil.relativedelta import relativedelta

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
                
                # 更新兑换码状态，将email设为用户email
                update_query = """
                UPDATE public.exchange 
                SET email = %s, is_exchange = true, exchange_time = %s
                WHERE exchange_code = %s
                RETURNING id, email, exchange_code, is_exchange, created_time, exchange_time, plan
                """
                cursor.execute(update_query, (email, datetime.now(), code))
                updated_result = cursor.fetchone()
                
                # 检查是否确实更新了行
                if updated_result is None:
                    # 可能由于某些原因RETURNING子句没有返回结果，但我们应该检查受影响的行数
                    if cursor.rowcount == 0:
                        raise ValueError("更新失败：没有匹配的兑换码被更新")
                    # 如果RETURNING没返回但rowcount>0，重新查询获取更新后的数据
                    else:
                        select_query = """
                        SELECT id, email, exchange_code, is_exchange, created_time, exchange_time, plan
                        FROM public.exchange 
                        WHERE exchange_code = %s
                        """
                        cursor.execute(select_query, (code,))
                        updated_result = cursor.fetchone()
                
                print("更新后的兑换码信息:", updated_result)
                
                # 根据plan类型给用户充值相应额度
                quota_amount = self._get_quota_by_plan(plan)
                
                # 更新用户额度（使用相同的数据库连接和事务）
                self._recharge_user_quota_with_cursor(cursor, email, plan, quota_amount)
                
                # 更新tokens表（使用相同的数据库连接和事务）
                self._update_tokens_table_with_cursor(cursor, email, plan, quota_amount)
                
                self.db.conn.commit()
                
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

    def _recharge_user_quota_with_cursor(self, cursor, email: str, plan: str, quota_amount: int):
        """
        为用户充值额度，根据email更新用户信息
        :param cursor: 数据库游标
        :param email: 用户邮箱
        :param plan: 套餐类型
        :param quota_amount: 额度数量
        """
        # 首先检查用户是否存在
        check_user_query = "SELECT COUNT(*) FROM users_center WHERE email = %s"
        cursor.execute(check_user_query, (email,))
        user_exists = cursor.fetchone()[0] > 0
        
        if user_exists:
            # 获取当前用户的plan_level和days_left，以决定是否为同一套餐
            get_current_info_query = "SELECT plan_level, days_left, quota_left FROM users_center WHERE email = %s"
            cursor.execute(get_current_info_query, (email,))
            result = cursor.fetchone()
            
            if result is None:
                raise ValueError(f"用户不存在: {email}")
                
            current_plan, current_days_left, quota_left = result
            print(current_plan, current_days_left, quota_left)
            
            is_same_plan = current_plan == plan
            
            import datetime
            from datetime import datetime as dt
            
            if is_same_plan:
                print(current_days_left)
                # 如果是同一套餐，保留原有的过期时间并增加额度
                new_days_left = current_days_left + (30 * 24 * 3600)  
                print(new_days_left)
                
                # 使用SQL表达式更新数值，符合数据库规范
                update_user_quota_query = """
                UPDATE users_center 
                SET days_left = %s,
                    quota_left = quota_left + %s, 
                    recharge = recharge + %s,
                    plan_level = %s
                WHERE email = %s
                """
                cursor.execute(update_user_quota_query, (new_days_left, quota_amount, quota_amount, plan, email))
            else:
                # 如果是不同套餐，更新过期时间为当前时间加一个月，并重置额度
                # 将当前时间转换为整数时间戳，防止浮点数问题
                new_days_left = int(dt.now().timestamp()) + (30 * 24 * 3600)  # 秒时间戳，加一个月
                
                # 检查时间戳是否超出范围，防止整数溢出
                if new_days_left > 2147483647:  # 32位整数最大值
                    raise ValueError("计算出的时间戳超出范围")
                    
                # 使用SQL表达式更新数值，符合数据库规范
                update_user_quota_query = """
                UPDATE users_center 
                SET days_left = %s,
                    quota_left = %s, 
                    recharge = recharge + %s,
                    plan_level = %s
                WHERE email = %s
                """
                cursor.execute(update_user_quota_query, (new_days_left, quota_amount, quota_amount, plan, email))
        else:
            # 用户不存在，可能需要先注册用户或者报错
            raise ValueError(f"用户不存在: {email}")


    def _update_tokens_table_with_cursor(self, cursor, email: str, plan: str, quota_amount: int):
        """
        更新tokens表中的相关字段
        :param cursor: 数据库游标
        :param email: 用户邮箱
        :param plan: 套餐类型
        :param quota_amount: 额度数量
        """
        # 查询当前用户的信息，包括当前套餐类型和剩余配额
        select_query = """
        SELECT remain_quota, expired_time, status, name
        FROM public.tokens 
        WHERE name = %s AND deleted_at IS NULL
        """
        cursor.execute(select_query, (email,))
        result = cursor.fetchone()
        
        if not result:
            # 如果找不到对应用户，跳过更新
            return
        
        current_remain_quota, current_expired_time, current_status, token_name = result
        current_plan = self._get_plan_from_quota(current_remain_quota)
        
        # 计算新的过期时间和额度
        new_expired_time, new_remain_quota = self._calculate_new_expiry_and_quota(
            current_plan, plan, current_expired_time, current_remain_quota, quota_amount
        )
        print(f"当前套餐: {current_plan}, 当前剩余额度: {current_remain_quota}, 当前过期时间: {datetime.fromtimestamp(current_expired_time) if current_expired_time else '无'}, 充值后新套餐: {plan}, 新剩余额度: {new_remain_quota}, 新过期时间: {datetime.fromtimestamp(new_expired_time)}")
        # 如果当前状态不是1，则更新为1
        new_status = 1 if current_status != 1 else current_status
        
        # 更新tokens表
        update_query = """
        UPDATE public.tokens 
        SET expired_time = %s, 
            remain_quota = %s, 
            status = %s
        WHERE name = %s AND deleted_at IS NULL
        """
        cursor.execute(update_query, (new_expired_time, new_remain_quota, new_status, email))

    def _calculate_new_expiry_and_quota(self, current_plan, plan, current_expired_time, current_remain_quota, quota_amount):
        """
        计算新的过期时间和额度
        """
        import datetime
        from datetime import datetime as dt
        
        # 判断套餐类型是否相同
        is_same_plan = current_plan == plan
        # 计算一个月的时间增量（秒数）
        month_seconds = 30 * 24 * 3600
        
        # 如果套餐类型相同，额度叠加；否则重置为新套餐的额度
        if is_same_plan:
            new_remain_quota = current_remain_quota + quota_amount
            # 在当前过期时间基础上延长一个月
            new_expired_time = current_expired_time + month_seconds
        else:
            new_remain_quota = quota_amount
            # 计算新的过期时间，当前时间加上一个月
            new_expired_time = int(dt.now().timestamp()) + month_seconds  # 加上一个月的秒数
        
        return new_expired_time, new_remain_quota

    def _get_plan_from_quota(self, quota: int) -> str:
        """
        根据额度反推套餐类型
        """
        if quota == 500000:
            return "vip"
        elif quota == 1000000:
            return "svip"
        elif quota == 5000000:
            return "至尊版"
        else:
            # 如果无法确定套餐类型，返回一个默认值或None
            return None

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