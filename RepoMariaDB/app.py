import sys, logging
import numpy as np
import akshare as ak
import pandas as pd
import mplfinance as mpf
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QComboBox, QPushButton, 
                             QDateEdit, QLabel, QMessageBox, QSplitter, QProgressBar,
                             QAction, QToolBar, QMenu, QStatusBar)
from PyQt5.QtCore import QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from stock_manager import DBConfig, StockManager
from stock_data_manager import StockDataManager
import stock_config

# 股票分析线程
class DataFetchThread(QThread):
    """数据获取线程"""
    statusbar_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, bool)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    
    def __init__(self, market_type, start_date, end_date, market_strategy):
        super().__init__()
        self.market_type = market_type
        self.start_date = start_date
        self.end_date = end_date
        self.market_strategy = market_strategy
        self.stock_list = []
        self.stock_data = []
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        try:
            #
            db_config = DBConfig()
            db_manager = StockManager(db_config)
            db_data_manager = StockDataManager(db_manager) 

            # 获取股票列表
            self.statusbar_signal.emit(f"股票分析开始...") 

            markets = stock_config.STOCK_MARKETS
            choice = ''

            if self.market_type == "全部股票":
                choice = 'a'
            elif self.market_type == "上证主板":
                choice = '3'
            elif self.market_type == "上证科创板":
                choice = '4'
            elif self.market_type == "深证主板":
                choice = '1'
            elif self.market_type == "深证创业板":
                choice = '2'
            elif self.market_type == "北证":
                choice = '5'
            else:
                return 

            self.statusbar_signal.emit(f"正在获取所选市场股票列表...")
            if choice == 'a':                
                stock_list = db_data_manager.stocklist_query()
            else:
                market = markets[choice]
                stock_list = db_data_manager.stocklist_query(market)

            if stock_list.empty:
                return
            #self.logger.info(f"获取{len(stock_list)}只股票列表")    
            #self.statusbar_signal.emit(f"获取{len(stock_list)}只股票列表")
            self.progress_signal.emit(len(stock_list), True)  

            # 获取股票日交易数据
            self.statusbar_signal.emit(f"正在获取股票日交易数据...") 
            start_date = self.start_date
            end_date = self.end_date
            #stock_daily_all = db_data_manager.stockdaily_query_all(stock_list, start_date, end_date)
            
            # 逐一读取，获取进度信息
            i = 0 
            total = len(stock_list)
            stock_daily_all = []
            for stock in stock_list.itertuples():
                stock_code = stock.stock_code
                stock_name = stock.stock_name
                stock_data = db_data_manager.stockdaily_query_one(stock_code, start_date, end_date)

                if stock_data.empty:                    
                    self.logger.info(f"{stock_code}的日交易数据为空，忽略处理")
                    continue

                stock_daily_all.append({
                    'code': stock_code,
                    'name': stock_name,
                    'data': stock_data
                })
                i += 1
                self.progress_signal.emit(i, False)
             
            if not stock_daily_all:
                return
            #self.logger.info(f"获取{len(stock_daily_all)}只股票日交易数据")
            #self.statusbar_signal.emit(f"获取{len(stock_daily_all)}只股票日交易数据")

            # 获取值得推荐的股票
            recommended_stocks = []
            self.statusbar_signal.emit(f"正在进行策略分析...")

            if self.market_strategy == stock_config.STOCK_STRATEGY[0]:
                recommended_stocks = db_data_manager.stockdaily_ma_analyze(stock_daily_all)
            if self.market_strategy == stock_config.STOCK_STRATEGY[1]:
                recommended_stocks = db_data_manager.stockdaily_gain_analyze(stock_daily_all)
            if self.market_strategy == stock_config.STOCK_STRATEGY[2]:
                recommended_stocks = db_data_manager.stockdaily_turnover_analyze(stock_daily_all)
            if self.market_strategy == stock_config.STOCK_STRATEGY[3]:
                recommended_stocks = db_data_manager.stockdaily_gainmax_analyze(stock_daily_all)

            if not recommended_stocks:
                return

            # 处理完成            
            sorted_recommended_stocks = sorted(recommended_stocks, key=lambda x: x['sort_factor'], reverse=True)
            self.stock_data = sorted_recommended_stocks[:10]
            self.finished_signal.emit(self.stock_data) 
            self.statusbar_signal.emit("分析推荐完成")

        except Exception as e:
            self.error_signal.emit(str(e))

class StockAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.stock_data = []
        self.current_stock = None
        self.current_progress_bar_max = 100
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("玄甲股票分析系统 v1.0")
        self.setGeometry(100, 100, 1400, 800)
        
        # 创建菜单栏
        self.create_menubar()
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建状态栏
        self.statusBar().showMessage("就绪")
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter()
        
        # 左侧控制面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # 股票列表
        self.stock_list = QListWidget()
        self.stock_list.itemSelectionChanged.connect(self.on_stock_selected)
        
        # 添加到左侧布局
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(QLabel("推荐股票列表:"))
        left_layout.addWidget(self.stock_list)
        
        # 右侧图表区域
        self.chart_widget = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_widget)
        
        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(self.chart_widget)
        splitter.setSizes([400, 1000])
        
        main_layout.addWidget(splitter)
    
    def create_menubar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        
        new_action = QAction('新建(&N)', self)
        new_action.setShortcut('Ctrl+N')
        new_action.setStatusTip('新建分析')
        new_action.triggered.connect(self.new_analysis)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出(&X)', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('退出程序')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 数据菜单
        data_menu = menubar.addMenu('数据(&D)')
        
        refresh_action = QAction('刷新数据(&R)', self)
        refresh_action.setShortcut('F5')
        refresh_action.setStatusTip('刷新股票数据')
        refresh_action.triggered.connect(self.fetch_stock_data)
        data_menu.addAction(refresh_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图(&V)')
        
        toggle_toolbar_action = QAction('显示/隐藏工具栏', self)
        toggle_toolbar_action.setStatusTip('切换工具栏显示')
        toggle_toolbar_action.triggered.connect(self.toggle_toolbar)
        view_menu.addAction(toggle_toolbar_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')
        
        about_action = QAction('关于(&A)', self)
        about_action.setStatusTip('关于本程序')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar('主工具栏')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 市场类型选择
        toolbar.addWidget(QLabel(" 市场类型: "))
        self.market_combo = QComboBox()
        self.market_combo.addItems(["全部股票", "上证主板", "上证科创板", "深证主板", "深证创业板", "北证"])
        self.market_combo.setMinimumWidth(120)
        toolbar.addWidget(self.market_combo)
        
        toolbar.addSeparator()
        
        # 日期选择
        toolbar.addWidget(QLabel(" 开始日期: "))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addMonths(-6))
        self.start_date.setDate(QDate(2025, 12, 31))
        self.start_date.setCalendarPopup(True)
        self.start_date.setMaximumWidth(120)
        toolbar.addWidget(self.start_date)
        
        toolbar.addWidget(QLabel(" 结束日期: "))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setMaximumWidth(120)
        toolbar.addWidget(self.end_date)
        
        toolbar.addSeparator()

        # 策略选择
        toolbar.addWidget(QLabel(" 选股策略: "))
        self.market_strategy = QComboBox()
        self.market_strategy.addItems(stock_config.STOCK_STRATEGY)
        self.market_strategy.setMinimumWidth(120)
        toolbar.addWidget(self.market_strategy)
        
        toolbar.addSeparator()
        
        # 开始按钮
        self.fetch_btn = QPushButton("分析")
        self.fetch_btn.clicked.connect(self.fetch_stock_data)
        toolbar.addWidget(self.fetch_btn)
        
        toolbar.addSeparator()
        
        # 清空按钮
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self.clear_stock_list)
        toolbar.addWidget(clear_btn)
    
    def new_analysis(self):
        """新建分析"""
        self.clear_stock_list()
        self.statusBar().showMessage("新建分析完成")
    
    def toggle_toolbar(self):
        """切换工具栏显示"""
        toolbar = self.findChild(QToolBar)
        if toolbar:
            toolbar.setVisible(not toolbar.isVisible())
    
    def show_about(self):
        """显示关于信息"""
        QMessageBox.about(self, "关于", 
                         "股票分析软件\n\n"
                         "版本: 1.0\n"
                         "功能: 支持通过akshare获取股票数据\n"
                         "并使用mplfinance展示K线图和均线图")
    
    def clear_stock_list(self):
        """清空股票列表"""
        self.stock_list.clear()
        self.stock_data = []
        self.current_stock = None
        # 清除图表
        for i in reversed(range(self.chart_layout.count())): 
            widget = self.chart_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.statusBar().showMessage("已清空股票列表")
    
    # 点击"分析"按钮动作
    def fetch_stock_data(self):
        """分析股票数据"""
        market_type = self.market_combo.currentText()
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        market_strategy = self.market_strategy.currentText()
        
        if start_date > end_date:
            QMessageBox.warning(self, "警告", "开始日期不能晚于结束日期")
            return
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.fetch_btn.setEnabled(False)
        self.statusBar().showMessage("正在分析股票数据...")
        
        # 创建并启动数据获取线程
        self.fetch_thread = DataFetchThread(market_type, start_date, end_date, market_strategy)
        self.fetch_thread.statusbar_signal.connect(self.update_statusbar)
        self.fetch_thread.progress_signal.connect(self.update_progress)
        self.fetch_thread.finished_signal.connect(self.on_data_fetched)
        self.fetch_thread.error_signal.connect(self.on_data_error)
        self.fetch_thread.start()
    
    def update_statusbar(self, info):
        '''更新状态栏'''
        self.statusBar().showMessage(f"{info}")

    def update_progress(self, value, reset):
        """更新进度条"""
        if reset:
            self.current_progress_bar_max = value
            self.progress_bar.setMaximum(value)
        else:
            self.progress_bar.setValue(value)
            self.statusBar().showMessage(f"正在获取数据... {value}/{self.current_progress_bar_max}")
    
    def on_data_fetched(self, stock_data):
        """数据获取完成"""
        self.stock_data = stock_data
        self.progress_bar.setVisible(False)
        self.fetch_btn.setEnabled(True)
        
        # 更新股票列表
        self.stock_list.clear()
        for stock in stock_data:
            item_text = f"{stock['code']} - {stock['name']} - {stock['sort_factor']}"
            self.stock_list.addItem(item_text)
        
        self.statusBar().showMessage(f"成功获取 {len(stock_data)} 只股票数据")
        #QMessageBox.information(self, "完成", f"成功获取 {len(stock_data)} 只股票数据")
    
    def on_data_error(self, error_msg):
        """数据获取错误"""
        self.progress_bar.setVisible(False)
        self.fetch_btn.setEnabled(True)
        #self.statusBar().showMessage("数据获取失败")
        print(f"{error_msg}")
        QMessageBox.critical(self, "错误", f"获取数据失败: {error_msg}")
    
    def on_stock_selected(self):
        """股票选择事件"""
        current_row = self.stock_list.currentRow()
        if current_row >= 0 and current_row < len(self.stock_data):
            self.current_stock = self.stock_data[current_row]
            self.plot_stock_chart()
    
    def plot_stock_chart(self):
        """绘制股票图表"""
        if not self.current_stock:
            return
        
        # 清除现有图表
        for i in reversed(range(self.chart_layout.count())): 
            widget = self.chart_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        try:
            stock_df = self.current_stock['data']
            stock_name = self.current_stock['name']
            stock_code = self.current_stock['code']

            # 设置中文字体（简化版）
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'STHeiti']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 创建图形
            fig = Figure(figsize=(12, 8))
            canvas = FigureCanvasQTAgg(fig)
            
            # 创建子图
            ax1 = fig.add_subplot(2, 1, 1)
            ax2 = fig.add_subplot(2, 1, 2)
            
            # 设置mplfinance样式
            style = mpf.make_mpf_style(
                base_mpf_style='yahoo',
                rc={'font.family': 'SimHei'}
            )
            
            # 绘制K线图
            mpf.plot(stock_df,
                    type='candle',
                    mav=(5, 10, 20),
                    volume=ax2,
                    ax=ax1,
                    style=style,
                    returnfig=False)
            
            # 设置标题
            ax1.set_title(f'{stock_name}({stock_code}) K线图', 
                         fontsize=14, 
                         fontweight='bold')

            # 添加到布局
            self.chart_layout.addWidget(canvas)           
            self.statusBar().showMessage(f"已显示 {stock_name} 的K线图")
            
        except Exception as e:
            self.statusBar().showMessage("图表绘制失败")
            QMessageBox.warning(self, "图表错误", f"绘制图表失败: {e}")

    def plot_stock_chart_test(self):
        """绘制股票图表"""
        if not self.current_stock:
            return
        
        # 清除现有图表
        for i in reversed(range(self.chart_layout.count())): 
            widget = self.chart_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        try:
            stock_df = self.current_stock['data']
            stock_name = self.current_stock['name']
            stock_code = self.current_stock['code']

            # 设置中文字体（简化版）
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'STHeiti']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 创建图形
            fig = Figure(figsize=(12, 8))
            canvas = FigureCanvasQTAgg(fig)
            
            # 创建子图
            ax1 = fig.add_subplot(2, 1, 1)
            ax2 = fig.add_subplot(2, 1, 2)

            # 2. 创建两个子图
            ax1 = fig.add_subplot(2, 1, 1)  # 上方子图
            ax2 = fig.add_subplot(2, 1, 2)  # 下方子图
            
            # 3. 在上方子图绘制曲线
            x = np.linspace(0, 10, 100)
            y1 = np.sin(x)
            ax1.plot(x, y1, 'r-', linewidth=2)
            ax1.set_title('正弦波')
            ax1.grid(True)
            
            # 4. 在下方子图绘制柱状图
            categories = ['A', 'B', 'C', 'D']
            values = [15, 23, 18, 32]
            ax2.bar(categories, values, color='skyblue')
            ax2.set_title('柱状图示例')
            ax2.set_xlabel('类别')
            ax2.set_ylabel('数值')
            
            # 5. 调整子图间距
            fig.tight_layout()
            
            # 6. 将 Canvas 添加到窗口
            self.chart_layout.addWidget(canvas)
            
        except Exception as e:
            self.statusBar().showMessage("图表绘制失败")
            QMessageBox.warning(self, "图表错误", f"绘制图表失败: {e}")

def main():
    app = QApplication(sys.argv)
    
    # 设置字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    window = StockAnalyzer()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()