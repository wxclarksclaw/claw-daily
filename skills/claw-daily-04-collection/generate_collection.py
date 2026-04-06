#!/usr/bin/env python3
"""
Claw Daily 04: 日报合集生成器 (重构版)
直接从 01-Digested/*.md 读取，生成带日历导航和分类排序的 index.html。
"""

import argparse, hashlib, json, os, re, sys, time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES = ["【AI技术与应用】", "【美妆个护行业】", "【国际地缘与能源】", "【企业商业与竞争】", "【前沿科技与民生】"]
CATEGORY_ORDER = {"【AI技术与应用】": 1, "【美妆个护行业】": 2, "【国际地缘与能源】": 3, "【企业商业与竞争】": 4, "【前沿科技与民生】": 5}
IMPORTANCE_THRESHOLD = 20

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"

def call_minimax_llm(prompt, model="MiniMax-M2.7", max_tokens=4000):
    import urllib.request
    import urllib.error
    import json
    if not MINIMAX_API_KEY:
        return ""
    for attempt in range(3):
        try:
            proxies = {"http": os.environ.get("HTTPS_PROXY", ""), "https": os.environ.get("HTTPS_PROXY", "")}
            proxies = {k: v for k, v in proxies.items() if v}
            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.3}).encode("utf-8")
            req = urllib.request.Request(
                f"{MINIMAX_BASE_URL}/text/chatcompletion_v2",
                data=payload,
                headers={"Authorization": f"Bearer {MINIMAX_API_KEY}", "Content-Type": "application/json"},
                method="POST"
            )
            if proxies:
                proxy_handler = urllib.request.ProxyHandler(proxies)
                opener = urllib.request.build_opener(proxy_handler)
                resp = opener.open(req, timeout=120)
            else:
                resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices")
            if not choices:
                sc = data.get("base_resp", {}).get("status_code", 0)
                sm = data.get("base_resp", {}).get("status_msg", "unknown")
                if sc == 2062:
                    wait = (attempt + 1) * 15
                    print(f"    ⏳ API 限流 (2062)，{wait}秒后重试...")
                    time.sleep(wait)
                    continue
                raise ValueError(f"API error {sc}: {sm}")
            raw = choices[0].get("message", {}).get("content", "").strip()
            reasoning = choices[0].get("message", {}).get("reasoning_content", "").strip()
            return raw or reasoning or ""
        except urllib.error.HTTPError as e:
            if attempt == 2:
                raise
            wait = (attempt + 1) * 10
            print(f"    ⚠ HTTP错误 {e.code}，{wait}秒后重试...")
            time.sleep(wait)
        except Exception as e:
            if attempt == 2:
                raise
            wait = (attempt + 1) * 10
            print(f"    ⚠ {e}，{wait}秒后重试...")
            time.sleep(wait)
    return ""

def file_hash(fp):
    return hashlib.md5(fp.read_bytes()).hexdigest()[:12]

def extract_title_and_summary(md_text):
    lines = md_text.strip().split("\n")
    title, summary, capture = "", "", False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not title:
            title = stripped[2:].replace("#", "").strip()
        if "一句话总结" in stripped:
            capture = True
            continue
        if capture and stripped:
            summary = stripped
            break
    return title, summary

def extract_source(md_text):
    lines = md_text.strip().split("\n")
    in_source = publisher = pub_time = url = ""
    for line in lines:
        stripped = line.strip()
        if "## 来源 ##" in stripped:
            in_source = True
            continue
        if in_source:
            if stripped.startswith("**发布人**"):
                publisher = stripped.replace("**发布人**", "").strip()
            elif stripped.startswith("**发布时间**"):
                t = stripped.replace("**发布时间**", "").strip()
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})", t)
                if m:
                    pub_time = f"{int(m.group(2))}月{int(m.group(3))}日{int(m.group(4))}时"
            elif "[原文链接](" in stripped:
                m = re.search(r"\[原文链接\]\((.+?)\)", stripped)
                if m:
                    url = m.group(1)
            elif stripped.startswith("## ") or stripped.startswith("# "):
                break
    parts = [p for p in [publisher, pub_time, f'<a href="{url}" target="_blank" style="color:var(--c6);text-decoration:none;">链接</a>' if url else url] if p]
    return " ".join(parts) if parts else ""

def parse_date_from_filename(name):
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""

def group_by_date(md_dir):
    groups = defaultdict(list)
    for f in sorted(md_dir.glob("*.md")):
        ds = parse_date_from_filename(f.name)
        if ds:
            groups[ds].append(f)
    return dict(sorted(groups.items()))

def md_to_html(md_text):
    lines = md_text.strip().split("\n")
    html_parts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("# 【"):
            i += 1
            continue
        if stripped.startswith("## "):
            i += 1
            continue
        if stripped.startswith("### "):
            title = re.sub(r"\s*#+$", "", stripped[4:].strip())
            html_parts.append(f'<div class="level1"><div class="level1-title">{title}</div><div class="level1-content">')
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    continue
                if nxt.startswith("### "):
                    break
                if nxt.startswith("#### "):
                    sub = re.sub(r"\s*#+$", "", nxt[5:].strip())
                    html_parts.append(f'<div class="level2"><div class="level2-title">{sub}</div><div class="level2-content">')
                    i += 1
                    while i < len(lines):
                        pt = lines[i].strip()
                        if not pt or pt.startswith("#### ") or pt.startswith("### "):
                            break
                        if pt.startswith("**"):
                            km = re.match(r"\*\*(.+?)\*\*：?(.*)", pt)
                            if km:
                                kw, val = km.group(1).strip(), km.group(2).strip()
                                html_parts.append(f'<div class="point"><span class="point-kw">{kw}</span><span class="point-val">：{val}</span></div>' if val else f'<div class="point"><span class="point-kw">{kw}</span></div>')
                            else:
                                c = re.sub(r"\*\*(.+?)\*\*", r"\1", pt)
                                if c.strip():
                                    html_parts.append(f'<div class="point">{c}</div>')
                        elif pt.startswith("- "):
                            c = re.sub(r"\*\*(.+?)\*\*", r"\1", pt[2:])
                            if c.strip():
                                html_parts.append(f'<div class="point">{c}</div>')
                        i += 1
                    html_parts.append("</div></div>")
                else:
                    i += 1
            html_parts.append("</div></div>")
        else:
            i += 1
    return "\n".join(html_parts)

