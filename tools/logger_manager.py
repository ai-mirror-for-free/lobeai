import os
import logging

class LoggerManager:
    """日志管理类，负责将日志记录到指定文件"""

    def __init__(self, log_file="app.log"):
        self.log_dir = "logs"
        self.log_file = os.path.join("logs", log_file)
        self._ensure_log_dir()
        self.logger = self._setup_logger()

    def _ensure_log_dir(self):
        """确保日志文件夹存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def _setup_logger(self):
        """配置 logging 模块"""
        logger = logging.getLogger("AppLogger")
        logger.setLevel(logging.INFO)

        # 防止多次添加处理器导致日志重复
        if not logger.handlers:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # 同时在控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def info(self, message):
        self.logger.info(message)

    def error(self, message):
        self.logger.error(message)

    def warning(self, message):
        self.logger.warning(message)
