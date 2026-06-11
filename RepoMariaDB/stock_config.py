import logging
from enum import Enum, StrEnum

class StockStrategy(StrEnum):
    SEL_MA = "MA均线多头排列"
    SEL_MAX = "涨幅最大的十只股票"
    SEL_MIN = "跌幅最大的十只股票"
    SEL_TURNOVER = "换手率最高的十只股票"


STOCK_STRATEGY =  ["MA均线多头排列", "涨幅最大的十只股票", "换手率最高的十只股票", "涨停最多的十只股票"]

#历史股票更新截止时间
HISTORY_UPDATE_DATE = '20251231' 

#当前股票更新时间，必须为有效的交易日
CURRENT_UPDATE_DATE = '2026-01-13'  

# 股票市场定义 --- 按股票code从小到大
STOCK_MARKETS = {
    '1': {
        'name': '深证主板',
        'symbol': 'A股列表',
        'market': 'SZSE',
        'exchange': 'sz',
        'code_prefix': '00', 
        'gain_percent': 0.1,
        'description': '深圳证券交易所主板市场',
        'start_code': '000001',
        'end_code': '003816',
        'update_date': CURRENT_UPDATE_DATE, 
        'operations_date': '1991-07-03'
    },
    '2': {
        'name': '深证创业板',
        'symbol': 'A股列表',
        'market': 'SZSE',
        'exchange': 'sz',
        'code_prefix': '30',
        'gain_percent': 0.2,
        'description': '深圳证券交易所创业板',
        'start_code': '300001',
        'end_code': '302132',
        'update_date': CURRENT_UPDATE_DATE, 
        'operations_date': '2009-10-30'
    },
    '3': {
        'name': '上证主板', 
        'symbol': '主板A股',   #用于AKShare接口
        'market': 'SSE',
        'exchange': 'sh',
        'code_prefix': '60',
        'gain_percent': 0.1,
        'description': '上海证券交易所主板市场',
        'start_code': '600000',
        'end_code': '605599',
        'update_date': CURRENT_UPDATE_DATE, 
        'operations_date': '1990-12-19'
    },
    '4': {
        'name': '上证科创板',
        'symbol': '科创板',
        'market': 'SSE',
        'exchange': 'sh',
        'code_prefix': '68',
        'gain_percent': 0.2,
        'description': '上海证券交易所科创板',
        'start_code': '688001',
        'end_code': '688981',
        'update_date': CURRENT_UPDATE_DATE, 
        'operations_date': '2019-07-22'
    },
    '5': {
        'name': '北证',
        'symbol': '',
        'market': 'BSE',
        'exchange': 'bj',
        'code_prefix': '920',
        'gain_percent': 0.3,
        'description': '北京证券交易所',
        'start_code': '920000',
        'end_code': '920992',
        'update_date': CURRENT_UPDATE_DATE, 
        'operations_date': '2021-11-25'
    }
}

# 选股策略

# 配置日志
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )