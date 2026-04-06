"""
火车票缓存预热脚本
批量爬取热门城市对的真实数据，写入 SQLite 缓存。
运行一次后缓存 TTL=7天，期间无需再查。
"""
import asyncio
import sys
import time
from pathlib import Path

# 确保项目根目录在 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.train_cache import get_cached, set_cached, init_db

# 热门旅游城市
CITIES = [
    "北京", "上海", "杭州", "西安", "成都",
    "重庆", "苏州", "南京", "广州", "深圳",
    "厦门", "青岛", "长沙", "武汉", "昆明",
    "丽江", "桂林", "三亚", "哈尔滨", "天津",
]

# 热门日期（每个城市对只爬 3 个代表性日期：工作日、周末、节假日）
DATES = [
    "2026-04-06",   # 普通工作日
    "2026-04-11",   # 普通周末
    "2026-05-01",   # 劳动节
]

# 热门出发城市（优先爬这些城市的出发的票）
ANCHOR_CITIES = ["北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆"]


async def fetch_one(provider, from_city: str, to_city: str, date: str):
    """查询单条，返回是否成功"""
    key = (from_city, to_city, date)
    # 已缓存则跳过
    if get_cached(from_city, to_city, date):
        return "cached", key

    try:
        result = await provider.search_single_train(from_city, to_city, date)
        count = result.get("count", 0)
        set_cached(from_city, to_city, date, result)
        return ("ok", key, count) if count else ("empty", key)
    except Exception as e:
        return ("error", key, str(e))


async def run():
    init_db()
    print(f"热门城市: {len(CITIES)} 个")
    print(f"热门日期: {len(DATES)} 个")
    print(f"锚点出发城市: {ANCHOR_CITIES}")
    print()

    # 构造查询任务：锚点城市 → 所有城市
    from app.providers.train_provider import TrainProvider
    provider = TrainProvider()

    tasks = []
    for from_city in ANCHOR_CITIES:
        for to_city in CITIES:
            if from_city == to_city:
                continue
            for date in DATES:
                key = (from_city, to_city, date)
                if get_cached(from_city, to_city, date):
                    continue
                tasks.append((from_city, to_city, date))

    LOG_FILE = Path(__file__).parent.parent / "data" / "warmup.log"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    import io, atexit

    def log(*args, **kw):
        msg = " ".join(str(a) for a in args) + "\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg)
        print(*args, flush=True, **kw)

    # 清空日志
    open(LOG_FILE, "w", encoding="utf-8").close()

    log(f"待查询: {len(tasks)} 条（已缓存自动跳过）")
    log(f"预计耗时: ~{len(tasks) * 20 / 60:.0f} 分钟（每条约20秒，含 12306 反爬限制）")
    log()

    if not tasks:
        log("全部已缓存，无需预热。")
        return

    ok = empty = error = cached = 0
    t0 = time.time()

    CONCURRENCY = 3  # 并发数，太高容易被 12306 封

    for i in range(0, len(tasks), CONCURRENCY):
        batch = tasks[i:i + CONCURRENCY]
        coros = [fetch_one(provider, fc, tc, d) for fc, tc, d in batch]
        results = await asyncio.gather(*coros)

        for r in results:
            if r[0] == "ok":
                ok += 1
                log(f"  [{ok}] {r[1][0]}→{r[1][1]} {r[1][2]} : {r[2]} 条车次")
            elif r[0] == "empty":
                empty += 1
            elif r[0] == "error":
                error += 1
                log(f"  [!] {r[1][0]}→{r[1][1]} {r[1][2]} 错误: {r[2]}")

        elapsed = time.time() - t0
        done = ok + empty + error
        eta = (elapsed / done * (len(tasks) - done)) if done > 0 else 0
        log(f"进度 {done}/{len(tasks)} | 成功 {ok} | 空结果 {empty} | 失败 {error} | 预计剩余 {eta:.0f}s")

    total = time.time() - t0
    log()
    log(f"完成！总耗时 {total:.0f}s")
    log(f"成功 {ok} 条 | 空结果 {empty} | 失败 {error} 条")


if __name__ == "__main__":
    asyncio.run(run())
