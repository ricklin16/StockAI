#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股全量历史日交易数据采集程序（按交易所分别获取股票列表版本）
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='sqlite3')

import tushare as ts
import akshare as ak
import pandas as pd
import sqlite3
import time
from datetime import datetime, date, timedelta
from tqdm import tqdm
from typing import Optional, Dict, List, Tuple
import logging


# ==================== 配置区域 ====================
DB_PATH = "a_stock_data.db"
REQUEST_INTERVAL = 0.5      # 请求间隔（秒），建议0.5秒以上
MAX_RETRIES = 3
ADJUST = "qfq"              # qfq: 前复权, hfq: 后复权, "": 不复权
VERBOSE = True
SPEC_STOCKS = ('sh689009',)   # 需要通过TS接口获取数据的股票
TS_TOKEN = '8b001669116f59aed7f94ef845ec0a9be810ac310df5b7e2f4147b93'
ts.set_token(TS_TOKEN)
pro = ts.pro_api()
# =================================================


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO if VERBOSE else logging.WARNING,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()


def get_stock_list_by_market() -> Dict[str, pd.DataFrame]:
    """
    按市场分别获取股票列表
    返回: {'sh': df_sh, 'sz': df_sz, 'bj': df_bj}
    """
    result = {}
    
    # 1. 上交所股票（主板A + 科创板）
    try:
        # 主板A股
        df_sh_main = ak.stock_info_sh_name_code("主板A股")
        df_sh_main.insert(0, "market", "沪市主板")
        # 科创板
        df_sh_kcb = ak.stock_info_sh_name_code("科创板")
        df_sh_kcb.insert(0, "market", "科创板")
        # 合并上交所数据
        result['sh'] = pd.concat([df_sh_main, df_sh_kcb], ignore_index=True)
        logger.info(f"上交所: 主板 {len(df_sh_main)} 只, 科创板 {len(df_sh_kcb)} 只, 合计 {len(result['sh'])} 只")
    except Exception as e:
        logger.error(f"获取上交所股票列表失败: {e}")
        result['sh'] = pd.DataFrame()
    
    # 2. 深交所股票
    try:
        # 合并深交所数据
        result['sz'] = ak.stock_info_sz_name_code("A股列表")
        # 拆分深交所数据
        # 查看代码列的实际名称（通常是 '代码' 或 'A股代码'）
        code_col = '代码' if '代码' in result['sz'].columns else 'A股代码'
        # 将代码转换为字符串并填充为6位
        result['sz'][code_col] = result['sz'][code_col].astype(str).str.zfill(6)
        # 根据代码前缀区分主板和创业板（主板：00、01、02、03开头，创业板：300、301、302开头）                
        is_chuangye = result['sz'][code_col].str.startswith(('300', '301', '302'))
        # 创建主板和创业板DataFrame
        df_sz_main = result['sz'][~is_chuangye].copy()
        df_sz_cyb = result['sz'][is_chuangye].copy()
        # 添加板块标识列
        result['sz'].insert(0, "market", "深市")
        df_sz_main.insert(0, 'market', '深市主板')
        df_sz_cyb.insert(0, 'market', '创业板')                        
        logger.info(f"深交所: 主板 {len(df_sz_main)} 只, 创业板 {len(df_sz_cyb)} 只, 合计 {len(result['sz'])} 只")

        # 查看示例
        #print("\n主板示例:")
        #print(df_sz_main.head(3))
        #print("\n创业板示例:")
        #print(df_sz_cyb.head(3))

    except Exception as e:
        logger.error(f"获取深交所股票列表失败: {e}")
        result['sz'] = pd.DataFrame()
    
    # 3. 北交所股票
    try:
        result['bj'] = ak.stock_info_bj_name_code()
        result['bj'].insert(0, "market", "北交所")
        logger.info(f"北交所: {len(result['bj'])} 只")
    except Exception as e:
        logger.error(f"获取北交所股票列表失败: {e}")
        result['bj'] = pd.DataFrame()
    
    return result


