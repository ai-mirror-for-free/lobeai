-- =============================================================================
-- 用户工单 / 反馈系统 DDL（手动执行，lobeai 不会自动建表）
-- =============================================================================
-- 目标库：A 端 claude_agent 库（同一 pg 实例，正式环境 localhost:2543）
-- 隔离方式：独立 schema `ticket`，与 claude_agent 现有 public 表完全隔离
--
-- 执行方式（正式环境）：
--   psql -h localhost -p 2543 -U postgres -d claude_agent -f docs/schema_tickets.sql
--
-- 业务规则（与后端代码保持一致，改这里必须同步改代码）：
--   1) 多轮对话：一条工单 N 条 ticket_messages，关闭后用户再发消息会自动 reopen
--   2) 附件保留：从 **关单时间** (tickets.closed_at) 起算 30 天；
--      超期只删物理文件，行保留（status='purged'），文字内容一律不动
--   3) 自动关单：仅 `replied` 状态（管理员已回复）且管理员最后回复超过 7 天、
--      期间用户没有任何新消息 → 自动关闭；`open` 状态**永不自动关闭**
--   4) 触发器函数建在 ticket 内（ticket.set_updated_at），避免 docs/schema.sql
--      重跑时 `DROP FUNCTION set_updated_at() CASCADE` 把本表触发器一起带走
--
-- 重入：全部 IF NOT EXISTS / CREATE OR REPLACE / DROP TRIGGER IF EXISTS
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS ticket;

-- 工单号序列：TK20261119-00001
CREATE SEQUENCE IF NOT EXISTS ticket.ticket_no_seq START 1;

CREATE OR REPLACE FUNCTION ticket.set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ─── 1. 工单主表 ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticket.tickets (
    id              BIGSERIAL PRIMARY KEY,
    ticket_no       VARCHAR(32)  NOT NULL UNIQUE
                    DEFAULT ('TK' || to_char(NOW(), 'YYYYMMDD') || '-'
                             || lpad(nextval('ticket.ticket_no_seq')::text, 5, '0')),
    user_email      VARCHAR(255) NOT NULL,          -- 小写，来源 claude_agent /api/v1/auth/me（登录账号）
    user_name       VARCHAR(100),
    contact_email   VARCHAR(255),                   -- 用户自己填写的联系邮箱（必填，可与登录账号不同）
    activation_code VARCHAR(1000),                  -- 仅 category='billing' 时保存，用户粘贴的有问题激活码
    category        VARCHAR(32)  NOT NULL DEFAULT 'other',
                    -- cannot_use 无法使用 / account 账号登录 / billing 充值与额度
                    -- feature 功能建议 / other 其他
    subject         VARCHAR(200) NOT NULL,
    status          VARCHAR(16)  NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'replied', 'closed')),

    -- 未读计数（前端红点）
    user_unread     INTEGER      NOT NULL DEFAULT 0,
    admin_unread    INTEGER      NOT NULL DEFAULT 0,

    -- 多轮 / 自动关单判定
    last_user_at    TIMESTAMPTZ,                    -- 用户最后一条消息时间
    last_admin_at   TIMESTAMPTZ,                    -- 管理员最后一条回复时间
    last_message_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    closed_at       TIMESTAMPTZ,
    close_reason    VARCHAR(16),                    -- user / admin / auto_7d
    reopened_count  INTEGER      NOT NULL DEFAULT 0,

    -- 用户主动移除（用户侧所有查询都过滤，管理员可见）
    -- 2026-11-19：原「撤销 / 删除」两个操作已合并为一个「撤销&删除」，统一用这一列
    user_deleted_at   TIMESTAMPTZ,                  -- 用户移除：不再出现在「我的工单」

    source          VARCHAR(16)  NOT NULL DEFAULT 'portal',
    meta            JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_email_created
    ON ticket.tickets (user_email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_status_last
    ON ticket.tickets (status, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_admin_unread
    ON ticket.tickets (admin_unread DESC, created_at DESC);
-- 自动关单扫描（只扫 replied）
CREATE INDEX IF NOT EXISTS idx_tickets_auto_close
    ON ticket.tickets (status, last_admin_at)
    WHERE status = 'replied';

-- ─── 1.1 增量变更（已建表环境重跑本文件也能升级）──────────────
-- 2026-11-19：新增加「联系邮箱」与「激活码」两个反馈字段
ALTER TABLE ticket.tickets ADD COLUMN IF NOT EXISTS contact_email   VARCHAR(255);
ALTER TABLE ticket.tickets ADD COLUMN IF NOT EXISTS activation_code VARCHAR(1000);
-- 2026-11-19：用户侧移除（软删），用户看不到，管理员可见
ALTER TABLE ticket.tickets ADD COLUMN IF NOT EXISTS user_deleted_at TIMESTAMPTZ;
-- 撤销/删除已合并，旧的单独「撤销」列不再使用（重跑本文件会自动清理）
ALTER TABLE ticket.tickets DROP COLUMN IF EXISTS user_withdrawn_at;

-- 用户侧列表只查可见工单
CREATE INDEX IF NOT EXISTS idx_tickets_user_visible
    ON ticket.tickets (user_email, last_message_at DESC)
    WHERE user_deleted_at IS NULL;

DROP TRIGGER IF EXISTS trg_tickets_updated_at ON ticket.tickets;
CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON ticket.tickets
    FOR EACH ROW EXECUTE FUNCTION ticket.set_updated_at();

-- ─── 2. 工单消息（多轮对话本体）──────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticket.ticket_messages (
    id           BIGSERIAL PRIMARY KEY,
    ticket_id    BIGINT      NOT NULL
                 REFERENCES ticket.tickets(id) ON DELETE CASCADE,
    author_role  VARCHAR(8)  NOT NULL CHECK (author_role IN ('user', 'admin')),
    author_email VARCHAR(255),
    content      TEXT        NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket
    ON ticket.ticket_messages (ticket_id, created_at);

-- ─── 3. 附件（图片 / 普通文件）───────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticket.ticket_attachments (
    id            BIGSERIAL PRIMARY KEY,
    ticket_id     BIGINT      NOT NULL
                  REFERENCES ticket.tickets(id) ON DELETE CASCADE,
    message_id    BIGINT
                  REFERENCES ticket.ticket_messages(id) ON DELETE CASCADE,
    uploader_role VARCHAR(8)  NOT NULL CHECK (uploader_role IN ('user', 'admin')),
    file_name     VARCHAR(255) NOT NULL,            -- 原始名，永久保留用于展示
    mime_type     VARCHAR(128),
    size_bytes    BIGINT      NOT NULL DEFAULT 0,
    storage_path  TEXT,                             -- NULL = 文件已清理
    is_image      BOOLEAN     NOT NULL DEFAULT FALSE,
    status        VARCHAR(16) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'purged')),
    purged_at     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ticket_attachments_ticket
    ON ticket.ticket_attachments (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_attachments_cleanup
    ON ticket.ticket_attachments (status, ticket_id);

-- ─── 运维核查语句（只读，供排查）────────────────────────────────────
-- 待处理工单数
-- SELECT count(*) FROM ticket.tickets WHERE status = 'open';
-- 已回复超过 7 天、用户没回的（下次 cron 会被自动关）
-- SELECT ticket_no, user_email, last_admin_at FROM ticket.tickets
--  WHERE status = 'replied' AND last_admin_at < NOW() - INTERVAL '7 days';
-- 某工单全部消息
-- SELECT * FROM ticket.ticket_messages WHERE ticket_id = 1 ORDER BY id;
