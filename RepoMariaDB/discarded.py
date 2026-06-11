import tushare as ts
import baostock as bs
import akshare as ak
import pandas as pd 
import mplfinance as mpf
import xlrd, time, sys, logging, os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)




# TUSHARE接口令牌设置
token = '8b001669116f59aed7f94ef845ec0a9be810ac310df5b7e2f4147b93'
ts.set_token(token)



# 股票市场定义
markets = config.STOCK_MARKETS

df_SSE_Main = pd.DataFrame()
df_SSE_STAR = pd.DataFrame()
df_SZSE_Main = pd.DataFrame()
df_SZSE_ChiNext = pd.DataFrame()
df_BSE = pd.DataFrame()

# 北交所股票列表
tsstocklist = list()
bse_recommend_stocks = dict()

# 从文件中获取北交所股票列表
def BSEGetStockListFromFile():

    global tsstocklist
    tsstocklist.clear()
    stocklist = list()

    filename = '标的股票信息.xls'
    workbook = xlrd.open_workbook(filename)

    # 通过索引获取第一个工作表
    sheet = workbook.sheet_by_index(0)

    # 读取单元格数据(测试)
    cell_value = sheet.cell_value(0, 0)  # 读取第一行第一列的数据
    #print(cell_value)

    # 遍历行和列
    bse_nums = 0
    for row_index in range(sheet.nrows):
        if row_index == 0 or row_index == sheet.nrows - 1:
            continue
        cell_value = sheet.cell_value(row_index,0)
        cell_value = cell_value.replace(" ", "")
        stocklist.append(f"{cell_value}.BJ")
        bse_nums = bse_nums + 1

    tsstocklist = stocklist.copy()
    print(f"\n北交所可分析股票数量为{len(tsstocklist)}个\n")

# 从TUSHARE接口获取某只股票日两个月内的日交易数据
def BSEGetDatasFromTushare(stocklist):

    global bse_recommend_stocks

    current_tsstocklist = stocklist
    pro = ts.pro_api()

    # 获取日K数据
    for tsstock in current_tsstocklist:
        print("processing:" + tsstock)
        df = pro.daily(ts_code=tsstock, start_date='20211115', end_date='20251125')

        days_num = len(df)
        if(days_num <20):
            print(f"股票{tsstock}样本空间不足20个")
            continue

        #ts_code = ''
        current_price = average_price5 = average_price10 = average_price20 = 0

        df20 = df.head(20)
        index = 0
        for rows in df20.itertuples(index=False):
            #ts_code = rows.ts_code
            close_price = rows.close

            if(index == 0):
                current_price = close_price

            if(index < 5):
                average_price5 = average_price5 + close_price

            if(index < 10):
                average_price10 = average_price10 + close_price

            average_price20 = average_price20 + close_price

            index = index + 1

        current_price = round(current_price, 2)
        average_price5 = round(average_price5/5, 2)
        average_price10 = round(average_price10/10, 2)
        average_price20 = round(average_price20/20,2)
        
        condition = current_price > average_price5 and average_price5 > average_price10 and average_price10 > average_price20
        if condition:            
            bse_recommend_stocks[tsstock] = [current_price, average_price5, average_price10, average_price20]
            #print(f"股票{tsstock}为短期做多的推荐样本")

# 分析北交所股票
def BSESAnalyzeStocks(market):

    BSEGetStockListFromFile()

    global tsstocklist, bse_recommend_stocks
    bse_recommend_stocks.clear()

    for i in range(6):
        current_tsstocklist = tsstocklist[50*i:50*(i+1)]
        BSEGetDatasFromTushare(current_tsstocklist)         
        time.sleep(60)

    print("\n以下股票为短期做多的推荐样本\n")
    print("股票代码\t参考价格")
    for symbol, price in bse_recommend_stocks.items():
        print(f"{symbol}\t{price}")

# 上交所、深交所
bsstocklist = list()
recommend_stocks = dict()

# 从Baostock接口获取上交所、深交所股票列表
def HSEGetDatasFromBaostock(market):

    today = date.today()
    specified_trade_date = today.strftime("%Y%m%d")

    global tsstocklist
    tsstocklist.clear()

    pro = ts.pro_api()
    df = pro.daily(trade_date=specified_trade_date)

    sums = sh_nums = sz_nums = bse_nums = 0
    for rows in df.itertuples(index=True):
        tsstocklist.append(rows[1].replace(" ", ""))
        
        if '.SH' in rows[1]:
            sh_nums +=1
        elif '.SZ' in rows[1]:
            sz_nums += 1
        elif '.BJ' in rows[1]:
            bse_nums += 1

        sums += 1

    print(f"通过TUSHARE接口查询到的上交所、深交所、北交所股票数以及总数量分别为{sh_nums}:{sz_nums}:{bse_nums}:{sums}")

# 分析上交所、深交所股票    
def HSESAnalyzeStocksByBaostock(market):

    global bsstocklist, recommend_stocks
    bsstocklist.clear()
    recommend_stocks.clear()
    sh_nums = sz_nums = nums = 0

    try:

        #
        lg = bs.login()

        # 获取证券基本资料
        rs = bs.query_stock_basic()
        
        # 转换为DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())        
        df = pd.DataFrame(data_list, columns=rs.fields)

        stock_mark = f"{market['exchage']}.{market['code_prefix']}"
        print(stock_mark)

        for rows in df.itertuples(index=False):
            stock_code = rows[0].replace(" ", "")
            if stock_code.startswith(stock_mark):
                bsstocklist.append(stock_code)
            else:
                continue

        print(f"通过BaoStock接口查询到的待分析股票数量为{len(bsstocklist)}个")

        today = date.today()
        two_months_ago  = today - relativedelta(months=2)
        today = today.strftime("%Y-%m-%d")
        two_months_ago = two_months_ago.strftime("%Y-%m-%d")

        for stock in bsstocklist:
            print("processing:" + stock)
            rs = bs.query_history_k_data_plus(stock,"date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                start_date=two_months_ago, end_date=today, frequency="d", adjustflag="3")
            #
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            #
            df = pd.DataFrame(data_list, columns=rs.fields)
            days_num = len(df)
            if(days_num <20):
                print(f"股票{stock}样本空间不足20个")
                continue
            df20 = df.tail(20)
            df20 = df20[::-1]

            #
            current_price = average_price5 = average_price10 = average_price20 = 0.0
            index = 0
            for rows in df20.itertuples(index=False):

                close_price = float(rows.close)
                if(index == 0):
                    current_price = close_price
                if(index < 5):
                    average_price5 = average_price5 + close_price
                if(index < 10):
                    average_price10 = average_price10 + close_price
                average_price20 = average_price20 + close_price
                index += 1

            current_price = round(current_price, 2)
            average_price5 = round(average_price5/5, 2)
            average_price10 = round(average_price10/10, 2)
            average_price20 = round(average_price20/20,2)            
            condition = current_price > average_price5 and average_price5 > average_price10 and average_price10 > average_price20
            if(condition):
                recommend_stocks[stock] = [current_price, average_price5, average_price10, average_price20]
                #print(f"股票{stock}为短期做多的推荐样本")

        print("\n以下股票为短期做多的推荐样本\n")
        print("股票代码\t参考价格")
        for symbol, price in recommend_stocks.items():
            print(f"{symbol}\t{price}")

    finally:
        # 
        bs.logout()
