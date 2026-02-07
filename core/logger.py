import logging
import sys
import os

# Create logs directory if not exists
if not os.path.exists("logs"):
    os.makedirs("logs")

def setup_logger(name: str = "instagram_bot", log_file: str = "logs/app.log", level=logging.INFO):
    """Function to setup as many loggers as you want"""
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File Handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
    return logger

# Global logger instance
logger = setup_logger()