def llm_batch_classify(articles_data):
    """
    一次 LLM 调用完成所有文章的分类和排序。
    返回格式：
    {
        "categories": [
            {"name": "【AI/IT】", "articles": [[序号, "总结"], ...]},
            {"name": "【快消美妆】", "articles": [[序号, "总结"], ...]},
            {"name": "【金融财经】", "articles": [[序号, "总结"], ...]},
            ...
        ]
    }
    """
    if not articles_data:
        return {"categories": []}
    
    # 构造文章列表字符串
    articles_text = "\n".join(
        f"[{i}] [{a['date']}] {a['summary']}"
        for i, a in enumerate(articles_data)
    )
    
    prompt = f"""你是一个内容分类和排序专家。请根据每篇文章的"一句话总结"，完成以下任务：

1. 分类：严格按以下5个类别分类，每篇文章必须归属其中一个类别：
   - 【AI技术与应用】：涵盖 AI Agent、大模型、多智能体框架、AI 算力/Token 生态、AI 对职场/行业影响等相关内容；
   - 【美妆个护行业】：涵盖品牌战略、产品创新、行业合规、市场趋势、供应链/成本等美妆个护全产业链内容；
   - 【国际地缘与能源】：涵盖中东局势、全球能源危机（氦气/石油）、国际政治博弈、全球经济风险（黄金/美股）等；
   - 【企业商业与竞争】：涵盖企业财报/战略、资本动作（IPO/融资）、组织变革、赛道竞争（达播/消费品牌转型）等；
   - 【前沿科技与民生】：涵盖非 AI 类科技突破（航天/军事技术/生物研究）、民生议题（宠物医疗/储能/消费观）等。

2. 排序：每个类别内按对读者价值高低排序
   - 重大新闻、首发新闻、行业拐点、突破性进展排前面
   - 同一类内容，细节丰富、有数据支撑的排前面

3. 输出格式（严格 JSON）：
{{
  "categories": [
    {{"name": "【AI技术与应用】", "articles": [[序号, "一句话总结"], [序号, "一句话总结"], ...]}},
    {{"name": "【美妆个护行业】", "articles": [[序号, "一句话总结"], ...]}},
    {{"name": "【国际地缘与能源】", "articles": [[序号, "一句话总结"], ...]}},
    {{"name": "【企业商业与竞争】", "articles": [[序号, "一句话总结"], ...]}},
    {{"name": "【前沿科技与民生】", "articles": [[序号, "一句话总结"], ...]}}
  ]
}}

文章列表：
{articles_text}

请只输出 JSON，不要输出任何解释或说明文字。"""
    
    raw = call_minimax_llm(prompt)
    if not raw:
        return default_batch_classify(articles_data)
    
    # Bug 1 fix: 优先查找 {"categories": 开头的 JSON 片段
    json_m = re.search(r'\{\s*"categories"\s*:', raw)
    if not json_m:
        print(f"  ⚠ LLM 返回无法解析: {raw[:200]}")
        return default_batch_classify(articles_data)
    
    # 从找到的位置开始，尝试匹配完整的 JSON
    json_start = json_m.start()
    json_str = raw[json_start:]
    
    try:
        result = json.loads(json_str)
        if "categories" in result and isinstance(result["categories"], list):
            return result
        print(f"  ⚠ LLM 返回结构异常: {raw[:200]}")
        return default_batch_classify(articles_data)
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON 解析失败: {e}")
        return default_batch_classify(articles_data)

