# Python 编码规范

- 使用 Python 3.11+。
- 使用 pathlib.Path。
- 使用类型注解。
- FastAPI route 不写复杂业务逻辑。
- 核心业务逻辑放 services。
- 批处理必须单文件失败不中断。
- 不允许移动、删除、覆盖原始文件。
