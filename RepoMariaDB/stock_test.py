import logging
import stock_config
from stock_manager import DBConfig, StockManager
from stock_data_manager import StockDataManager

# CMD界面
def cmdui(logger, db_manager, db_data_manager):

    def display_menu(markets):
        """显示菜单"""
        print("\n" + "=" * 60)
        print("               股票市场分析系统 v1.0")
        print("=" * 60)
        print("请选择想要分析的股票市场：")
        print()
        for key, market in markets.items():
            print(f"  {key}. {market['name']}")
            #print(f"     {market['description']}")
        print()
        print("  Q. 退出程序")
        print("=" * 60)
    
    def get_user_choice(markets):
        """获取用户选择"""
        while True:
            choice = input("\n请输入您的选择 (1-5 或 Q退出): ").strip().upper()   
            #print(f"choice={choice},type(choice) is {type(choice)}")         
            
            if choice == 'Q':
                return None
            elif choice in markets:
                return choice
            else:
                print("❌ 输入无效，请输入 1-5 或 Q")
    
    def process_choice(markets, choice):
        
        # 处理用户选择,打印配置文件中的市场信息
        market = markets[choice]
        print(f"market={market}")
        
        # 询问是否继续
        while True:
            continue_choice = input("\n是否继续选择其他市场? (Y/N): ").strip().upper()
            if continue_choice in ['Y', 'N']:
                return continue_choice == 'Y'
            else:
                print("❌ 请输入 Y 或 N")

    # 主程序循环
    markets = stock_config.STOCK_MARKETS
    print("🚀 启动股票市场分析系统...")
    
    while True:
        try:
            display_menu(markets)
            choice = get_user_choice(markets)
            
            if choice is None:
                print("\n👋 感谢使用，再见！")
                break
            
            should_continue = process_choice(markets, choice)
            
            if not should_continue:
                print("\n👋 感谢使用，再见！")
                break
                
        except KeyboardInterrupt:
            print("\n\n⚠️  检测到中断信号，程序退出")
            break
        except Exception as e:
            print(f"\n❌ 程序出错: {e}")
            retry = input("是否重新尝试? (Y/N): ").strip().upper()
            if retry != 'Y':
                break

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
    # 启动命令行界面主程序
    cmdui(logger, db_manager, db_data_manager)

if __name__ == "__main__":
    main()