def default_batch_classify(articles_data):
    """无 API Key 或 LLM 失败时，使用关键词分类"""
    ai_kw = ["AI", "人工智能", "大模型", "模型", "ChatGPT", "LLM", "算法", "AI Agent", "多智能体", "算力", "Token", "机器学习", "深度学习", "OpenAI", "Claude", "Kimi", "智谱", "腾讯混元", "百度文心", "阿里通义", "字节豆包", "自动驾驶", "机器人"]
    bz_kw = ["美妆", "护肤", "化妆品", "口红", "粉底", "精华", "面霜", "洗面奶", "防晒", "护发", "洗发", "沐浴", "香水", "眼影", "美容", "整形", "医美", "兰蔻", "雅诗兰黛", "欧莱雅", "资生堂", "SKII", "海蓝之谜", "娇韵诗", "倩碧", "理肤泉", "薇姿", "抗衰", "抗老", "成分", "原料", "配方", "次抛", "洗护", "母婴", "儿童", "孕妇", "个护", "快消", "零售"]
    geo_kw = ["中东", "能源", "石油", "天然气", "氦气", "地缘", "国际政治", "全球经济", "黄金", "美股", "美联储", "俄乌", "中美关系", "台海", "南海", "欧盟", "北约", "OPEC"]
    biz_kw = ["财报", "IPO", "融资", "投资", "收购", "并购", "上市", "组织变革", "战略", "达播", "直播带货", "品牌转型", "消费品牌", "赛道竞争", "市场份额", "营收", "利润", "亏损", "裁员"]
    tech_kw = ["航天", "卫星", "火箭", "军事", "武器", "生物", "基因", "医疗", "研究", "储能", "宠物", "消费观", "新能源", "电动汽车", "半导体", "芯片", "材料"]
    
    cat_articles = {
        "【AI技术与应用】": [],
        "【美妆个护行业】": [],
        "【国际地缘与能源】": [],
        "【企业商业与竞争】": [],
        "【前沿科技与民生】": []
    }
    
    for i, a in enumerate(articles_data):
        s = a["summary"].lower()
        if any(kw.lower() in s for kw in ai_kw):
            cat_articles["【AI技术与应用】"].append([i, a["summary"]])
        elif any(kw.lower() in s for kw in bz_kw):
            cat_articles["【美妆个护行业】"].append([i, a["summary"]])
        elif any(kw.lower() in s for kw in geo_kw):
            cat_articles["【国际地缘与能源】"].append([i, a["summary"]])
        elif any(kw.lower() in s for kw in biz_kw):
            cat_articles["【企业商业与竞争】"].append([i, a["summary"]])
        elif any(kw.lower() in s for kw in tech_kw):
            cat_articles["【前沿科技与民生】"].append([i, a["summary"]])
        else:
            cat_articles["【前沿科技与民生】"].append([i, a["summary"]])
    
    return {
        "categories": [
            {"name": "【AI技术与应用】", "articles": cat_articles["【AI技术与应用】"]},
            {"name": "【美妆个护行业】", "articles": cat_articles["【美妆个护行业】"]},
            {"name": "【国际地缘与能源】", "articles": cat_articles["【国际地缘与能源】"]},
            {"name": "【企业商业与竞争】", "articles": cat_articles["【企业商业与竞争】"]},
            {"name": "【前沿科技与民生】", "articles": cat_articles["【前沿科技与民生】"]}
        ]
    }

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐾 Claw Daily</title>
<style>
:root{--bg:#0f1318;--card:#181d24;--card2:#1c2130;--border:#2a3040;--c1:#f5c842;--c2:#e8a832;--c3:#4ec9b0;--c4:#80b0e0;--c5:#dce3ea;--c6:#7a8898;--c7:#e07840;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;background:var(--bg);color:var(--c5);line-height:1.7;font-size:1.3rem;}
.topbar{background:var(--card);border-bottom:1px solid var(--border);padding:0.7rem 1rem;display:flex;align-items:center;gap:1rem;position:sticky;top:0;z-index:100;}
.topbar h1{font-size:1.2rem;color:var(--c1);}
.topbar .title-area{display:flex;flex-direction:column;gap:0.1rem;}
.topbar .subtitle{font-size:0.65rem;color:var(--c6);line-height:1.3;}
.topbar .toggle-btn{background:var(--card2);border:1px solid var(--border);color:var(--c6);padding:0.3rem 0.7rem;border-radius:6px;cursor:pointer;font-size:0.9rem;}
.tabs{display:flex;flex:1;gap:0.35rem;overflow-x:auto;}
.tab{padding:0.42rem 0.7rem;color:var(--c6);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;font-size:0.84rem;}
.tab.active{color:var(--c3);border-bottom-color:var(--c3);}
.tab:hover{color:var(--c5);}
.main{padding:1rem;}
.section{display:none;}
.section.active{display:block;}
.sidebar-toggle{position:fixed;bottom:1rem;left:1rem;background:var(--c3);color:var(--bg);border:none;border-radius:50%;width:50px;height:50px;font-size:1.5rem;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.3);z-index:200;}
.sidebar{position:fixed;top:0;left:-280px;width:280px;height:100vh;background:var(--card);border-right:1px solid var(--border);transition:left 0.3s;z-index:300;overflow-y:auto;padding:1rem;}
.sidebar.open{left:0;}
.sidebar-close{background:none;border:none;color:var(--c6);font-size:1.5rem;cursor:pointer;float:right;}
.cal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem;clear:both;}
.cal-month{font-weight:700;color:var(--c3);}
.cal-nav-btn{cursor:pointer;color:var(--c6);padding:0.2rem 0.5rem;}
.cal-nav-btn:hover{color:var(--c5);}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;}
.cal-weekday{font-size:0.75rem;color:var(--c6);padding:0.2rem;}
.cal-day{padding:0.3rem;font-size:0.85rem;border-radius:4px;cursor:pointer;}
.cal-day.empty{}
.cal-day.has-entry{background:var(--card2);color:var(--c5);}
.cal-day.has-entry:hover{background:var(--border);}
.cal-day.today{border:1px solid var(--c1);color:var(--c1);}
.cal-day.active{background:var(--c3)!important;color:var(--bg)!important;}
.date-group{margin-bottom:1.5rem;}
.date-header{display:flex;align-items:center;gap:0.5rem;margin-bottom:0.8rem;padding-bottom:0.5rem;border-bottom:1px solid var(--border);}
.date-label{font-weight:700;color:var(--c3);font-size:1rem;}
.date-count{color:var(--c6);font-size:0.8rem;}
.category{margin-bottom:1rem;}
.category-title{color:var(--c4);font-size:0.9rem;margin-bottom:0.5rem;padding-left:0.5rem;border-left:3px solid var(--c4);}
.importance-section{margin-bottom:1rem;}
.importance-title{color:var(--c7);font-size:0.85rem;margin-bottom:0.5rem;}
.article-card{margin-bottom:0.5rem;}
.card-summary{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:0.8rem;cursor:pointer;display:flex;align-items:flex-start;gap:0.5rem;}
.card-summary:hover{border-color:var(--c3);}
.summary-text{flex:1;font-size:1.3rem;}
.importance-tag{font-size:0.75rem;background:var(--c7);color:var(--bg);padding:0.1rem 0.4rem;border-radius:4px;white-space:nowrap;}
.card-summary .arrow{color:var(--c6);margin-left:auto;transition:transform 0.25s;}
.article-card.open .card-summary .arrow{transform:rotate(180deg);}
.card-detail{display:none;background:var(--card2);border:1px solid var(--border);border-top:none;border-radius:0 0 8px 8px;padding:0.8rem;}
.article-card.open .card-detail{display:block;}
.card-title{font-size:0.9rem;color:var(--c1);margin-bottom:0.5rem;font-weight:600;}
.card-source{color:var(--c6);font-size:0.8rem;margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid var(--border);}
.level1{margin:0.5rem 0;}
.level1-title{display:flex;align-items:center;gap:0.4rem;padding:0.3rem 0.5rem;background:var(--card);border:1px solid var(--border);border-radius:6px;border-left:3px solid var(--c3);margin-bottom:0.2rem;}
.level1-title .name{font-size:1.3rem;font-weight:700;color:var(--c5);flex:1;}
.level1-content{display:none;padding-left:0.6rem;margin-top:0.2rem;}
.level1.open>.level1-content{display:block;}
.level2{margin:0.3rem 0;}
.level2-title{display:flex;align-items:center;gap:0.4rem;cursor:pointer;padding:0.2rem 0.5rem;font-size:1.3rem;color:var(--c5);}
.level2-title:hover{color:var(--c4);}
.level2-content{display:none;padding-left:0.8rem;}
.level2.open>.level2-content{display:block;}
.point{font-size:1.3rem;color:var(--c5);margin:0.2rem 0;padding-left:0.5rem;border-left:2px solid var(--border);}
.point-kw{color:var(--c7);font-weight:600;}
.point-val{color:var(--c5);}
.highlights-grid{display:grid;gap:0.5rem;}
.highlight-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:0.8rem;cursor:pointer;}
.highlight-card:hover{border-color:var(--c3);}
.highlight-meta{font-size:0.75rem;color:var(--c6);margin-bottom:0.3rem;}
.highlight-summary{font-size:0.9rem;color:var(--c5);}
</style>
</head>
<body>
<div class="topbar">
  <div class="title-area">
    <h1>🐾 Claw Daily</h1>
    <div class="subtitle">Auto-generated by Claw<br>An AI-bot Trained by Clark</div>
  </div>
  <div class="tabs" id="dynamicTabs"></div>