def get_stock_list_unified() -> pd.DataFrame:
    """
    备选方案：一次性获取所有A股（如果按市场获取失败时使用）
    """
    try:
        df = ak.stock_info_a_code_name()
        df.columns = ["code", "name"]
        df["code"] = df["code"].astype(str).str.zfill(6)
        df.insert(0, "market", "A股")
        logger.info(f"统一接口获取成功，共 {len(df)} 只股票")
        return df
    except Exception as e:
        logger.error(f"统一接口获取失败: {e}")
        return pd.DataFrame()


def init_database(db_path: str):
    """初始化数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 股票日线数据表（新增 market 字段）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily (
            code TEXT NOT NULL,
            name TEXT,
            market TEXT,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turnover REAL,
            pct_chg REAL,
            PRIMARY KEY (code, date)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_code ON stock_daily(code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON stock_daily(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_market ON stock_daily(market)')
    
    # 进度表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_progress (
            code TEXT PRIMARY KEY,
            name TEXT,
            market TEXT,
            last_update_date TEXT,
            update_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"数据库初始化完成: {db_path}")


def download_stock_data(code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    下载单只股票的日线数据
    """    
    for attempt in range(MAX_RETRIES):
        try:
            if start_date is not None:
                start_date = start_date.replace("-", "")

            if code in SPEC_STOCKS:                
                code = f"{code[-6:]}.{code[:2]}"
                df = pro.daily(
                    ts_code=code, 
                    start_date=start_date or "19900101", 
                    end_date=end_date or datetime.now().strftime("%Y%m%d")
                )

                df.rename(columns={
                    'ts_code': 'code',
                    'trade_date': 'date'
                }, inplace=True)                
            else:                
                df = ak.stock_zh_a_daily(
                    symbol=code,
                    #period="daily",
                    start_date=start_date or "19900101",
                    end_date=end_date or datetime.now().strftime("%Y%m%d"),
                    adjust=ADJUST
                )
            
            if df is None or df.empty:                
                return None
            
            return df
            
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"股票 {code} 第{attempt+1}次下载失败，{REQUEST_INTERVAL*2}秒后重试...")
                time.sleep(REQUEST_INTERVAL * 2)
            else:
                logger.error(f"股票 {code} 下载失败: {e}")
                return None
        
        time.sleep(REQUEST_INTERVAL)
    
    return None


def save_to_database(df: pd.DataFrame, code: str, name: str, market: str):
    """将数据保存到数据库"""
    if df is None or df.empty:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0

    # 将日期列转换为字符串
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d")
    
    for _, row in df.iterrows():
        try:
            market_code = f"{market}{code}"
            if market_code in SPEC_STOCKS:      # TUSHARE接口
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_daily 
                    (code, name, market, date, open, high, low, close, volume, amount, pct_chg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code, name, market, row.get("date"), row.get("open"),
                    row.get("high"), row.get("low"), row.get("close"),
                    row.get("vol"), row.get("amount"), row.get("pct_chg") 
                ))
            else:   # AKSHARE接口
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_daily 
                    (code, name, market, date, open, high, low, close, volume, amount, turnover)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code, name, market, row.get("date"), row.get("open"),
                    row.get("high"), row.get("low"), row.get("close"),
                    row.get("volume"), row.get("amount"), row.get("turnover")
                ))
            inserted += 1
        except Exception as e:
            logger.error(f"保存数据失败 {code} {row.get('date')}: {e}")
    
    conn.commit()
    conn.close()
    return inserted


