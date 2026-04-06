# Travel Planner

一个可运行的旅行规划后端原型：

- FastAPI API
- 动态规划路线优化
- 可替换的数据提供层（当前为 hybrid：同程机票 + 本地 12306 + 缺失边补全）
- 支持预算、候选城市、权重输入

## 启动

最推荐的方式（Homebrew + Python 3.12）：

```bash
cd travel_planner
./setup_python312.sh
./start.sh
```

如果想先检查环境：

```bash
cd travel_planner
./check_env.sh
```

最省事的直接启动方式：

```bash
cd travel_planner
./start.sh
```

手动启动方式：

```bash
cd travel_planner
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

说明：
- 如果本机 Python / pip 较旧，`numpy==2.1.1` 可能装不上
- 现在已调整为更兼容的 `numpy==2.0.2`
- `start.sh` 会自动先升级 pip 再安装依赖
- 实时同程抓取默认走无头模式，不会主动弹浏览器
- 如果只想先测规划接口，不想触发实时抓取，可用：`TONGCHENG_USE_BROWSER=0 ./start.sh`

## 测试请求

```bash
curl -X POST 'http://127.0.0.1:8010/plan' \
  -H 'Content-Type: application/json' \
  -d '{
    "start_city": "上海",
    "end_city": "上海",
    "candidate_cities": ["杭州", "南京", "苏州"],
    "days": 4,
    "budget": 2500,
    "weights": {
      "cost": 0.4,
      "experience": 0.35,
      "time": 0.1,
      "fatigue": 0.1,
      "comfort": 0.05
    },
    "pace": "balanced",
    "travel_date": "2026-04-10"
  }'
```

## 当前能力

- `/plan` 返回多种策略候选方案（当前含 DP + Greedy）
- 已加入 `TongchengProvider` 浏览器抓取桥接版本
- `/plan` 现优先混合同程实时机票、本地 `output/train_live.json` 火车结果，并只对缺失边做补全
- 支持先手动登录同程并保存浏览器会话
- 附带一个最小前端页面：`frontend/index.html`
- 后端已开启 CORS，前端可直接调用
- `/health` 健康检查接口已提供
- `POST /live/flight` 可单独调试实时机票抓取（推荐，JSON 传中文更稳）
- `GET /live/flight?from_city=西安&to_city=北京&date=2026-04-03` 也可用，但中文 query 在某些终端里可能出编码问题
- `node scripts/watch_tongcheng_flight.js` 可直接有头观看页面行为
- `node scripts/capture_tongcheng_flight_search.js` 可在你手动完成一次搜索后抓取关键网络请求与页面结果
- 目前机票脚本优先走已验证可用的 itinerary URL 模板（例如 `SIA-PEK` 这种城市代码段）
- 实时抓取失败时会局部补全，不会直接把整单服务打挂

## 浏览器抓取准备

先安装 JS 依赖：

```bash
cd travel_planner
npm install
```

如需首次登录并保存同程会话：

```bash
node scripts/tongcheng_login.js
```

脚本会打开浏览器到同程首页，你手动登录完成后，在终端按回车，就会把登录状态保存到：

`browser_state/tongcheng-storage.json`

之后后端会优先复用这个登录会话去执行抓取脚本。

## 机票页调试

如果要单独调试同程机票抓取：

```bash
node scripts/debug_tongcheng_flight.js 西安 北京 2026-04-03
```

如果你手上有已经打开成功的机票结果页直链，也可以显式传入 URL：

```bash
node scripts/debug_tongcheng_flight.js 西安 北京 2026-04-03 'https://www.ly.com/flights/itinerary/oneway/...'
```

如果要直接看结构化抓取结果：

```bash
node scripts/search_tongcheng_transport.js 西安 北京 2026-04-03
```

脚本会额外保存调试产物到：
- `runtime_data/flight_debug/*.html`
- `runtime_data/flight_debug/*.png`

当前脚本会尝试提取：
- 航司
- 航班号
- 起飞时间
- 到达时间
- 出发机场
- 到达机场
- 飞行耗时
- 是否中转/经停
- 价格

如果直达机票结果页返回 `Server error`，脚本会自动回退访问同程机票频道首页，并把页面正文片段一起返回，方便继续定位可用入口。

## 下一步建议

1. 扩展更多城市/机场/车站映射，提升真实边覆盖率
2. 把 12306 查询也做成实时接口，而不是先读本地 `train_live.json`
3. 增加酒店/景点维度的城市内优化
4. 增加 TopN 路线和 GA/OR-Tools 优化器
5. 增加 Redis 缓存和异步抓取任务
6. 接数据库保存历史方案与用户偏好