</div>
<div class="main">
<div class="section active" id="section-today"></div>
<div class="section" id="section-week"></div>
<div class="section" id="section-month"></div>
</div>
<div class="sidebar" id="sidebar">
<button class="sidebar-close" id="sidebarClose">×</button>
<div class="cal-header"><span class="cal-nav-btn" id="prevMonth">◀</span><span class="cal-month" id="calMonth"></span><span class="cal-nav-btn" id="nextMonth">▶</span></div>
<div class="cal-grid" id="calGrid"></div>
<div style="margin-top:1rem;"><div id="dayArticles"></div></div>
</div>
<script>
const ALL_DATA = __ALL_DATA__;
const DATE_GROUPS = __DATE_GROUPS__;
const CALENDAR_DATA = __CALENDAR_DATA__;
let currentTab = "";
let SIMULATED_DATE = "__SIMULATED_DATE__";
const todayObj = SIMULATED_DATE ? new Date(SIMULATED_DATE + "T00:00:00") : new Date();
let calYear = todayObj.getFullYear();
let calMonth = todayObj.getMonth() + 1;
const todayStr = todayObj.toISOString().split("T")[0];

// Bug 2 fix: 动态生成 Tabs
// 计算相对日期
function getRelativeDate(days) {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d.toISOString().split("T")[0];
}

function buildTabs() {
    const dates = Object.keys(DATE_GROUPS).sort(); // 已经是倒序
    const tabsContainer = document.getElementById("dynamicTabs");
    let html = "";
    
    // 计算固定偏移日期（从今天算起）
    const today = SIMULATED_DATE ? new Date(SIMULATED_DATE + "T00:00:00") : new Date();
    today.setHours(0,0,0,0);
    const toDateStr = (d) => {
        return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    };
    
    const yesterdayDate = new Date(today);
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayStr = toDateStr(yesterdayDate);
    
    const dayBeforeYesterdayDate = new Date(today);
    dayBeforeYesterdayDate.setDate(dayBeforeYesterdayDate.getDate() - 2);
    const dayBeforeYesterdayStr = toDateStr(dayBeforeYesterdayDate);
    
    // 昨天（-1天）- 始终显示，即使没有文章
    html += `<div class="tab active" data-tab="${yesterdayStr}">昨天</div>`;
    
    // 前天（-2天）- 始终显示，即使没有文章
    html += `<div class="tab" data-tab="${dayBeforeYesterdayStr}">前天</div>`;
    
    // P7D（-3到-7天）
    html += `<div class="tab" data-tab="p7d">P7D</div>`;
    
    // P14D（-8到-14天）
    html += `<div class="tab" data-tab="p14d">P14D</div>`;
    
    // 历史（-15天及之前）
    html += `<div class="tab" data-tab="history">历史</div>`;
    
    tabsContainer.innerHTML = html;
    
    // 绑定 tab 点击事件
    tabsContainer.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            tabsContainer.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            currentTab = tab.dataset.tab;
            renderCurrentTab();
        });
    });
    
    // 初始化 currentTab 为默认激活的昨天 tab
    currentTab = yesterdayStr;
}

function renderCurrentTab() {
    document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
    if (currentTab === "p14d") {
        const section = document.getElementById("section-today");
        if (!section) return;
        section.classList.add("active");
        renderDateGroups("p14d");
    } else if (currentTab === "p7d") {
        // P7D 使用 section-today
        const section = document.getElementById("section-today");
        if (!section) return;
        section.classList.add("active");
        renderDateGroups("p7d");
    } else if (currentTab === "history") {
        // 历史（-15天及之前）
        const section = document.getElementById("section-today");
        if (!section) return;
        section.classList.add("active");
        renderDateGroups("history");
    } else {
        // 日期 tab 使用 section-today
        const section = document.getElementById("section-today");
        if (!section) return;
        section.classList.add("active");
        renderDateGroups(currentTab);
    }
}

