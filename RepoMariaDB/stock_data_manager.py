# stock_data_manager.py

import tushare as ts
import akshare as ak
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
import logging
from requests.exceptions import Timeout, RequestException
import stock_config

class StockDataManager():

    def __init__(self, db_manager):
        self.db = db_manager

        self.driver = 'pymysql'
        connection_string = f"mysql+{self.driver}://{self.db.user}:{self.db.password}@{self.db.host}:{self.db.port}/{self.db.database}"
        self.engine = create_engine(
                connection_string,
                echo=False,     # 设置为True可以查看SQL语句
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={'connect_timeout': 10}
            )

        self.df_SSE_Main = pd.DataFrame()
        self.df_SSE_STAR = pd.DataFrame()
        self.df_SZSE_Main = pd.DataFrame()
        self.df_SZSE_ChiNext = pd.DataFrame()
        self.df_BSE = pd.DataFrame()
        self.df_all_stocks = pd.DataFrame()
        self.df_all_stocks_data = pd.DataFrame()
        self.logger = logging.getLogger(__name__)
        self.abnormal_stocks = ['689009', '603352']

        # TUSHARE接口令牌设置
        self.token = '8b001669116f59aed7f94ef845ec0a9be810ac310df5b7e2f4147b93'
        ts.set_token(self.token)


    #------------------------------基础数据准备---------------------------- #

    # 通过AKShare接口获取某个市场交易板块股票基础信息
    def get_one_stock_list(self, market=None):

        try:
            if market is None:
                return pd.DataFrame()

            # 获取上交所股票 --- 主板、科创板
            if market['exchange'] == 'sh':
                df = ak.stock_info_sh_name_code(symbol=market['symbol'])      
                if df.empty:
                    return pd.DataFrame()

                # 格式化列名称
                df = df.rename(columns={
                    '证券代码': 'stock_code',
                    '证券简称': 'stock_name',
                    '上市日期': 'listing_date'
                })                
                # 格式化上市日期
                df['listing_date'] = pd.to_datetime(df['listing_date'])
                df['listing_date'] = df['listing_date'].dt.strftime('%Y-%m-%d')

                # 添加其他列数据
                df['market_type'] = market['symbol']
                df['market'] = market['market']
                df['exchange'] = market['exchange']                
                df['code_prefix'] = market['code_prefix']                
                #
                return df

            # 获取深交所股票
            if market['exchange'] == 'sz':
                stock_info_sz_df = ak.stock_info_sz_name_code(symbol=market['symbol'])
            
                # 格式化列名称
                stock_info_sz_df = stock_info_sz_df.rename(columns={
                    'A股代码': 'stock_code',
                    'A股简称': 'stock_name',
                    'A股上市日期': 'listing_date',
                    '板块': 'market_type'
                })
                # 添加其他列数据                
                stock_info_sz_df['market'] = market['market'] 
                stock_info_sz_df['exchange'] = market['exchange']   
                stock_info_sz_df['code_prefix'] = market['code_prefix']
                # 提取主板/创业板
                condition = stock_info_sz_df['stock_code'].str.startswith(market['code_prefix'])
                df_SZSE = stock_info_sz_df[condition].copy()
                #
                return df_SZSE

            # 获取北交所股票
            if market['exchange'] == 'bj':
                df_BSE = ak.stock_info_bj_name_code()
                # 格式化列名称
                df_BSE = df_BSE.rename(columns={
                    '证券代码': 'stock_code',
                    '证券简称': 'stock_name',
                    '上市日期': 'listing_date'
                })
                df_BSE['listing_date'] = pd.to_datetime(df_BSE['listing_date'])
                df_BSE['listing_date'] = df_BSE['listing_date'].dt.strftime('%Y-%m-%d')
                df_BSE['market_type'] = ''
                df_BSE['market'] = market['market'] 
                df_BSE['exchange'] = market['exchange']
                df_BSE['code_prefix'] = market['code_prefix']
                #
                return df_BSE

        except Exception as e:
            print(f"获取股票列表出错: {e}")
            return pd.DataFrame()

    # 通过AKShare接口获取所有市场板块股票基础信息
    def get_all_stock_list(self):

        try:

            # 分别获取每个市场股票列表
            markets = stock_config.STOCK_MARKETS
            choice = '1' 
            market = markets[choice]
            df_SSE_Main = self.get_one_stock_list(market)
            choice = '2' 
            market = markets[choice]
            df_SSE_STAR = self.get_one_stock_list(market)
            choice = '3' 
            market = markets[choice]
            df_SZSE_Main = self.get_one_stock_list(market)
            choice = '4' 
            market = markets[choice]
            df_SZSE_ChiNext = self.get_one_stock_list(market)
            choice = '5' 
            market = markets[choice]
            df_BSE = self.get_one_stock_list(market)

            # 纵向合并各个市场股票列表
            sorted_columns = ['stock_code', 'stock_name', 'listing_date', 'market_type', 'exchange', 'code_prefix']
            self.df_SSE_Main = df_SSE_Main[sorted_columns]
            self.df_SSE_STAR = df_SSE_STAR[sorted_columns]
            self.df_SZSE_Main = df_SZSE_Main[sorted_columns]
            self.df_SZSE_ChiNext = df_SZSE_ChiNext[sorted_columns]
            self.df_BSE = df_BSE[sorted_columns]
            self.df_all_stocks = pd.concat([self.df_SSE_Main, self.df_SSE_STAR, self.df_SZSE_Main, self.df_SZSE_ChiNext, self.df_BSE], ignore_index=True) 

            #
            return self.df_all_stocks
            
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    # 更新并存储所有股票历史基础信息
    def update_stock_basic_info(self):

        choice = input("\n确定要更新股票列表信息吗 (y/n)? ").strip().lower()
        if choice != 'y':
            return

        try:
            stock_list = self.get_all_stock_list()
            if not stock_list.empty:
                stock_list.to_sql(
                    'stock_basic', 
                    self.engine, 
                    if_exists='append', 
                    index=False,
                    method='multi'
                )
                self.logger.info("股票基本数据更新完成")
            else:
                self.logger.info("未获取到股票基本数据")
        except Exception as e:
            self.logger.info(f"更新股票基本数据失败: {e}")
    
    # 更新并存储"所有"股票数据截止到HISTORY_UPDATE_DATE的日交易数据
    def update_history_stock_daily_data(self, batch_size=50):

        try:
            end_date = stock_config.HISTORY_UPDATE_DATE
            markets = stock_config.STOCK_MARKETS

            # 遍历每一个股票市场
            for num, market in markets.items():
                #
                prompt = f"确定要获取以{market['code_prefix']}开头的股票的历史数据吗 (y/n)? "
                choice = input(prompt).strip().lower()
                if choice != 'y':
                    continue

                # 实时获取当前市场股票列表
                start_date = market['operations_date'].replace("-", "")
                stock_list = self.get_one_stock_list(market)
                if stock_list.empty:
                    print(f"未能获取到{market[exchange]}市场{market['code_prefix']}开头的股票")
                    continue

                # 遍历每只股票             
                for row in stock_list.itertuples():
                    
                    # 判断是否为异常股票
                    if row.stock_code in self.abnormal_stocks:
                        self.logger.info(f"{row.stock_code}数据缺失，暂不处理")
                        continue

                    # 用于断点续传
                    #if int(row.stock_code) < 603352:
                    #    continue

                    #
                    symbol = f"{row.exchange}{row.stock_code}".lower()                    
                    df_daily_data = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")
                    #
                    if df_daily_data.empty:
                        self.logger.info(f"通过AKShare接口获取{row.stock_code}日交易数据为空")
                        continue
                    
                    # 用于测试AK接口                    
                    print(f"获取{row.stock_code}完成,{len(df_daily_data)}")
                    continue

                    # 格式化数据    
                    df_daily_data = df_daily_data.rename(columns={
                        'date': 'trade_date',
                        'open': 'open_price',
                        'high': 'high_price',
                        'low':'low_price',
                        'close':'close_price',
                        'turnover':'turnover_rate'
                    })
                    df_daily_data['stock_code'] = row.stock_code
                    df_daily_data['previous_close_price'] = 0.0
                    df_daily_data['previous_volume'] = 0.0
                    df_daily_data = df_daily_data[['stock_code', 'trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'previous_close_price', 'volume', 'previous_volume', 'turnover_rate']]
                    df_daily_data.loc[1:, 'previous_close_price'] = df_daily_data['close_price'].shift(1).loc[1:]
                    df_daily_data.loc[1:, 'previous_volume'] = df_daily_data['volume'].shift(1).loc[1:]

                    #
                    df_daily_data.to_sql(
                        'stock_daily', 
                        self.engine, 
                        if_exists='append', 
                        index=False,
                        chunksize=5000,
                        method='multi'
                    )

                    # 更新处理进程
                    print(f"数据加载完成{row.stock_code}")
                    
            return True
                
        except Exception as e:
            self.logger.info(f"加载股票历史daily数据失败: {e}")
            return False
    
    # 更新并存储"异常"股票数据截止到HISTORY_UPDATE_DATE的日交易数据
    def update_history_stock_daily_data2(self, batch_size=50):

        try:

            start_date = '19900101'
            end_date = stock_config.HISTORY_UPDATE_DATE
            pro = ts.pro_api()
            for stock_code in self.abnormal_stocks:
                # 
                df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
                if df.empty:
                    print(f"未能获取到{stock_code}的日交易数据")
                    continue

                # 格式化数据  
                print(f"找到{stock_code}股票的{len(df)}条数据")
                continue  

                df_daily_data = df.rename(columns={
                    'date': 'trade_date',
                    'open': 'open_price',
                    'high': 'high_price',
                    'low':'low_price',
                    'close':'close_price',
                    'turnover':'turnover_rate'
                })
                df_daily_data['stock_code'] = row.stock_code
                df_daily_data['previous_close_price'] = 0.0
                df_daily_data['previous_volume'] = 0.0
                df_daily_data = df_daily_data[['stock_code', 'trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'previous_close_price', 'volume', 'previous_volume', 'turnover_rate']]
                df_daily_data.loc[1:, 'previous_close_price'] = df_daily_data['close_price'].shift(1).loc[1:]
                df_daily_data.loc[1:, 'previous_volume'] = df_daily_data['volume'].shift(1).loc[1:]

                #
                df_daily_data.to_sql(
                    'stock_daily', 
                    self.engine, 
                    if_exists='append', 
                    index=False,
                    chunksize=5000,
                    method='multi'
                )

                # 更新处理进程
                print(f"数据加载完成{row.stock_code}")
                    
            return True
                
        except Exception as e:
            self.logger.info(f"加载股票历史daily数据失败: {e}")
            return False
    
    # 更新并存储"CURRENT_UPDATE_DATE"到程序运行时的日交易数据
    def update_latest_stocks_daily_data(self, batch_size=50):
        """
        批量更新所有股票的日交易数据
        batch_size: 每批处理的股票数量
        """
        current_stock_code = ''
        end_date = datetime.now().strftime('%Y%m%d')

        try:
            
            markets = stock_config.STOCK_MARKETS
            for num, market in markets.items():

                #
                prompt = f"确定要更新以{market['code_prefix']}开头的股票数据吗 (y/n)? "
                choice = input(prompt).strip().lower()
                if choice != 'y':
                    continue

                stock_list = self.get_one_stock_list(market)
                if stock_list.empty:
                    print(f"未能获取到{market[exchange]}市场{market['code_prefix']}开头的股票")
                    continue

                start_date = market['update_date'].replace("-","")            
                for row in stock_list.itertuples():
                    # 判断是否为异常股票，比如689009
                    if row.stock_code in self.abnormal_stocks:
                        self.logger.info(f"{row.stock_code}数据缺失，暂不处理")
                        continue

                    if int(row.stock_code) > 688647:
                        continue

                    current_stock_code = row.stock_code 
                    symbol = f"{row.exchange}{row.stock_code}".lower()
                    df_daily_data = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")

                    if df_daily_data.empty:
                        self.logger.info(f"通过AKShare接口获取{row.stock_code}日交易数据为空")
                        continue
                    if len(df_daily_data) == 1:
                        continue
                    
                    # 格式化数据    
                    df_daily_data = df_daily_data.rename(columns={
                        'date': 'trade_date',
                        'open': 'open_price',
                        'high': 'high_price',
                        'low':'low_price',
                        'close':'close_price',
                        'turnover':'turnover_rate'
                    })
                    df_daily_data['stock_code'] = row.stock_code
                    df_daily_data['previous_close_price'] = 0.0
                    df_daily_data['previous_volume'] = 0.0
                    df_daily_data = df_daily_data[['stock_code', 'trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'previous_close_price', 'volume', 'previous_volume', 'turnover_rate']]
                    df_daily_data.loc[1:, 'previous_close_price'] = df_daily_data['close_price'].shift(1).loc[1:]
                    df_daily_data.loc[1:, 'previous_volume'] = df_daily_data['volume'].shift(1).loc[1:]
                    df_daily_data = df_daily_data.tail(len(df_daily_data)-1)    # 开始日期股票数据已入库

                    #
                    df_daily_data.to_sql(
                        'stock_daily', 
                        self.engine, 
                        if_exists='append', 
                        index=False,
                        chunksize=5000,
                        method='multi'
                    )
                    print(f"{current_stock_code}数据更新完成")

            #
            return True

        except Timeout as e:            
            print(f"{current_stock_code}数据更新超时: {e}")
            return False

        except RequestException as e:
            print(f"{current_stock_code}网络请求错误: {e}")
            return False

        except Exception as e:
            print(f"{current_stock_code}数据更新失败: {e}")
            return False
    
    
    #-----------------------数据分析应用:玄甲股票分析系统 v1.0------------- #
    #-------基于索数据库内股票列表和日交易数据，查找符合策略的推荐股票-----------#

    # 基于MA及方差选股
    def rapid_stock_selector(self, market=None, strategy=None, start_date=None, end_date=None, ploted = False):

        try:

            stock_list = self.stocklist_query_all(market)
            if stock_list.empty:
                return False

            stock_daily_all = self.stockdaily_query_all(stock_list, start_date, end_date)
            if not stock_daily_all:
                return False

            recommended_stocks = self.stockdaily_ma_analyze(stock_daily_all)
            if not recommended_stocks:
                return False

            if ploted:
                self.plot_kline_mplfinance(recommended_stocks)

            return True

        except Exception as e:
            print(f"股票推荐程序出错 {e}")
            return False

    # 查询stock_basic获取股票列表数据
    def stocklist_query(self, market=None):

        try:

            market_name = ''

            # 读取数据库，获取股票列表
            table_name = 'stock_basic'
            if market is None:
                market_name = '全部市场'
                query = f"SELECT * FROM {table_name}"
                params = ()
            else:
                market_name = market['name']
                query = f"SELECT * FROM {table_name} WHERE stock_code LIKE %s"
                pattern = f"{int(market['code_prefix'])}%"
                params = (pattern,)

            stock_list = pd.read_sql(query, self.engine, params=params)
            self.logger.info("股票basic数据检索完成")
            return stock_list

        except Exception as e:
            self.logger.info(f"股票basic数据检索失败: {e}")
            return pd.DataFrame()

    # 查询数据库获取某只股票日交易数据
    def stockdaily_query_one(self, stock_code, start_date, end_date):

        try:
            table_name = 'stock_daily'
            query = """
                SELECT * FROM stock_daily 
                WHERE stock_code = %s 
                AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date
            """
            params = (stock_code, start_date, end_date)
            df = pd.read_sql(query, self.engine, params=params)
            return df

        except Exception as e:
            print(f"数据库查询失败: {e}")
            return pd.DataFrame()

    # 查询stock_daily获取所有股票日交易数据
    def stockdaily_query_all(self, stock_list, start_date = None, end_date = None):

        try:

            stock_daily_all = []
            days = 90

            if start_date is None or end_date is None:
                start_date = (datetime.now() - timedelta(days)).strftime('%Y-%m-%d')
                end_date = datetime.now().strftime('%Y-%m-%d')
            else:
                date1 = datetime.strptime(start_date, "%Y-%m-%d")
                date2 = datetime.strptime(end_date, "%Y-%m-%d")
                
                # 计算时间差
                delta = date2 - date1
                # 获取天数差（绝对值）
                days = abs(delta.days)

            # 读取表数据
            table_name ='stock_daily'
            for stock in stock_list.itertuples():
                stock_code = stock.stock_code
                stock_name = stock.stock_name
                stock_data = self.stockdaily_query_one(stock_code, start_date, end_date)

                stock_daily_all.append({
                    'code': stock_code,
                    'name': stock_name,
                    'data': stock_data
                })
        
            #    
            self.logger.info(f"股票daily数据检索完成")
            return stock_daily_all

        except Exception as e:
            self.logger.info(f"股票daily数据检索失败: {e}")
            return []

    # 对股票daily数据做MA分析
    def stockdaily_ma_analyze(self, stock_list):

        try:

            recommended_stocks = []

            for stock in stock_list:

                stock_code = stock['code']
                stock_name = stock['name']
                stock_data = stock['data']

                # 样本数不足
                if len(stock_data) < 30:
                    self.logger.info(f"股票{stock_code}样本数不足 {len(stock_data)}")
                    continue
                
                # 计算移动平均线
                stock_data['MA5'] = stock_data['close_price'].rolling(window=5).mean()
                stock_data['MA10'] = stock_data['close_price'].rolling(window=10).mean()
                stock_data['MA20'] = stock_data['close_price'].rolling(window=20).mean()

                # 设置索引
                stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'])  # 先转换为 datetime 类型
                stock_data.set_index('trade_date', drop=False, inplace=True)  # 设为索引

                # 重命名列以符合函数规范
                column_mapping = {
                    'open_price': 'Open',
                    'high_price': 'High', 
                    'low_price': 'Low',
                    'close_price': 'Close',
                    'volume': 'Volume'
                }
                stock_data = stock_data.rename(columns=column_mapping)
                df = stock_data.tail(3)
                df_processed = df.assign(
                    golden_cross=(df['MA5'] > df['MA10']) & (df['MA10'] > df['MA20']),
                    death_cross=(df['MA5'] < df['MA10']) & (df['MA10'] < df['MA20']),
                    ddof1 = (stats.variation([df['MA5'], df['MA10'], df['MA20']], ddof=1))
                )
                ddof1_mean = round(df_processed['ddof1'].mean(), 4)

                if df_processed['golden_cross'].all(skipna=False) and df_processed['MA20'].notna().all():
                    recommended_stocks.append({
                        'code': stock_code,
                        'name': stock_name,
                        'data': stock_data,
                        'sort_factor': ddof1_mean
                    })  

            #
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[0]}分析完成")  
            return recommended_stocks

        except Exception as e:
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[0]}分析失败: {e}")
            return pd.DataFrame()

    # 对股票daily数据做gain分析
    def stockdaily_gain_analyze(self, stock_infos):

        try:

            recommended_stocks = []

            for stock in stock_infos:

                stock_code = stock['code']
                stock_name = stock['name']
                stock_data = stock['data']

                if stock_data.empty:
                    print(f"{stock_code}的数据为空")
                    continue


                # 设置索引
                stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'])  # 先转换为 datetime 类型
                stock_data.set_index('trade_date', drop = False, inplace=True)  # 设为索引

                # 以指定时间段的第一天和最后一天为基准计算涨跌幅
                df1 = stock_data.head(1)
                df2 = stock_data.tail(1)
 

                start_close_price = df1['close_price'].iloc[0]
                start_trade_date = df1['trade_date'].iloc[0]
                end_close_price = df2['close_price'].iloc[0]       
                end_trade_date = df2['trade_date'].iloc[0]
                gain = round(end_close_price / start_close_price, 2)

                # 以指定时间段的第一天和收盘价最高的一天为基准计算涨跌幅
                #max_close_price = stock_data['close_price'].max()
                #max_index = stock_data['close_price'].idxmax()
                #max_trade_date = df2['trade_date'].iloc[max_index]
                #gain = round(max_close_price / start_close_price, 2)

                # 重命名列以符合函数规范
                column_mapping = {
                    'open_price': 'Open',
                    'high_price': 'High', 
                    'low_price': 'Low',
                    'close_price': 'Close',
                    'volume': 'Volume'
                }
                stock_data = stock_data.rename(columns=column_mapping)

                #
                recommended_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'data': stock_data,
                    'sort_factor': gain
                })

            #
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[1]}分析完成")  
            return recommended_stocks

        except Exception as e:
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[1]}分析失败: {e}")
            return pd.DataFrame()

    # 对股票daily数据做换手率分析
    def stockdaily_turnover_analyze(self, stock_list):

        try:

            recommended_stocks = []

            for stock in stock_list:

                stock_code = stock['code']
                stock_name = stock['name']
                stock_data = stock['data']
                
                # 计算涨跌幅和换手率
                turnover_rates = stock_data['turnover_rate'].sum()

                # 设置索引
                stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'])  # 先转换为 datetime 类型
                stock_data.set_index('trade_date', inplace=True)  # 设为索引

                # 重命名列以符合函数规范
                column_mapping = {
                    'open_price': 'Open',
                    'high_price': 'High', 
                    'low_price': 'Low',
                    'close_price': 'Close',
                    'volume': 'Volume'
                }
                stock_data = stock_data.rename(columns=column_mapping)

                #
                recommended_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'data': stock_data,
                    'sort_factor': turnover_rates
                })

            #
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[2]}分析完成")  
            return recommended_stocks

        except Exception as e:
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[2]}分析失败: {e}")
            return pd.DataFrame()

    # 对股票daily数据做涨停个数分析
    def stockdaily_gainmax_analyze(self, stock_list):

        try:

            recommended_stocks = []

            for stock in stock_list:

                stock_code = stock['code']
                stock_name = stock['name']
                stock_data = stock['data']

                # 设置索引
                stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'])  # 先转换为 datetime 类型
                stock_data.set_index('trade_date', drop = False, inplace=True)  # 设为索引

                # 
                limit_percent = 0.0
                for key, value in stock_config.STOCK_MARKETS.items():
                    if stock_code.startswith(value['code_prefix']):
                        limit_percent = value['gain_percent']
                        #print(f"limit_percent: {limit_percent*100}%")
                        break

                #
                gainmax_num = 0
                for row in stock_data.itertuples():
                    if row.close_price == round(row.previous_close_price * (1 + limit_percent), 2):
                        gainmax_num += 1
                        print(f"{stock_code}:{row.trade_date}:{row.previous_close_price}:{row.close_price}:{limit_percent}")

                # 重命名列以符合函数规范
                column_mapping = {
                    'open_price': 'Open',
                    'high_price': 'High', 
                    'low_price': 'Low',
                    'close_price': 'Close',
                    'volume': 'Volume'
                }
                stock_data = stock_data.rename(columns=column_mapping)

                #
                recommended_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'data': stock_data,
                    'sort_factor': gainmax_num
                })

            #
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[1]}分析完成")  
            return recommended_stocks

        except Exception as e:
            self.logger.info(f"股票{stock_config.STOCK_STRATEGY[1]}分析失败: {e}")
            return pd.DataFrame()

    # 绘制推荐股票的K线图
    def plot_kline_mplfinance(self, recommended_stocks):

        try:
            # 绘制推荐股票的k线图
            for stock in recommended_stocks:

                stock_code = stock['code']
                stock_name = stock['name']
                stock_data = stock['data']

                # 创建额外的绘图数据
                apds = [
                    mpf.make_addplot(stock_data['MA5'], color='gray', width=1, label='MA5'),
                    mpf.make_addplot(stock_data['MA10'], color='yellow', width=1, label='MA10'),
                    mpf.make_addplot(stock_data['MA20'], color='purple', width=1, label='MA20'),
                ]

                # 绘制专业K线图
                newtitle = f"{stock_code} - K线图与移动平均线"
                newstyle = mpf.make_mpf_style(base_mpf_style='yahoo', rc={
                    'font.family': 'SimHei', 'axes.unicode_minus': 'False'})
                fig, axes = mpf.plot(stock_data, 
                    type='candle',
                    addplot=apds,
                    title=newtitle,
                    ylabel='价格 (元)',
                    volume=True,
                    style=newstyle, # 'charles'
                    figratio=(12, 8),
                    figscale=1.2,
                    datetime_format='%Y-%m-%d',
                    show_nontrading=False,
                    returnfig=True)

                # 修改窗口标题栏
                fig.canvas.manager.set_window_title('玄甲股票分析系统 v1.0')

                # 显示图表
                mpf.show()

            return True

        except Exception as e:
            print(f"股票K线图绘制失败: {e}")
            return False


