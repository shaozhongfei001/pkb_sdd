# Plan: 唯一原文仓库 raw_vault

## 1. 相关模块

- backend/app/services/
- backend/app/models/
- backend/app/cli/
- backend/app/api/
- config/
- sql/

## 2. 核心流程

1. 读取配置。
2. 查询或写入 MySQL 元数据。
3. 执行本功能处理逻辑。
4. 写入状态、日志和产物文件。
5. 如果失败，记录错误并保持可重试。
6. 如果需要人工确认，写入 review queue。

## 3. 异常处理

| 场景 | 处理 |
|---|---|
| 输入不存在 | 记录错误，任务失败 |
| 单文件失败 | 记录错误，继续批处理 |
| 数据库失败 | 回滚当前事务 |
| 质量低 | 写 review item 或触发重解析 |
