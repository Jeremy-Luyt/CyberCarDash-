import logging
import os
import time

def setup_logger(name="CyberCarDash"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 控制台处理程序
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # 文件处理程序
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    fh = logging.FileHandler(f"logs/session_{int(time.time())}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger
