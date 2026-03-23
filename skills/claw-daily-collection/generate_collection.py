#!/usr/bin/env python3
"""
Claw Daily 日报合集生成器 v1.0
- 扫描 Claw Daily HTML 文件
- 生成带日历导航的合集页面
- 支持手机端适配
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
import base64
from datetime import datetime
from calendar import monthrange

# 配置路径
SOURCE_DIR = "/Users/wxclarksclaw/.openclaw/workspace/Claw Daily/03-Claw's Daily"
OUTPUT_DIR = "/Users/wxclarksclaw/.openclaw/workspace/Claw Daily/04-Claw's Daily Collection"
LOGO_PATH = "/Users/wxclarksclaw/.openclaw/workspace/Logo/Head.JPEG"

def get_logo_base64():
    """获取 Logo 的 base64 编码"""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def parse_filename(filename):
    """
    解析文件名，提取日期信息
    文件名格式: ClawDaily-YYYY-MM-DD-XX.html
    返回: (date_str, display_name) 或 None
    """
    pattern = r'ClawDaily-(\d{4})-(\d{2})-(\d{2})-(\d{2})\.html'
    match = re.match(pattern, filename)
    if match:
        year, month, day, index = match.groups()
        date_str = f"{year}{month}{day}"
        display_name = f"ClawDaily-{year}-{month}-{day}"
        return {
            'date_str': date_str,
            'year': int(year),
            'month': int(month),
            'day': int(day),
            'index': int(index),
            'display_name': display_name,
            'filename': filename
        }
    return None

def get_article_files(source_dir):
    """获取所有文章文件，按日期排序"""
    articles = []
    source = Path(source_dir)
    
    if not source.exists():
        print(f"⚠️ 源目录不存在: {source_dir}")
        return articles
    
    for html_file in source.glob("*.html"):
        info = parse_filename(html_file.name)
        if info:
            info['full_path'] = str(html_file)
            articles.append(info)
    
    # 按日期倒序排列
    articles.sort(key=lambda x: (x['date_str'], x['index']), reverse=True)
    return articles

def extract_article_info(html_path):
    """从 HTML 中提取标题和其他信息"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # 提取标题
        title_elem = soup.find('h1') or soup.find('title')
        title = title_elem.get_text(strip=True) if title_elem else "Claw Daily"
        
        # 提取正文内容 - 获取 body 内的所有内容
        body = soup.find('body')
        content = str(body) if body else ""
        
        return {
            'title': title,
            'content': content
        }
    except Exception as e:
        print(f"⚠️ 读取文件失败 {html_path}: {e}")
        return {'title': 'Claw Daily', 'content': ''}

