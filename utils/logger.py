import logging
import os

def setup_logging():
    log_file = 'inventory.log'
    if os.path.exists(log_file):
        os.remove(log_file)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )