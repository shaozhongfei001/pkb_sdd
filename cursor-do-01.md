# -------------------------------------------
# 4. Cursor 打开后，第一条提示词：只读理解项目
> 先不要让 Cursor 写代码。粘贴下面提示词：
> 你现在是个人历史项目文档知识库 pkb_sdd 项目的开发助手。
> 当前项目根目录是：
> /home/szf/dev/pyws/pkb_sdd

# 请先只阅读和理解以下文件，不要修改任何代码：
```
1. README.md
2. manifest.md
3. .cursor/rules/000-project-rules.mdc
4. .cursor/rules/001-sdd-workflow.mdc
5. .cursor/rules/002-python-coding.mdc
6. .cursor/rules/003-database.mdc
7. .cursor/rules/004-parser.mdc
8. .cursor/rules/005-testing.mdc
9. .cursor/rules/006-ai-boundaries.mdc
10. docs/sdd_development_standard.md
11. docs/database_standard.md
12. docs/parser_integration_standard.md
13. specs/000-project-charter/spec.md
14. specs/001-file-inventory/spec.md
15. specs/001-file-inventory/plan.md
16. specs/001-file-inventory/tasks.md
17. specs/001-file-inventory/acceptance.md
18. specs/001-file-inventory/test_cases.md

阅读后请输出：
1. 本项目的开发边界
2. 原始文件保护原则
3. 当前第一个要开发的 Spec 是什么
4. 你后续写代码时必须遵守哪些规则
5. 哪些行为是禁止的

本轮不要修改文件，不要生成代码。
```
# -------------------------------------------
# 5. 创建 Python 虚拟环境，在 Cursor 终端或 WSL 终端执行：
cd /home/szf/dev/pyws/pkb_sdd/backend

python3 -m venv .venv
source .venv/bin/activate

python --version
pip install --upgrade pip
pip install -r requirements.txt
# 日常使用 python环境
cd backend
source .venv/bin/activate
python -m app.cli.main --help

# 若以后重装依赖，网络不好时可用镜像：
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt


#检查 CLI：
python -m app.cli.main --help
# -------------------------------------------
# 6. 初始化 MySQL
# 先启动 MySQL：

sudo service mysql start

# 初始化数据库：

cd /home/szf/dev/pyws/pkb_sdd
mysql -uroot -p < sql/001_init_schema_v1_1.sql

# 验证：

mysql -uroot -p

# 进入 MySQL 后执行：

SHOW DATABASES;
USE personal_kb;
SHOW TABLES;
+----------------------------+
| Tables_in_personal_kb      |
+----------------------------+
| kb_curated_asset           |
| kb_document                |
| kb_document_chunk          |
| kb_document_quality        |
| kb_duplicate_group         |
| kb_embedding_ref           |
| kb_evidence                |
| kb_file_content            |
| kb_file_instance           |
| kb_manual_correction       |
| kb_parse_job               |
| kb_project                 |
| kb_project_document        |
| kb_raw_vault_object        |
| kb_review_item             |
| kb_schema_version          |
| kb_task_log                |
| kb_version_candidate_group |
+----------------------------+
18 rows in set (0.00 sec)
# -------------------------------------------
# 7. 创建 config/app.yaml
# 执行：

cd /home/szf/dev/pyws/pkb_sdd
cp config/app.example.yaml config/app.yaml

# 创建数据目录：

mkdir -p /home/szf/dev/data/personal-kb/source_registry
mkdir -p /home/szf/dev/data/personal-kb/raw_vault
mkdir -p /home/szf/dev/data/personal-kb/parsed
mkdir -p /home/szf/dev/data/personal-kb/curated
mkdir -p /home/szf/dev/data/personal-kb/quarantine
mkdir -p /home/szf/dev/data/personal-kb/reports

编辑配置：

nano config/app.yaml

建议改成：

storage:
  source_registry_root: /home/szf/dev/data/personal-kb/source_registry
  raw_vault_root: /home/szf/dev/data/personal-kb/raw_vault
  parsed_root: /home/szf/dev/data/personal-kb/parsed
  curated_root: /home/szf/dev/data/personal-kb/curated
  quarantine_root: /home/szf/dev/data/personal-kb/quarantine
  reports_root: /home/szf/dev/data/personal-kb/reports

MySQL 部分先用本地 root：

mysql:
  host: 127.0.0.1
  port: 3306
  database: personal_kb
  username: root
  password: mahound  # 你的MySQL密码
  charset: utf8mb4


8. 创建测试样本

执行：

cd /home/szf/dev/pyws/pkb_sdd
bash scripts/create_sample_dataset.sh
find backend/tests/fixtures -maxdepth 5 -type f

预期能看到：

backend/tests/fixtures/中文路径/银行项目/方案.txt
backend/tests/fixtures/中文路径/银行项目/方案副本.txt
# -------------------------------------------
# 9. 第二条 Cursor 提示词：项目基线检查
# 粘贴：
```
请对当前项目做一次基线检查。

当前项目路径：
/home/szf/dev/pyws/pkb_sdd

请检查：
1. .cursor/rules 是否完整
2. docs 规范文件是否完整
3. specs/000 到 specs/008 是否完整
4. backend 骨架是否完整
5. config/app.yaml 是否存在
6. sql/001_init_schema_v1_1.sql 是否存在
7. scripts 是否可用于初始化和测试
8. 是否存在明显不符合 V1.1 设计的问题

要求：
- 只输出检查报告
- 不要修改任何文件
- 不要生成代码
- 如果发现问题，按“必须修复 / 建议修复 / 可暂缓”分类
```

