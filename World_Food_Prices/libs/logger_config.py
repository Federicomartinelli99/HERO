import logging
import sys
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    """Configura un logger professionale con output sia a schermo che su file."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Stream handler (console per Jupyter)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        
        # File handler (salvataggio storico delle run della pipeline)
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        fh = logging.FileHandler(log_dir / "pipeline_execution.log")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
