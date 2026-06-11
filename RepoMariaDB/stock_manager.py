
# stock_manager.py

import logging
import pymysql
from pymysql import Error
from datetime import datetime

# 数据库配置
class DBConfig():
    def __init__(self):
        self.host = 'localhost'
        self.port = 3306
        self.user = 'root'
        self.password = 'tjj31415'
        self.database = 'stock_data'

# 数据库管理类
class StockManager():
    
    def __init__(self, db_config):
        self.host = db_config.host
        self.port = db_config.port
        self.user = db_config.user
        self.password = db_config.password
        self.database = db_config.database
        self.connection = None
        self.logger = logging.getLogger(__name__)

    def init(self):

        # 1. 检查数据库是否存在
        if self.database_exists():

            #
            choice = input("\n确定要删除吗 (y/n)? ").strip().lower()
            if choice != 'y':
                return
            # 删除数据库
            if not self.drop_database():
                return
            
        # 2. 创建数据库
        if not self.create_database():
            return

        # 3. 创建数据表
        if not self.create_table():
            return

        # 4. 完成初始化
        self.logger.info(f"数据库 '{self.database}' 初始化完成")

    def connect(self, use_database=False):
        """连接到数据库服务器"""
        try:
            connection_params = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'charset': 'utf8mb4'
            }
            
            if use_database and self.database:
                connection_params['database'] = self.database
            
            self.connection = pymysql.connect(**connection_params)
            #self.logger.info("数据库连接成功")
            return True
            
        except Error as e:
            self.logger.error(f"数据库连接失败: {e}")
            return False
    
    def create_database(self, charset='utf8mb4', collate='utf8mb4_unicode_ci'):
        try:
            if not self.connect(use_database=False):
                return False

            database_name = self.database

            with self.connection.cursor() as cursor:
                # 创建数据库
                sql = f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET {charset} COLLATE {collate}"
                cursor.execute(sql)
                
                # 更新实例的数据库名称
                self.database = database_name                
                self.logger.info(f"数据库 '{database_name}' 创建成功")

                # 切换到新建数据库
                #cursor.execute(f"USE {database_name}")

                return True
                
        except Error as e:
            self.logger.error(f"创建数据库失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
    
    def create_table(self, charset='utf8mb4', collate='utf8mb4_unicode_ci'):
        try:
            if not self.connect(use_database=True):
                return False
            
            with self.connection.cursor() as cursor:

                # 创建股票基本信息表
                table_name = 'stock_basic'
                sql = """
                CREATE TABLE IF NOT EXISTS stock_basic (
                    id INT AUTO_INCREMENT PRIMARY KEY,                    
                    stock_code VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(100) NOT NULL,
                    listing_date DATE,
                    #industry VARCHAR(100),
                    market_type VARCHAR(20) NOT NULL,  
                    exchange VARCHAR(10) NOT NULL,                  
                    code_prefix VARCHAR(10) NOT NULL,                    
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_stock (stock_code, exchange)
                )
                """
                cursor.execute(sql)
                self.logger.info(f"数据表 '{table_name}' 创建成功")
                
                # 创建股票日交易数据表
                table_name = 'stock_daily'
                sql = """
                CREATE TABLE IF NOT EXISTS stock_daily (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    stock_code VARCHAR(10) NOT NULL,
                    trade_date DATE NOT NULL,
                    open_price DECIMAL(10, 3),
                    high_price DECIMAL(10, 3),
                    low_price DECIMAL(10, 3),
                    close_price DECIMAL(10, 3),
                    previous_close_price DECIMAL(10, 3),
                    volume BIGINT,              # 成交量
                    previous_volume BIGINT,     # 前一日成交量
                    amount DECIMAL(10, 3),      # 成交额
                    outstanding_share BIGINT,   # 流动股本
                    amplitude DECIMAL(8, 4),    # 振幅
                    change_rate DECIMAL(8, 4),  # 涨跌幅
                    change_amount DECIMAL(8, 4),    # 涨跌额
                    turnover_rate DECIMAL(8, 4),    # 换手率
                    turnover DECIMAL(15, 2),    # 换手数                    
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_stock_code (stock_code),
                    INDEX idx_trade_date (trade_date),
                    INDEX idx_stock_date (stock_code, trade_date),
                    UNIQUE KEY unique_daily_record (stock_code, trade_date)
                )
                """
                cursor.execute(sql)
                self.logger.info(f"数据表 '{table_name}' 创建成功")

                return True
                
        except Error as e:
            self.logger.error(f"创建数据库失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
    
    def database_exists(self):
        """
        检查数据库是否存在
        """
        database_name = self.database
        try:
            if not self.connect(use_database=False):
                return False
            
            with self.connection.cursor() as cursor:
                cursor.execute("SHOW DATABASES")
                databases = [db[0] for db in cursor.fetchall()]
                if database_name in databases:
                    self.logger.info(f"数据库 '{database_name}' 存在")
                    return True
                else:
                    self.logger.info(f"数据库 '{database_name}' 不存在")
                    return False
                
        except Error as e:
            self.logger.error(f"检查数据库存在性失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
    
    def drop_database(self):
        """
        删除数据库
        """
        database_name = self.database
        try:
            if not self.connect(use_database=False):
                return False
            
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS {database_name}")
                self.logger.info(f"数据库 '{database_name}' 删除成功")
                return True
                
        except Error as e:
            self.logger.error(f"删除数据库失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
    
    def execute_sql_file(self, sql_file_path):
        """
        执行SQL文件来创建数据库和表
        """
        try:
            if not self.connect(use_database=True):
                return False
            
            with open(sql_file_path, 'r', encoding='utf-8') as file:
                sql_script = file.read()
            
            with self.connection.cursor() as cursor:
                # 分割SQL语句并执行
                sql_commands = sql_script.split(';')
                for command in sql_commands:
                    if command.strip():
                        cursor.execute(command)
            
            self.connection.commit()
            self.logger.info(f"SQL文件 '{sql_file_path}' 执行成功")
            return True
            
        except Error as e:
            self.logger.error(f"执行SQL文件失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
