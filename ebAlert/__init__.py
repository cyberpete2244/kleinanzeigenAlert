import logging
from ebAlert.core.configs import configs

logging.basicConfig(level=configs.LOGGING)


def create_logger(name):
    logger = logging.getLogger(name)
    # Create handlers
    c_handler = logging.StreamHandler()
    c_handler.setLevel(configs.LOGGING)

    # Create formatters and add it to handlers
    c_format = logging.Formatter('%(asctime)s - %(funcName)s in %(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)

    return logger
