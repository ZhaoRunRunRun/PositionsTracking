# PositionsTracking

科技风投资人物持仓追踪站点，基于 SEC 13F 文件自动抓取并展示著名投资人的持仓、季度变化和 10 年历史趋势。

## 已实现

- 跟踪多位著名投资人物最近 10 年的 13F 持仓历史
- 生成科技风可视化页面，适配 GitHub Pages
- 每天北京时间 08:00 / 12:00 / 18:00 自动更新
- 当 `QianYuan1437` 向 `main` 分支推送提交时自动刷新并重新部署

## 目录

- `scripts/update_data.py`：从 SEC 抓取并整理 13F 数据
- `data/positions.json`：站点展示数据
- `site/`：GitHub Pages 静态页面
- `.github/workflows/update-data.yml`：数据更新 + Pages 部署

## 本地运行

```bash
python3 scripts/update_data.py
mkdir -p site/data && cp data/positions.json site/data/positions.json
python3 -m http.server 8000 -d site
```

## GitHub Pages

发布地址：`https://qianyuan1437.github.io/PositionsTracking/`