def extract_body_content(html_path):
    """从 HTML 文件中提取 body 内容，同时保留 head 中的 style"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # 提取 head 中的 style
        styles = []
        for style_tag in soup.find_all('style'):
            styles.append(style_tag.decode_contents())
        style_content = '\n'.join(styles)
        
        # 提取 body 的内部内容
        body = soup.find('body')
        body_content = body.decode_contents() if body else ''
        
        # 组合：保留原始样式
        if style_content:
            return f'<style>{style_content}</style>\n{body_content}'
        return body_content
    except Exception as e:
        print(f"⚠️ 读取内容失败 {html_path}: {e}")
        return ""

def format_date_cn(year, month, day):
    """格式化中文日期"""
    return f"{year}年{month}月{day}日"

def format_date_en(year, month, day):
    """格式化英文日期"""
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    suffix = 'th' if day not in [1,21,31,2,22,3,23] else ('st' if day in [1,21,31] else ('nd' if day in [2,22] else 'rd'))
    return f"{months[month]} {day}{suffix} {year}"

def get_calendar_data(articles):
    """获取日历数据，按月份组织"""
    dates_by_month = {}
    for article in articles:
        year_month = f"{article['year']}{article['month']:02d}"
        day = article['day']
        if year_month not in dates_by_month:
            dates_by_month[year_month] = {}
        if day not in dates_by_month[year_month]:
            dates_by_month[year_month][day] = 0
        dates_by_month[year_month][day] += 1
    return dates_by_month

def generate_collection():
    """生成合集页面"""
    logo_base64 = get_logo_base64()
    logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" class="logo-img" alt="Logo">' if logo_base64 else '🐾'
    
    # 获取文章列表
    articles = get_article_files(SOURCE_DIR)
    
    if not articles:
        print("⚠️ 没有找到任何日报文件")
        return None
    
    print(f"📚 找到 {len(articles)} 篇日报")
    
    # 获取日历数据
    calendar_data = get_calendar_data(articles)
    calendar_json = str(calendar_data).replace("'", '"')
    
    # 生成目录和内容
    toc_items = []
    content_items = []
    
    for i, article in enumerate(articles):
        date_key = article['date_str']
        
        # 生成目录项
        date_display = format_date_cn(article['year'], article['month'], article['day'])
        toc_items.append(
            f'<div class="toc-item" onclick="showArticle({i})" data-index="{i}" data-date="{date_key}">'
            f'<div class="toc-date">{date_display}</div>'
            f'<div class="toc-title">{article["display_name"]}</div>'
            f'</div>'
        )
        
        # 读取内容（只提取 body 部分）
        html_content = extract_body_content(article['full_path'])
        content_items.append(
            f'<div id="article-{i}" class="article-wrapper" style="display:none;">'
            f'<div class="article-header">'
            f'<h2>{article["display_name"]}</h2>'
            f'<div class="article-date">{date_display}</div>'
            f'</div>'
            f'<div class="article-content">{html_content}</div>'
            f'</div>'
        )
    
    # 生成完整 HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Claw Daily Collection</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        :root {{
            --bg: #0f1318;
            --card: #181d24;
            --border: #2a3040;
            --text: #d4dce8;
            --muted: #6b7a94;
            --gold: #e8c26b;
            --teal: #5fb3a1;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        html, body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            overflow: hidden;
        }}
        
        /* 手机端顶部按钮 */
        .mobile-toggle {{
            display: none;
            position: relative;
            z-index: 1000;
            background: rgba(95, 179, 161, 0.2);
            border: 1px solid var(--teal);
            color: var(--teal);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 14px;
            cursor: pointer;
            backdrop-filter: blur(5px);
        }}
        
        .header {{
            height: 65px;
            background: linear-gradient(90deg, #181d24 0%, #0f1318 100%);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            padding: 0 20px;
            justify-content: space-between;
        }}
        
        .logo-section {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .logo-img {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid var(--teal);
        }}
        
        .logo-text {{
            font-size: 20px;
            font-weight: 700;
            color: var(--gold);
        }}
        
        .logo-sub {{
            font-size: 11px;
            color: var(--muted);
        }}
        
        .main-container {{
            display: flex;
            height: calc(100vh - 65px);
        }}
        
        .sidebar {{
            width: 300px;
            background: var(--card);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transition: transform 0.3s ease;
        }}
        
        .calendar-section {{
            padding: 15px;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }}
        
        .calendar-title {{
            font-size: 13px;
            color: var(--gold);
            font-weight: 600;
            margin-bottom: 10px;
        }}
        
        .month-nav {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        
        .month-btn {{
            background: rgba(95, 179, 161, 0.15);
            border: 1px solid rgba(95, 179, 161, 0.3);
            color: var(--teal);
            width: 28px;
            height: 28px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .month-btn:hover {{
            background: rgba(95, 179, 161, 0.3);
        }}
        
        .month-title {{
            font-size: 14px;
            color: var(--text);
            font-weight: 600;
        }}
        
        .weekdays {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 2px;
            margin-bottom: 4px;
        }}
        
        .weekday {{
            text-align: center;
            font-size: 11px;
            color: var(--muted);
            padding: 4px 0;
        }}
        
        .days-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 2px;
        }}
        
        .day {{
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            border-radius: 4px;
            color: var(--muted);
            min-height: 32px;
        }}
        
        .day.empty {{
            background: transparent;
        }}
        
        .day.has-article {{
            background: rgba(95, 179, 161, 0.2);
            color: var(--teal);
            cursor: pointer;
            font-weight: 600;
        }}
        
        .day.has-article:hover {{
            background: rgba(95, 179, 161, 0.4);
        }}
        
        .article-count {{
            position: absolute;
            top: 2px;
            right: 2px;
            width: 14px;
            height: 14px;
            background: var(--teal);
            color: var(--bg);
            font-size: 9px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        
        .day-wrapper {{
            position: relative;
        }}
        
        .toc-section {{
            flex: 1;
            overflow-y: auto;
            padding: 15px;
        }}
        
        .toc-header {{
            font-size: 13px;
            color: var(--gold);
            font-weight: 600;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }}
        
        .toc-item {{
            padding: 10px;
            margin-bottom: 6px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }}
        
        .toc-item:hover {{
            background: rgba(95, 179, 161, 0.1);
            border-color: rgba(95, 179, 161, 0.3);
        }}
        
        .toc-item.active {{
            background: rgba(95, 179, 161, 0.2);
            border-color: var(--teal);
        }}
        
        .toc-date {{
            font-size: 11px;
            color: var(--teal);
            margin-bottom: 3px;
        }}
        
        .toc-title {{
            font-size: 13px;
            color: var(--text);
            font-weight: 500;
        }}
        
        .content-area {{
            flex: 1;
            overflow-y: auto;
            background: var(--bg);
        }}
        
        .welcome {{
            text-align: center;
            padding: 80px 40px;
            background: linear-gradient(180deg, #181d24 0%, #0f1318 100%);
            min-height: 100%;
        }}
        
        .welcome-logo {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid var(--teal);
            margin-bottom: 30px;
        }}
        
        .welcome h1 {{
            font-size: 32px;
            color: var(--gold);
            margin-bottom: 15px;
        }}
        
        .welcome .subtitle {{
            font-size: 16px;
            color: var(--muted);
            margin-bottom: 10px;
        }}
        
        .welcome .tagline {{
            font-size: 13px;
            color: var(--muted);
            margin-bottom: 10px;
            font-style: italic;
        }}
        
        .welcome .tip {{
            font-size: 13px;
            color: var(--teal);
            margin-top: 30px;
            padding: 15px 25px;
            background: rgba(95, 179, 161, 0.1);
            border: 1px solid rgba(95, 179, 161, 0.3);
            border-radius: 10px;
            display: inline-block;
        }}
        
        .article-wrapper {{
            display: none;
            padding: 0;
        }}
        
        .article-wrapper.active {{
            display: block;
        }}
        
        .article-header {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
            background: var(--card);
        }}
        
        .article-header h2 {{
            font-size: 20px;
            color: var(--gold);
            margin-bottom: 8px;
        }}
        
        .article-date {{
            font-size: 13px;
            color: var(--muted);
        }}
        
        .article-content {{
            padding: 0;
        }}
        
        /* 保持原文档样式，不做额外覆盖 */
        
        .hidden {{
            display: none !important;
        }}
        
        ::-webkit-scrollbar {{
            width: 6px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--bg);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 3px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--muted);
        }}
        
        /* ==================== 手机端响应式样式 ==================== */
        @media screen and (max-width: 768px) {{
            .mobile-toggle {{
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            
            .header {{
                padding-left: 12px;
                padding-right: 12px;
                height: 55px;
                flex-direction: row-reverse;
                justify-content: flex-end;
            }}
            
            .logo-section {{
                gap: 8px;
            }}
            
            .logo-img {{
                width: 32px;
                height: 32px;
            }}
            
            .logo-text {{
                font-size: 16px;
            }}
            
            .logo-sub {{
                display: none;
            }}
            
            .sidebar {{
                position: fixed;
                left: 0;
                top: 55px;
                height: calc(100vh - 55px);
                width: 85%;
                max-width: 300px;
                z-index: 999;
                transform: translateX(-100%);
                box-shadow: 4px 0 20px rgba(0,0,0,0.5);
            }}
            
            .sidebar.open {{
                transform: translateX(0);
            }}
            
            .main-container {{
                height: calc(100vh - 55px);
            }}
            
            .content-area {{
                width: 100%;
            }}
            
            .welcome {{
                padding: 40px 20px !important;
            }}
            
            .welcome-logo {{
                width: 70px !important;
                height: 70px !important;
                margin-bottom: 20px !important;
            }}
            
            .welcome h1 {{
                font-size: 24px !important;
                margin-bottom: 10px !important;
            }}
            
            .welcome .tagline {{
                font-size: 12px !important;
            }}
            
            .article-header {{
                padding: 15px;
            }}
            
            .article-header h2 {{
                font-size: 18px;
            }}
            
            .article-content .container {{
                padding: 10px !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <button class="mobile-toggle" id="sidebarToggle" onclick="toggleSidebar()">
            <span id="toggleIcon">☰</span>
            <span id="toggleText">菜单</span>
        </button>
        <div class="logo-section">
            {logo_html}
            <div>
                <div class="logo-text">Claw's Daily</div>
                <div class="logo-sub">Daily News Digest Collection</div>
            </div>
        </div>
    </div>
    
    <div class="main-container">
        <div class="sidebar" id="sidebar">
            <div class="calendar-section">
                <div class="calendar-title">📅 日历 Calendar</div>
                <div class="month-nav">
                    <button class="month-btn" onclick="changeMonth(-1)">◀</button>
                    <div class="month-title" id="currentMonth"></div>
                    <button class="month-btn" onclick="changeMonth(1)">▶</button>
                </div>
                <div class="weekdays" id="weekdays"></div>
                <div class="days-grid" id="daysGrid"></div>
            </div>
            <div class="toc-section">
                <div class="toc-header">📚 日报列表 Daily List</div>
                <div id="tocList">
                    {''.join(toc_items)}
                </div>
            </div>
        </div>
        
        <div class="content-area" id="contentArea">
            <div class="welcome" id="welcome">
                {f'<img src="data:image/jpeg;base64,{logo_base64}" class="welcome-logo" alt="Logo">' if logo_base64 else '<div style="font-size: 60px; margin-bottom: 20px;">🐾</div>'}
                <h1>Claw's Daily Collection</h1>
                <div class="subtitle">Claw的日报合集</div>
                <div class="tagline">Claw is an AI-bot trained by Clark Wang</div>
                <div class="tip">
                    📱 点击左上角「菜单」查看日历和日报列表<br>
                    💻 左侧选择日期查看日报内容
                </div>
            </div>
            {''.join(content_items)}
        </div>
    </div>
    
    <script>
        const calendarData = {calendar_json};
        let currentYearMonth = Object.keys(calendarData).sort().pop() || new Date().toISOString().slice(0,7).replace('-','');
        let currentIndex = null;
        let isMobile = window.innerWidth <= 768;
        let sidebarOpen = false;
        
        const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
        const months = ['', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
        
        function getDaysInMonth(year, month) {{
            return new Date(year, month, 0).getDate();
        }}
        
        function getFirstWeekday(year, month) {{
            return new Date(year, month - 1, 1).getDay();
        }}
        
        function checkMobile() {{
            isMobile = window.innerWidth <= 768;
            if (isMobile && sidebarOpen) {{
                document.getElementById('sidebar').classList.remove('open');
                sidebarOpen = false;
                updateToggleButton();
            }}
        }}
        
        function toggleSidebar() {{
            const sidebar = document.getElementById('sidebar');
            sidebarOpen = !sidebarOpen;
            sidebar.classList.toggle('open', sidebarOpen);
            updateToggleButton();
        }}
        
        function updateToggleButton() {{
            document.getElementById('toggleIcon').textContent = sidebarOpen ? '✕' : '☰';
            document.getElementById('toggleText').textContent = sidebarOpen ? '关闭' : '菜单';
        }}
        
        function renderCalendar() {{
            const year = parseInt(currentYearMonth.substring(0, 4));
            const month = parseInt(currentYearMonth.substring(4, 6));
            document.getElementById('currentMonth').textContent = `${{year}}年 ${{months[month]}}`;
            
            document.getElementById('weekdays').innerHTML = weekdays.map(wd => 
                `<div class="weekday">${{wd}}</div>`
            ).join('');
            
            const daysInMonth = getDaysInMonth(year, month);
            const firstWeekday = getFirstWeekday(year, month);
            let html = '';
            
            for (let i = 0; i < firstWeekday; i++) {{
                html += '<div class="day empty"></div>';
            }}
            
            const monthData = calendarData[currentYearMonth] || {{}};
            
            for (let day = 1; day <= daysInMonth; day++) {{
                const hasArticle = day in monthData;
                const count = monthData[day] || 0;
                
                if (hasArticle) {{
                    const dayStr = String(day).padStart(2, '0');
                    html += `
                        <div class="day-wrapper">
                            <div class="day has-article" onclick="jumpToDate('${{currentYearMonth}}${{dayStr}}')">
                                ${{day}}
                            </div>
                            ${{count > 1 ? `<span class="article-count">${{count}}</span>` : ''}}
                        </div>
                    `;
                }} else {{
                    html += `<div class="day">${{day}}</div>`;
                }}
            }}
            
            document.getElementById('daysGrid').innerHTML = html;
        }}
        
        function changeMonth(delta) {{
            let year = parseInt(currentYearMonth.substring(0, 4));
            let month = parseInt(currentYearMonth.substring(4, 6));
            month += delta;
            if (month > 12) {{ month = 1; year++; }}
            if (month < 1) {{ month = 12; year--; }}
            currentYearMonth = `${{year}}${{String(month).padStart(2, '0')}}`;
            renderCalendar();
        }}
        
        function showArticle(index) {{
            currentIndex = index;
            document.getElementById('welcome').style.display = 'none';
            
            document.querySelectorAll('.article-wrapper').forEach(el => {{
                el.style.display = 'none';
                el.classList.remove('active');
            }});
            
            document.querySelectorAll('.toc-item').forEach(el => {{
                el.classList.remove('active');
            }});
            
            const article = document.getElementById('article-' + index);
            if (article) {{
                article.style.display = 'block';
                article.classList.add('active');
            }}
            
            const tocItem = document.querySelector('.toc-item[data-index="' + index + '"]');
            if (tocItem) {{
                tocItem.classList.add('active');
            }}
            
            // 手机端：选择文章后自动隐藏侧边栏
            if (isMobile) {{
                document.getElementById('sidebar').classList.remove('open');
                sidebarOpen = false;
                updateToggleButton();
            }}
            
            // 滚动到顶部
            document.getElementById('contentArea').scrollTop = 0;
        }}
        
        function jumpToDate(datePrefix) {{
            const tocItem = document.querySelector('.toc-item[data-date^="' + datePrefix + '"]');
            if (tocItem) {{
                const index = tocItem.getAttribute('data-index');
                showArticle(parseInt(index));
                tocItem.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}
        
        // 监听窗口大小变化
        window.addEventListener('resize', checkMobile);
        
        // 初始化
        renderCalendar();
        checkMobile();
    </script>
</body>
</html>'''
    
    return html

def main():
    print("📝 生成 Claw Daily 合集页面...")
    
    # 确保输出目录存在
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成 HTML
    html_content = generate_collection()
    
    if html_content is None:
        print("❌ 生成失败")
        return
    
    # 写入文件
    output_file = output_path / "index.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ 合集已生成: {output_file}")
    print(f"📊 共包含 {len([f for f in Path(SOURCE_DIR).glob('*.html') if parse_filename(f.name)])} 篇日报")

if __name__ == '__main__':
    main()