function getDateRange(tab) {
    const today = SIMULATED_DATE ? new Date(SIMULATED_DATE + "T00:00:00") : new Date();
    today.setHours(0,0,0,0);
    const toDateStr = (d) => {
        return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    };
    let start = today, end = today;
    if (tab === "p7d") {
        // P7D: -3到-7天
        end = new Date(today);
        end.setDate(end.getDate() - 3);
        start = new Date(today);
        start.setDate(start.getDate() - 7);
    } else if (tab === "p14d") {
        // P14D: -8到-14天
        end = new Date(today);
        end.setDate(end.getDate() - 8);
        start = new Date(today);
        start.setDate(start.getDate() - 14);
    } else if (tab === "history") {
        // 历史：-15天及之前
        end = new Date(today);
        end.setDate(end.getDate() - 15);
        start = new Date("1970-01-01");
    } else {
        // 单日期 tab：只显示该日期
        start = new Date(tab);
        end = new Date(tab);
    }
    return {start: toDateStr(start), end: toDateStr(end)};
}

function renderDateGroups(tab) {
    const range = getDateRange(tab);
    const container = document.getElementById("section-today");
    let html = "";
    let hasData = false;
    
    // 计算昨天和前天的日期字符串（用于判断单日期 tab）
    const today = SIMULATED_DATE ? new Date(SIMULATED_DATE + "T00:00:00") : new Date();
    today.setHours(0,0,0,0);
    const toDateStr = (d) => {
        return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    };
    const yesterdayStr = toDateStr(new Date(today.getTime() - 86400000));
    const dayBeforeYesterdayStr = toDateStr(new Date(today.getTime() - 2 * 86400000));
    
    // 如果是单日期 tab（昨天/前天），直接显示该日期（即使没有数据）
    if (tab === yesterdayStr || tab === dayBeforeYesterdayStr) {
        const dateLabel = tab.replace(/^(\d{4})-(\d{2})-(\d{2})$/, (m,y,mo,d) => `${parseInt(mo)}月${parseInt(d)}日`);
        const groups = DATE_GROUPS[tab];
        const articleCount = groups ? (groups.categories?.reduce((sum, c) => sum + (c.articles?.length || 0), 0) || 0) : 0;
        html += `<div class="date-group"><div class="date-header"><span class="date-label">📅 ${dateLabel}</span><span class="date-count">${articleCount}篇</span></div>`;
        if (groups) {
            for (const cat of groups.categories || []) {
                if (!cat.articles || cat.articles.length === 0) continue;
                html += `<div class="category"><div class="category-title">${cat.category}</div>`;
                for (const art of cat.articles) {
                    html += buildArticleCard(art);
                }
                html += `</div>`;
            }
            for (const imp of groups.importance_levels || []) {
                html += `<div class="importance-section"><div class="importance-title">${imp.label}</div>`;
                for (const art of imp.articles) {
                    html += buildArticleCard(art);
                }
                html += `</div>`;
            }
        }
        html += `</div>`;
        hasData = articleCount > 0;
    } else {
        // 多日期 tab（P7D/P14D）
        for (const [date, groups] of Object.entries(DATE_GROUPS)) {
            if (date < range.start || date > range.end) continue;
            hasData = true;
            const dateLabel = date.replace(/^(\d{4})-(\d{2})-(\d{2})$/, (m,y,mo,d) => `${parseInt(mo)}月${parseInt(d)}日`);
            html += `<div class="date-group"><div class="date-header"><span class="date-label">📅 ${dateLabel}</span><span class="date-count">${groups.articles?.length || 0}篇</span></div>`;
            for (const cat of groups.categories || []) {
                if (!cat.articles || cat.articles.length === 0) continue;
                html += `<div class="category"><div class="category-title">${cat.category}</div>`;
                for (const art of cat.articles) {
                    html += buildArticleCard(art);
                }
                html += `</div>`;
            }
            for (const imp of groups.importance_levels || []) {
                html += `<div class="importance-section"><div class="importance-title">${imp.label}</div>`;
                for (const art of imp.articles) {
                    html += buildArticleCard(art);
                }
                html += `</div>`;
            }
            html += `</div>`;
        }
    }
    
    container.innerHTML = html || "<p style='color:var(--c6);text-align:center;padding:2rem;'>暂无数据</p>";
    attachCardListeners(container);
}

function buildArticleCard(art) {
    return `<div class="article-card" data-id="${art.id}"><div class="card-summary"><span class="summary-text">${art.emoji || "📰"} ${art.summary}</span>${art.importance_level ? `<span class="importance-tag">⭐ 第${art.importance_level}级</span>` : ""}<span class="arrow">▼</span></div><div class="card-detail">${art.body || ""}${art.source ? `<div class="card-source">来源：${art.source}</div>` : ""}</div></div>`;
}

// Bug 5 fix: 点击 summary 展开所有 level1（显示1、2、3）；点击 level2 标题展开详情
function attachCardListeners(container) {
    container.querySelectorAll(".card-summary").forEach(el => {
        el.addEventListener("click", () => {
            const card = el.closest(".article-card");
            card.classList.toggle("open");
            // 展开时只显示 level1（包含1、2、3标题），不显示 level2 详情
            if (card.classList.contains("open")) {
                card.querySelectorAll(".level1").forEach(l1 => l1.classList.add("open"));
            }
        });
    });
    // 点击 level2 标题展开详情
    container.querySelectorAll(".level2-title").forEach(el => {
        el.addEventListener("click", (e) => {
            e.stopPropagation();
            el.parentElement.classList.toggle("open");
        });
    });
}

