from gui.video_editor_gui import VideoEditorGUI
import tkinter as tk

def main():
    root = tk.Tk()
    app = VideoEditorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
