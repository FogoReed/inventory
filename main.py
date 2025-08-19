import logging
from utils.logger import setup_logging
from gui.app import App
import sys

def main():
    setup_logging()
    logging.debug("Starting application")
    app = App()
    def exception_hook(exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        app.upload_to_dropbox()  # Завантаження бази при аварійному закритті
    sys.excepthook = exception_hook
    app.mainloop()

if __name__ == "__main__":
    main()