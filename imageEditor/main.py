# main.py

import os
import tkinter as tk
import logging
from logger import setup_logging
from config import load_config
from gui.editor_gui import ImageEditorGUI

def main():
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        logger = setup_logging(config.get("LOG_FILE", "image_editor.log"))
        logger.info("Image Editor Started.")

        # Ensure output directory exists
        os.makedirs(config['OUTPUT_DIR'], exist_ok=True)

        # Initialize GUI
        root = tk.Tk()
        app = ImageEditorGUI(root, config, logger)
        root.mainloop()

        logger.info("Image Editor Finished.")
    except Exception as e:
        print(f"Error in main: {e}")
        return

if __name__ == "__main__":
    main()
