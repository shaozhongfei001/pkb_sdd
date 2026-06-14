# 解析器集成规范

解析器分工：

| 解析器 | 用途 |
|---|---|
| MarkItDown | 普通 Office、HTML、XML、JSON、TXT |
| MinerU | PDF、图片、扫描件、复杂版面、高价值文档 |
| DirectParser | CSV、TXT、Markdown |

输出目录：

```text
parsed/by_hash/{sha256前2位}/{sha256}/{parser_profile}/
```
