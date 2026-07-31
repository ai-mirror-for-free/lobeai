-- =============================================================================
-- lobeai 手动 SQL 运维说明 (prancy-splashing-goblet 计划配套)
-- =============================================================================
-- 重要：本文件内的 SQL 全部为**人工运维参考**，lobeai 程序永远不会读取或执行
-- 这里的语句。lobeai 运行期间不会自动迁移 `users_center` / `activation_codes` /
-- `tokens`，所有变更必须由 DBA 人工审核后手动执行。
--
-- 历史背景：2026-07 完成 OpenWebUI 服务剥离 + default/vip/svip 三种 API 套餐
-- 下线，lobeai 剩余业务：
--   1) NewAPI 用户注册 / 登录校验 / 重置密码
--   2) Claude Code 激活码生成 / 兑换 (通过 server_b 委派)
--   3) group="api" 批量令牌 (data/api.json 配置)
--   4) OpenRouter 模型价格查询
--
-- -----------------------------------------------------------------------------
-- 1) 盘点仍未使用的 default/vip/svip 历史激活码
--    用途：估算客服换码工作量；建议先看数量再决定是否作废
-- -----------------------------------------------------------------------------
SELECT plan_level, days, COUNT(*) AS unused_count
  FROM activation_codes
 WHERE plan_level IN ('default', 'vip', 'svip')
   AND used_at IS NULL
 GROUP BY plan_level, days
 ORDER BY plan_level, days;

-- -----------------------------------------------------------------------------
-- 2) 【可选】把历史套餐未使用激活码标记为作废 (保留行便于审计)
--    注意：不执行 DELETE；used_by 字段会被填为固定字符串，可追溯
-- -----------------------------------------------------------------------------
-- UPDATE activation_codes
--    SET used_at = NOW(), used_by = 'retired-plan-prancy-splashing-goblet'
--  WHERE plan_level IN ('default', 'vip', 'svip')
--    AND used_at IS NULL;

-- -----------------------------------------------------------------------------
-- 3) 盘点仍挂着旧 group 的 NewAPI 存量令牌
--    用途：评估 token 失效流程；套餐下线后这些 token 不再自动同步 model_limits
-- -----------------------------------------------------------------------------
SELECT "group", COUNT(*) AS alive_count
  FROM tokens
 WHERE "group" IN ('default', 'vip', 'svip')
   AND deleted_at IS NULL
 GROUP BY "group"
 ORDER BY "group";

-- -----------------------------------------------------------------------------
-- 4) users_center.plan_level 保持原值不迁移
--    该字段已退化为历史信息字段，不再参与 lobeai 任何业务判断。
--    建议：保留列、不更新值，避免影响前端兼容 (旧 user 可能仍依赖此字段展示)。
--    若确认前端已全部下线，才可执行：
--    -- ALTER TABLE users_center DROP COLUMN plan_level;
-- -----------------------------------------------------------------------------
-- (no SQL, 仅为说明)

-- -----------------------------------------------------------------------------
-- 5) openwebui 库的处理 (可选，需人工备份后操作)
--    lobeai 不再连接 openwebui DB；该库残留的 user/settings 数据可整库备份后
--    由 DBA 决定 DROP。lobeai 自身**不会**触发 DROP DATABASE。
-- -----------------------------------------------------------------------------
-- (no SQL, 仅为说明)

-- -----------------------------------------------------------------------------
-- 6) 服务器运行时残留文件清理
--    代码中已无任何路径引用 data/pricing_plan.json；可由运维直接删除：
--    rm -f /root/claude-web/data/pricing_plan.json
-- -----------------------------------------------------------------------------

-- =============================================================================
-- 附：表结构参考 (仅说明，DDL 不在本文件)
--   - users_center: (name, email, plan_level, plan_price, days_left,
--                    quota_left, recharge, token, ...)
--   - activation_codes: (encrypted_code, plan_level, days, code_id,
--                        quota, created_at, used_at, used_by)
--   - tokens: (id, key, name, status, remain_quota, unlimited_quota,
--              model_limits_enabled, model_limits, "group", expired_time, ...)
-- =============================================================================