10. 创建第一个功能分支

在终端执行：

cd /home/szf/dev/pyws/pkb_sdd
git checkout -b feature/001-file-inventory
11. 第三条 Cursor 提示词：让它先做实现计划

粘贴：

当前开始开发第一个功能：specs/001-file-inventory。

请严格阅读并遵守：
.cursor/rules/*.mdc
docs/sdd_development_standard.md
docs/database_standard.md
docs/coding_standard.md
specs/001-file-inventory/spec.md
specs/001-file-inventory/plan.md
specs/001-file-inventory/tasks.md
specs/001-file-inventory/acceptance.md
specs/001-file-inventory/test_cases.md
sql/001_init_schema_v1_1.sql

本轮只输出实现计划，不要修改文件。

目标是实现文件盘点 MVP：
1. 扫描指定目录
2. 识别文档候选文件
3. 计算 source_path_hash
4. 计算 sha256
5. 写入 kb_file_instance
6. 写入或更新 kb_file_content
7. 识别同 SHA256 的重复实例
8. 保证重复扫描幂等
9. 保证不移动、不删除、不重命名原始文件
10. 增加 pytest 测试

请输出：
1. 需要新增/修改哪些文件
2. 每个文件负责什么
3. 数据库表如何使用
4. CLI 命令如何设计
5. 测试用例如何设计
6. 哪些内容本阶段不做

你看 Cursor 的计划合理后，再让它开始改代码。

12. 第四条 Cursor 提示词：实现 001 最小闭环

粘贴：

请根据刚才的计划，开始实现 specs/001-file-inventory 的最小闭环。

允许修改：
1. backend/app/core/config.py
2. backend/app/core/database.py
3. backend/app/core/ids.py
4. backend/app/core/file_types.py
5. backend/app/models/file.py
6. backend/app/services/inventory_scanner.py
7. backend/app/cli/main.py
8. backend/tests/test_inventory_scanner.py

如果某些文件不存在，可以新建。

禁止修改：
1. specs/002 及之后的任何 Spec
2. sql/001_init_schema_v1_1.sql
3. README.md
4. docs 规范文件
5. 原始文件目录
6. raw_vault、parsed、curated、quarantine 的真实产物目录

实现要求：
1. 使用 pathlib.Path
2. 支持中文路径
3. SHA256 使用分块读取
4. source_path_hash 使用规范化路径计算
5. 同一路径重复扫描不得重复插入 kb_file_instance
6. 同一 SHA256 多路径文件应对应同一个 kb_file_content
7. 不移动、不删除、不重命名原始文件
8. 单文件异常不得中断整个扫描
9. CLI 支持：
   python -m app.cli.main scan --path <目录>
10. pytest 覆盖：
   - 普通文件扫描
   - 中文路径
   - 重复文件
   - 重复执行幂等
   - 原始文件不被修改

完成后请输出：
1. 修改了哪些文件
2. 如何运行测试
3. 如何运行 CLI
4. 满足了 acceptance.md 中哪些验收项
13. 跑测试

Cursor 完成后执行：

cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate
pytest -q

如果失败，把完整错误贴给 Cursor：

以下是 pytest 失败日志，请只修复 specs/001-file-inventory 范围内的问题。
不要修改 SQL 初始化脚本，不要扩大到其他 Spec。

【粘贴错误日志】
14. 手工运行扫描
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main scan --path /home/szf/dev/pyws/pkb_sdd/backend/tests/fixtures

查数据库：

mysql -uroot -p personal_kb

执行：

SELECT COUNT(*) FROM kb_file_instance;
SELECT COUNT(*) FROM kb_file_content;
SELECT file_name, sha256, is_duplicate_instance FROM kb_file_instance;
15. 第五条 Cursor 提示词：验收复核
请对 specs/001-file-inventory 做验收复核。

请检查：
1. tasks.md 中哪些任务已完成
2. acceptance.md 中 A001-A006 是否满足
3. test_cases.md 中 TC001-TC005 是否覆盖
4. 是否违反原始文件只读原则
5. 是否存在越界修改
6. 是否有必要更新文档

请只输出验收报告，不要修改文件。
16. 提交代码

确认无误后：

cd /home/szf/dev/pyws/pkb_sdd

git status
git add .
git commit -m "feat(001): implement file inventory scanner"

合并回 main：

git checkout main
git merge feature/001-file-inventory
17. 当前最关键提醒

你现在不要急着让 Cursor 做下面这些：

不要接 MinerU
不要接 MarkItDown
不要做 Streamlit 前端
不要做项目卡蒸馏
不要做向量库
不要扫描真实大目录
不要让 Codex 同时参与

先把这三个 Spec 跑通：

001-file-inventory
002-file-content-vault
003-duplicate-governance

这三个完成后，整个项目的“文件治理底座”才算稳。