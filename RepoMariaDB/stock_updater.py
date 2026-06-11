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
    

    # step1:数据库初始化 --- 创建数据库和表  
    #db_manager.init()
    # step2:数据初始化 --- 获取股票列表 
    #db_data_manager.update_stock_basic_info()  
    # step3:数据初始化 --- 获取股票历史日交易数据   
    db_data_manager.update_history_stock_daily_data()
    # stpe4:数据初始化 --- 获取异常股票历史日交易数据TUShare接口
    #db_data_manager.update_history_stock_daily_data2()

    # 数据更新 --- 获取正常股票最新日交易数据
    #db_data_manager.update_latest_stocks_daily_data()
    

if __name__ == "__main__":
    main()