function renderCalendar() {
    const monthNames = ["","1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];
    const weekdays = ["一","二","三","四","五","六","日"];
    document.getElementById("calMonth").textContent = `${calYear}年${monthNames[calMonth]}`;
    let html = "";
    for (const w of weekdays) {html += `<div class="cal-weekday">${w}</div>`;}
    const firstDay = new Date(calYear, calMonth - 1, 1);
    const startWeekday = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;
    for (let i = 0; i < startWeekday; i++) {html += "<div class='cal-day empty'></div>";}
    const daysInMonth = new Date(calYear, calMonth, 0).getDate();
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${calYear}-${String(calMonth).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
        const hasEntry = CALENDAR_DATA.includes(dateStr);
        const isToday = dateStr === todayStr;
        let classes = "cal-day";
        if (hasEntry) classes += " has-entry";
        if (isToday) classes += " today";
        html += `<div class="${classes}" data-date="${dateStr}">${day}</div>`;
    }
    document.getElementById("calGrid").innerHTML = html;
    document.querySelectorAll(".cal-day.has-entry").forEach(el => {
        el.addEventListener("click", () => {
            document.querySelectorAll(".cal-day").forEach(d => d.classList.remove("active"));
            el.classList.add("active");
            // 点击日期切换到对应 tab，并关闭侧边栏
            const dateStr = el.dataset.date;
            const tab = document.querySelector(`.tab[data-tab="${dateStr}"]`);
            if (tab) {
                tab.click();
            }
            document.getElementById("sidebar").classList.remove("open");
        });
    });
}

function loadDayArticles(dateStr) {
    const container = document.getElementById("dayArticles");
    const groups = DATE_GROUPS[dateStr];
    if (!groups) {container.innerHTML = "<p style='color:var(--c6);font-size:0.85rem;'>这天没有文章</p>";return;}
    let html = `<div style="font-weight:700;color:var(--c3);margin-bottom:0.5rem;">${dateStr}</div>`;
    for (const cat of groups.categories || []) {
        if (!cat.articles || cat.articles.length === 0) continue;
        html += `<div style="font-size:0.8rem;color:var(--c4);margin-top:0.3rem;">${cat.category}</div>`;
        for (const art of cat.articles) {
            html += `<div style="font-size:0.85rem;padding:0.2rem 0;cursor:pointer;" onclick="scrollToArticle('${art.id}')">${art.emoji || "📰"} ${art.summary.substring(0,20)}...</div>`;
        }
    }
    container.innerHTML = html;
}

document.getElementById("prevMonth").addEventListener("click", () => {calMonth--;if (calMonth < 1) {calMonth = 12; calYear--;}renderCalendar();});
document.getElementById("nextMonth").addEventListener("click", () => {calMonth++;if (calMonth > 12) {calMonth = 1; calYear++;}renderCalendar();});
document.getElementById("sidebarClose").addEventListener("click", () => {document.getElementById("sidebar").classList.remove("open");});
// 点击 sidebar 外部关闭侧边栏
document.addEventListener("click", (e) => {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar.contains(e.target) && sidebar.classList.contains("open")) {
        sidebar.classList.remove("open");
    }
});
function scrollToArticle(id) {document.querySelectorAll(".tab")[0].click();setTimeout(() => {const el = document.querySelector(`[data-id="${id}"]`);if (el) {el.scrollIntoView({behavior:"smooth",block:"center"});el.classList.add("open");}}, 100);}

