import logging
from utils.logger import setup_logging
from gui.app import App

def main():
    setup_logging()
    logging.debug("Starting application")
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()