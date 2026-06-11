import logging
import stock_config
from stock_manager import DBConfig, StockManager
from stock_data_manager import StockDataManager

def main():

    # 日志配置
    stock_config.setup_logging()
    logger = logging.getLogger(__name__)
    # 数据库配置
    db_config = DBConfig()
    # 数据库和表管理
    db_manager = StockManager(db_config)  
    # 日交易数据管理
    db_data_manager = StockDataManager(db_manager)    
    
    # 获取短期推荐股票 
    markets = stock_config.STOCK_MARKETS
    choice = '2'
    market = markets[choice]
    start_date = '2025-07-01'
    end_date = '2025-11-30'
    plot = True

    db_data_manager.rapid_stock_selector(market, start_date, end_date, plot)

if __name__ == "__main__":
    main()