// 初始化
buildTabs();
renderCalendar();
if (currentTab === "") currentTab = Object.keys(DATE_GROUPS).sort()[0];
renderCurrentTab();
</script>
</body>
</html>
'''

def rebuild_from_cache(md_dir, cached_llm):
    """
    从缓存的 LLM 分类结果重建 date_groups 和 all_articles。
    用于没有文件变更时快速重建。
    """
    print("📖 从缓存读取文章...")
    all_files = sorted(md_dir.glob("*.md"))
    articles_data = []
    for f in all_files:
        md_text = f.read_text(encoding="utf-8")
        title, summary = extract_title_and_summary(md_text)
        source = extract_source(md_text)
        body_html = md_to_html(md_text)
        emoji_match = re.match(r'^([\U0001F300-\U0001F9FF])\s*(.*)', summary)
        if emoji_match:
            emoji = emoji_match.group(1)
            summary = emoji_match.group(2)
        else:
            emoji = "📰"
        date_str = parse_date_from_filename(f.name)
        articles_data.append({
            "file": f,
            "date": date_str,
            "title": title,
            "summary": summary,
            "source": source,
            "body": body_html,
            "emoji": emoji
        })
    
    # 构建 date_articles 映射，保留 original_idx 用于缓存还原
    # 兼容 dict format ({"categories": [...]}) and list format ([...])
    cats = cached_llm if isinstance(cached_llm, list) else cached_llm.get("categories", [])
    
    date_articles = defaultdict(list)
    article_id_counter = 0
    for cat_result in cats:
        cat_name = cat_result.get("name", "【其他】")
        for item in cat_result.get("articles", []):
            idx = item[0]  # 原始文件索引
            art = articles_data[idx]
            art_copy = {k: v for k, v in art.items() if k != "file"}
            art_copy["id"] = f"art-{article_id_counter}"
            art_copy["original_idx"] = idx  # 保存原始索引用于缓存还原
            art_copy["category"] = cat_name
            article_id_counter += 1
            date_articles[art_copy["date"]].append(art_copy)
    
    # 构建 date_groups
    date_groups = defaultdict(lambda: {"categories": [], "articles": []})
    for date_str in sorted(date_articles.keys()):
        arts = date_articles[date_str]
        cat_map = defaultdict(list)
        for a in arts:
            cat_map[a["category"]].append(a)
        date_cats = []
        for cat_result in cats:
            cat_name = cat_result.get("name", "【其他】")
            if cat_name in cat_map:
                date_cats.append({"category": cat_name, "articles": cat_map[cat_name]})
        date_groups[date_str] = {"categories": date_cats, "articles": arts}
    
    # 构建 all_articles
    article_id_counter = 0
    all_articles = []
    for cat_result in cats:
        cat_name = cat_result.get("name", "【其他】")
        for item in cat_result.get("articles", []):
            idx = item[0]
            art = articles_data[idx]
            art_copy = {k: v for k, v in art.items() if k != "file"}
            art_copy["id"] = f"art-{article_id_counter}"
            art_copy["category"] = cat_name
            all_articles.append(art_copy)
            article_id_counter += 1
    
    return dict(sorted(date_groups.items(), reverse=True)), all_articles

def date_groups_to_categories(date_groups):
    """将 date_groups 转换回 categories 格式用于缓存"""
    cat_order = ["【AI/IT】", "【快消美妆】", "【其他】"]
    categories = []
    for cat_name in cat_order:
        cats_articles = []
        for date_data in date_groups.values():
            for cat in date_data.get("categories", []):
                if cat["category"] == cat_name:
                    for art in cat["articles"]:
                        original_idx = art.get("original_idx", int(art["id"].split("-")[1]))
                        cats_articles.append([original_idx, art["summary"]])
        if cats_articles:
            categories.append({"name": cat_name, "articles": cats_articles})
    return categories

def build_date_groups_and_articles(md_dir):
    """
    新流程：先读取所有文章，再一次 LLM 分类，Python 本地按日期拆分。
    返回 (date_groups, all_articles, categories)
    """
    # 1. 读取所有 md 文件，构建 articles_data
    print("📖 读取所有文章...")
    all_files = sorted(md_dir.glob("*.md"))
    articles_data = []
    for f in all_files:
        md_text = f.read_text(encoding="utf-8")
        title, summary = extract_title_and_summary(md_text)
        source = extract_source(md_text)
        body_html = md_to_html(md_text)
        # Bug 4 fix: 检查 summary 是否以 emoji 开头
        emoji_match = re.match(r'^([\U0001F300-\U0001F9FF])\s*(.*)', summary)
        if emoji_match:
            emoji = emoji_match.group(1)
            summary = emoji_match.group(2)  # 去掉开头的 emoji
        else:
            emoji = "📰"
        date_str = parse_date_from_filename(f.name)
        articles_data.append({
            "file": f,
            "date": date_str,
            "title": title,
            "summary": summary,
            "source": source,
            "body": body_html,
            "emoji": emoji
        })
    print(f"   共 {len(articles_data)} 篇文章")
    
    # 2. 一次 LLM 调用完成分类和排序
    print("🤖 调用 LLM 分类和排序...")
    if MINIMAX_API_KEY:
        llm_result = llm_batch_classify(articles_data)
        print(f"   LLM 分成 {len(llm_result['categories'])} 个类别")
    else:
        print("   ⚠ 无 API Key，使用默认分类")
        llm_result = default_batch_classify(articles_data)
    
    categories = llm_result.get("categories", [])
    
    # 3. Python 本地处理：为每篇文章分配 ID，按日期拆分
    print("🔨 本地处理：按日期拆分...")
    article_id_counter = 0
    date_groups = defaultdict(lambda: {"categories": [], "articles": []})
    
    # 构建 date -> article 映射（移除 file 字段，避免 JSON 序列化问题）
    date_articles = defaultdict(list)
    for cat_result in categories:
        cat_name = cat_result.get("name", "【其他】")
        cat_articles_list = cat_result.get("articles", [])
        
        for item in cat_articles_list:
            idx = item[0]
            summary = item[1]
            art = articles_data[idx]
            art_copy = {k: v for k, v in art.items() if k != "file"}
            art_copy["id"] = f"art-{article_id_counter}"
            art_copy["category"] = cat_name
            article_id_counter += 1
            date_articles[art_copy["date"]].append(art_copy)
    
    # 为每个日期构建 categories
    for date_str in sorted(date_articles.keys()):
        arts = date_articles[date_str]
        # 按类别分组
        cat_map = defaultdict(list)
        for a in arts:
            cat_map[a["category"]].append(a)
        
        # 构建该日期的 categories
        date_cats = []
        for cat_result in categories:
            cat_name = cat_result.get("name", "【其他】")
            if cat_name in cat_map:
                date_cats.append({"category": cat_name, "articles": cat_map[cat_name]})
        
        date_groups[date_str] = {
            "categories": date_cats,
            "articles": arts
        }
    
    # all_articles 是按 LLM 排序的所有文章（用于一周精选）
    all_articles = []
    for cat_result in categories:
        cat_name = cat_result.get("name", "【其他】")
        for item in cat_result.get("articles", []):
            idx = item[0]
            art = articles_data[idx]
            art_copy = {k: v for k, v in art.items() if k != "file"}
            art_copy["category"] = cat_name
            all_articles.append(art_copy)
    
    # Bug 3 fix: 日期倒序（最近日期在前）
    return dict(sorted(date_groups.items(), reverse=True)), all_articles, categories

def main():
    parser = argparse.ArgumentParser(description="Claw Daily 04: 生成日报合集 index.html")
    parser.add_argument("--md-dir", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--processed", type=str, default=None)
    parser.add_argument("--reset", action="store_true", help="重置所有文章的分类状态（调试用，不调用 LLM）")
    parser.add_argument("--simulated-date", type=str, default=None, help="模拟日期，如 2026-04-05")
    args = parser.parse_args()
    claw_daily_dir = Path(os.environ.get("CLAW_DAILY_DIR", "/Users/wxclarksclaw/.openclaw/workspace/Claw Daily"))
    md_dir = Path(args.md_dir) if args.md_dir else claw_daily_dir / "01-Digested"
    output_file = Path(args.output) if args.output else claw_daily_dir / "04-Output" / "index.html"
    processed_file = Path(args.processed) if args.processed else claw_daily_dir / "04-Output" / "processed.json"
    llm_cache_file = claw_daily_dir / "04-Output" / "llm_cache.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not md_dir.exists():
        print(f"❌ 目录不存在: {md_dir}")
        sys.exit(1)
    
    print(f"\n🔍 扫描目录: {md_dir}")
    all_files = list(md_dir.glob("*.md"))
    print(f"   共 {len(all_files)} 个 md 文件")
    
    # 读取 LLM 缓存
    cached_llm = {"categories": []}
    classified_summaries = set()  # 用 summary 来匹配已分类的文章
    if llm_cache_file.exists():
        cache_data = json.loads(llm_cache_file.read_text(encoding="utf-8"))
        # 兼容旧格式（直接是 list）和新格式（dict with "categories"）
        if isinstance(cache_data, list):
            cached_llm = {"categories": cache_data}
        else:
            cached_llm = cache_data
        # 从缓存中提取已分类的文章 summary（用于匹配）
        for cat in cached_llm.get("categories", []):
            for item in cat.get("articles", []):
                classified_summaries.add(item[1])  # item[1] is the summary
    
    # 读取已处理文件状态
    processed = {}
    if processed_file.exists():
        processed = json.loads(processed_file.read_text(encoding="utf-8"))
    
    # 调试模式：只清空 processed 中的文章状态，不调用 LLM
    if args.reset:
        print("🔄 调试模式：重置所有文章状态")
        processed = {"articles": {}}
        processed_file.write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已重置 {processed_file}")
        return
    
    new_files = [f for f in all_files if f.name not in processed.get("articles", {})]
    changed_files = [f for f in all_files if f.name in processed.get("articles", {}) and processed["articles"].get(f.name, {}).get("hash") != file_hash(f)]
    print(f"   新文件: {len(new_files)}, 变更文件: {len(changed_files)}")
    
    # 构建所有文章数据
    print("\n📖 读取所有文章...")
    articles_data = []
    for f in sorted(all_files):
        md_text = f.read_text(encoding="utf-8")
        title, summary = extract_title_and_summary(md_text)
        source = extract_source(md_text)
        body_html = md_to_html(md_text)
        emoji_match = re.match(r'^([\U0001F300-\U0001F9FF])\s*(.*)', summary)
        if emoji_match:
            emoji = emoji_match.group(1)
            summary = emoji_match.group(2)
        else:
            emoji = "📰"
        date_str = parse_date_from_filename(f.name)
        articles_data.append({
            "file": f,
            "date": date_str,
            "title": title,
            "summary": summary,
            "source": source,
            "body": body_html,
            "emoji": emoji
        })
    print(f"   共 {len(articles_data)} 篇文章")
    
    # 找出需要 LLM 分类的新文章（summary 不在缓存中的）
    new_article_indices = [i for i, a in enumerate(articles_data) if a["summary"] not in classified_summaries]
    print(f"   需要 LLM 分类的新文章: {len(new_article_indices)}")
    
    if new_article_indices:
        # 只对新增文章调用 LLM
        print("\n🤖 对新增文章调用 LLM 分类...")
        new_articles = [articles_data[i] for i in new_article_indices]
        new_result = llm_batch_classify(new_articles)
        
        # 合并到缓存
        # 先重新映射索引：将 new_result 中的索引（相对于 new_articles）转为原始索引
        for cat_idx, cat in enumerate(new_result.get("categories", [])):
            for art_idx, item in enumerate(cat.get("articles", [])):
                original_idx = new_article_indices[item[0]]
                new_result["categories"][cat_idx]["articles"][art_idx][0] = original_idx
        
        # 如果缓存为空，直接使用 new_result
        if not cached_llm.get("categories"):
            cached_llm = new_result
        else:
            # 合并到现有缓存
            for old_cat in cached_llm.get("categories", []):
                for new_cat in new_result.get("categories", []):
                    if old_cat["name"] == new_cat["name"]:
                        # 合并文章列表
                        old_indices = {item[0] for item in old_cat["articles"]}
                        for new_item in new_cat["articles"]:
                            if new_item[0] not in old_indices:
                                old_cat["articles"].append(new_item)
                        break
        
        # 保存合并后的缓存
        llm_cache_file.write_text(json.dumps(cached_llm, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已更新 LLM 缓存")
        categories = cached_llm
    else:
        print("✅ 所有文章已分类，使用缓存")
        categories = cached_llm
    
    # 重建 date_groups
    print("\n📊 重建文章结构...")
    date_groups, all_articles = rebuild_from_cache(md_dir, categories)
    
    calendar_data = list(date_groups.keys())
    new_processed = {"last_generated": datetime.now().isoformat(), "articles": {}}
    for f in md_dir.glob("*.md"):
        new_processed["articles"][f.name] = {"hash": file_hash(f), "date": parse_date_from_filename(f.name)}
    
    processed_file.write_text(json.dumps(new_processed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已更新 {processed_file}")
    print(f"\n📝 生成 index.html...")
    html = HTML_TEMPLATE
    simulated_date = args.simulated_date or ""
    html = html.replace("__ALL_DATA__", json.dumps({"date_groups": date_groups}, ensure_ascii=False))
    html = html.replace("__DATE_GROUPS__", json.dumps(date_groups, ensure_ascii=False))
    html = html.replace("__CALENDAR_DATA__", json.dumps(calendar_data, ensure_ascii=False))
    html = html.replace("__SIMULATED_DATE__", simulated_date)
    output_file.write_text(html, encoding="utf-8")
    print(f"✅ 已生成 {output_file}")

if __name__ == "__main__":
    main()
