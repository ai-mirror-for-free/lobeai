"""工单库连接（claude_agent 库中的独立 schema `ticket`）

设计取舍：
- **不新建数据库**：工单表与 claude_agent 业务表同库不同 schema，备份/迁移跟着走，
  lobeai 侧只碰 ticket.* 三张表，不做跨 schema 关联。
- **每次调用新建连接**：工单 QPS 极低（个位数/分钟），换来的好处是没有跨线程共享
  连接的问题（FastAPI 同步端点跑在线程池里，psycopg2 连接非线程安全）。
- **配置优先级**：`tickets.db_*`（可覆盖） > `database.*`（默认，与其它 lobeai 服务
  共用同一个 pg 实例）。本地测试把 tickets.db_host 指到 127.0.0.1:2544 即可，
  不必碰 database.*。

DDL 见 docs/schema_tickets.sql（手动执行，本模块不建表）。
"""
from __future__ import annotations

import contextlib
from typing import Iterator

import psycopg2
import psycopg2.extras

from tools.ConfigManager import get_config, get_env
from tools.password_encryption import get_decrypted_password

DB_SCHEMA = "ticket"


def _conn_params() -> dict:
    return {
        "host": get_config("tickets.db_host") or get_env("DB_HOST", "localhost"),
        "port": get_config("tickets.db_port") or get_env("DB_PORT", "5432"),
        "user": get_env("DB_USERNAME"),
        "password": get_decrypted_password("DB_PASSWORD_ENCRYPTED"),
        "dbname": get_config("tickets.db_name", "claude_agent"),
        "connect_timeout": 8,
    }


@contextlib.contextmanager
def ticket_cursor() -> Iterator[psycopg2.extras.RealDictCursor]:
    """with ticket_cursor() as cur: ...  正常退出 commit，异常 rollback。"""
    conn = psycopg2.connect(**_conn_params())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping() -> str:
    """健康检查用：返回当前库名，异常直接抛出。"""
    with ticket_cursor() as cur:
        cur.execute("SELECT current_database() AS db")
        return cur.fetchone()["db"]
