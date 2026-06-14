# Tasks: 文件盘点与资产登记

## T001 阅读 Spec

- [x] 阅读 spec.md
- [x] 阅读 plan.md
- [x] 阅读 acceptance.md
- [x] 阅读 .cursor/rules

## T002 建模与接口确认

- [x] 确认涉及数据库表
- [x] 确认涉及配置文件
- [x] 确认涉及服务类
- [x] 确认 CLI 或 API 入口

## T003 实现服务逻辑

- [x] 新增或修改对应 service
- [x] 增加日志
- [x] 增加异常处理
- [x] 保持幂等

## T004 接入 CLI/API

- [x] 如为批处理功能，接入 Typer CLI
- [ ] 如为查询/管理功能，接入 FastAPI（001 为批处理，本项不适用）

## T005 测试

- [x] 编写或补充 pytest
- [x] 覆盖正常场景
- [x] 覆盖异常场景
- [x] 覆盖中文路径/中文内容