def update_progress(code: str, name: str, market: str, last_date: str, success: bool = True):
    """更新进度"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if success:
        cursor.execute('''
            INSERT INTO stock_progress (code, name, market, last_update_date, update_count, error_count)
            VALUES (?, ?, ?, ?, 1, 0)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                last_update_date = excluded.last_update_date,
                update_count = update_count + 1,
                error_count = 0
        ''', (code, name, market, last_date))
    else:
        cursor.execute('''
            INSERT INTO stock_progress (code, name, market, last_update_date, update_count, error_count)
            VALUES (?, ?, ?, ?, 0, 1)
            ON CONFLICT(code) DO UPDATE SET
                error_count = error_count + 1
        ''', (code, name, market, last_date))
    
    conn.commit()
    conn.close()


def sync_all_stocks():
    """
    主同步函数：遍历三大交易所所有股票
    """
    logger.info("=" * 60)
    logger.info("开始A股全量历史数据同步（按交易所分别获取列表）")
    logger.info("=" * 60)

    # 初始化数据库
    init_database(DB_PATH)
    
    # 按市场获取股票列表
    stocks_by_market = get_stock_list_by_market()
    
    # 汇总各市场所有股票（用于进度显示）
    all_stocks = []
    for market, df in stocks_by_market.items():
        if df is not None and not df.empty:
            # 注意：列名可能因接口而异，这里做适配处理
            if '证券代码' in df.columns:
                codes = df['证券代码'].astype(str).str.zfill(6)
                names = df['证券简称'] if '证券简称' in df.columns else df.get('名称', '')
            elif 'A股代码' in df.columns:
                codes = df['A股代码'].astype(str).str.zfill(6)
                names = df['A股简称'] if 'A股简称' in df.columns else df.get('名称', '')
            else:
                # 默认取第一列为代码，第二列为名称
                codes = df.iloc[:, 0].astype(str).str.zfill(6)
                names = df.iloc[:, 1] if df.shape[1] > 1 else ''
            
            for code, name in zip(codes, names):
                all_stocks.append({
                    'code': code,
                    'name': name if pd.notna(name) else code,
                    'market': market
                })
    
    total_stocks = len(all_stocks)
    logger.info(f"总计待同步股票: {total_stocks} 只")

    # 获取已有进度
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, last_update_date FROM stock_progress")
    progress_dict = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    # 确定截至日期
    today = datetime.now()
    if today.weekday() == 5:
        today = today - timedelta(days=1)
    elif today.weekday() == 6:
        today = today - timedelta(days=2)
    else:
        today = today    
    today = today.strftime("%Y-%m-%d")

    # 处理所有市场股票
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for stock in tqdm(all_stocks, desc="同步股票"):
        code = stock['code']
        name = stock['name']
        market = stock['market']
        
        # 检查是否已同步到今天
        if code in progress_dict and progress_dict[code] >= today:
            skip_count += 1
            continue

        # 下载数据        
        market_code = f"{market}{code}"
        last_update_date = progress_dict.get(code)        
        df = download_stock_data(market_code, last_update_date)
        
        if df is not None and not df.empty:
            inserted = save_to_database(df, code, name, market)
            latest_date = df["date"].max()
            update_progress(code, name, market, latest_date, True)
            success_count += 1
            
            if VERBOSE and inserted > 0:
                logger.info(f"{market} {code} ({name}) 同步成功，新增 {inserted} 条，最新 {latest_date}")
        else:
            update_progress(code, name, market, "", False)
            fail_count += 1
            logger.warning(f"{market} {code} ({name}) 同步失败")
        
        # AK接口调用时延
        #time.sleep(REQUEST_INTERVAL)
    
    # 输出统计
    logger.info("=" * 60)
    logger.info("同步完成！")
    logger.info(f"总股票数: {total_stocks}")
    logger.info(f"成功同步: {success_count}")
    logger.info(f"跳过（已最新）: {skip_count}")
    logger.info(f"失败: {fail_count}")
    logger.info("=" * 60)

    # 输出数据库统计信息
    show_statistics()


def show_statistics():
    """显示数据库统计信息"""
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_daily")
    total_records = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT code) FROM stock_daily")
    stock_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT market, COUNT(DISTINCT code) FROM stock_daily GROUP BY market")
    market_stats = cursor.fetchall()
    
    cursor.execute("SELECT MIN(date), MAX(date) FROM stock_daily")
    min_date, max_date = cursor.fetchone()
    
    conn.close()
    
    logger.info(f"数据库统计:")
    logger.info(f"  - 总记录数: {total_records:,}")
    logger.info(f"  - 股票数: {stock_count}")
    
    for market, cnt in market_stats:
        logger.info(f"    · {market}: {cnt} 只")
    
    logger.info(f"  - 日期范围: {min_date} ~ {max_date}")


if __name__ == "__main__":
    sync_all_stocks()