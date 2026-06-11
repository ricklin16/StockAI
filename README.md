## 项目文件说明
stock_config:股票市场及股票策略定义  
stock_manager:创建数据库和表  
stock_data_manager:获取股票列表及日交易数据  
app.py:GUI主程序，基于已经入库的股票数据，支持多种策略  
app_cmd:CMD主程序，基于已经入库的股票数据，仅支持唯一策略（MA及方差）  
stock_test.py:辅助程序，用于查看配置文件信息以及测试使用  
stock_updater:辅助程序，用于股票及数据更新  
stock_manager:辅助程序，用于数据库管理  

RepoSQLite\stock_data_fetcher.py:基于AKShare和TUShare读取中国股票市场daily数据，并保存在SQLite数据库中。文件中同时包含数据库定义语句。
