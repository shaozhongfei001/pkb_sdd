# SDD 开发规范

## 基本原则

1. 没有 Spec，不开发功能。
2. 没有 Plan，不写实现。
3. 没有 Tasks，不交给 AI 编码。
4. 没有 Acceptance，不合并代码。
5. 数据库变更必须有 migration。
6. 文档解析必须有样本验证。
7. 原始文件默认只读。
8. 任何自动化动作不得直接删除原始文件。
9. 蒸馏结论必须有 evidence。
10. AI 生成代码必须人工审查。

## 标准流程

```text
需求想法 → spec.md → plan.md → tasks.md → code → tests → acceptance → review
```
