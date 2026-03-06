import logging
import os

def setup_logger(log_dir):
    os.makedirs(log_dir, exist_ok=True)

    import sys
    
    # Configure root logger to catch everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler
    file_handler = logging.FileHandler(os.path.join(log_dir, "chat_app.log"))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Stream Handler (Terminal)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # Silence noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    return root_logger
