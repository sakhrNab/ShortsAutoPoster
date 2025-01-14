import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from gui.dialogs.text_overlay_settings_dialog import TextOverlaySettingsDialog

class TextOverlayDialog:
    def __init__(self, parent, callback, preview_callback=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Text Overlays")
        self.dialog.geometry("600x400")
        self.callback = callback
        self.preview_callback = preview_callback  # Add preview callback
        self.overlays = []
        self.dragging = False
        self.drag_source_index = None
        self.create_widgets()
        self.drag_line = None
        self.current_index = None  # Add this line
        self.drag_line_index = None  # Add this line to track the arrow position
        self.parent = parent  # Add this line to store parent reference

    def create_widgets(self):
        # Text overlays list
        list_frame = ttk.LabelFrame(self.dialog, text="Text Overlays", padding="5")
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.overlay_list = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE)
        self.overlay_list.pack(side=tk.LEFT, fill='both', expand=True)

        # Add drag and drop bindings
        self.overlay_list.bind('<Button-1>', self.on_press)
        self.overlay_list.bind('<B1-Motion>', self.on_motion)
        self.overlay_list.bind('<ButtonRelease-1>', self.on_release)

        # Add visual feedback
        self.drag_line = None

        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.overlay_list.yview)
        scroll.pack(side=tk.RIGHT, fill='y')
        self.overlay_list.configure(yscrollcommand=scroll.set)

        # Control buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill='x', padx=5, pady=5)

        # Add Delete All button
        ttk.Button(btn_frame, text="Delete All", 
                  command=self.delete_all_overlays,
                  style='Danger.TButton').pack(side=tk.LEFT, padx=2)
        
        # Existing buttons
        ttk.Button(btn_frame, text="Add", 
                  command=self.add_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", 
                  command=self.edit_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", 
                  command=self.remove_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="OK", 
                  command=self.ok).pack(side=tk.RIGHT, padx=2)

    def delete_all_overlays(self):
        """Delete all text overlays after confirmation"""
        if messagebox.askyesno("Confirm Delete All", 
                             "Are you sure you want to delete all text overlays?"):
            self.overlays.clear()
            self.update_list()
            self.callback(self.overlays)

    def on_press(self, event):
        """Handle mouse press to start drag operation"""
        self.drag_source_index = self.overlay_list.nearest(event.y)
        if 0 <= self.drag_source_index < len(self.overlays):
            self.dragging = True
            self.overlay_list.selection_clear(0, tk.END)
            self.overlay_list.selection_set(self.drag_source_index)
            return "break"  # Prevent default handling

    def on_motion(self, event):
        """Handle mouse motion during drag"""
        if not self.dragging:
            return
            
        current_index = self.overlay_list.nearest(event.y)
        if current_index < 0:
            current_index = 0
        elif current_index >= len(self.overlays):
            current_index = len(self.overlays) - 1
            
        # Remove previous arrow indicator
        if hasattr(self, 'drop_indicator'):
            self.overlay_list.delete(self.drop_indicator)
            
        # Don't show indicator at source position
        if current_index != self.drag_source_index:
            # Store insertion point
            self.drop_indicator = current_index
            self.overlay_list.insert(current_index, "▼")
        return "break"  # Prevent default handling

    def on_release(self, event):
        """Handle mouse release to complete drag operation"""
        if not self.dragging:
            return
            
        try:
            # Get drop position
            drop_index = getattr(self, 'drop_indicator', self.drag_source_index)
            if hasattr(self, 'drop_indicator'):
                self.overlay_list.delete(self.drop_indicator)
                
            if drop_index != self.drag_source_index and 0 <= drop_index < len(self.overlays):
                # Get the overlay being moved
                overlay = self.overlays.pop(self.drag_source_index)
                
                # Adjust drop index if needed
                if drop_index > self.drag_source_index:
                    drop_index -= 1
                    
                # Insert at new position
                self.overlays.insert(drop_index, overlay)
                
                # Update display and trigger preview
                self.update_list()
                if self.callback:
                    self.callback(self.overlays)
                
        finally:
            self.dragging = False
            self.drag_source_index = None
            if hasattr(self, 'drop_indicator'):
                delattr(self, 'drop_indicator')
        
        return "break"  # Prevent default handling

    def update_list(self):
        """Update the listbox display"""
        self.overlay_list.delete(0, tk.END)
        for idx, overlay in enumerate(self.overlays):
            # Add numbering to make order clear
            self.overlay_list.insert(tk.END, f"{idx + 1}. {overlay['text']} ({overlay['position']})")

    def add_overlay(self):
        dialog = TextOverlaySettingsDialog(self.dialog, 
                                         preview_callback=self.on_preview_update)
        self.dialog.wait_window(dialog.dialog)
        if dialog.result:
            self.overlays.append(dialog.result)
            self.update_list()
            self.callback(self.overlays)

    def edit_overlay(self):
        sel = self.overlay_list.curselection()
        if sel and sel[0] < len(self.overlays):  # Add bounds check
            idx = sel[0]
            dialog = TextOverlaySettingsDialog(self.dialog, 
                                             self.overlays[idx],
                                             preview_callback=self.on_preview_update)
            self.dialog.wait_window(dialog.dialog)
            if dialog.result:
                self.overlays[idx] = dialog.result
                self.update_list()
                self.callback(self.overlays)

    def remove_overlay(self):
        sel = self.overlay_list.curselection()
        if sel:
            idx = sel[0]
            del self.overlays[idx]
            self.update_list()
            self.callback(self.overlays)

    def update_list(self):
        self.overlay_list.delete(0, tk.END)
        for overlay in self.overlays:
            self.overlay_list.insert(tk.END, f"{overlay['text']} ({overlay['position']})")

    def ok(self):
        self.dialog.destroy()

    def on_preview_update(self, current_settings):
        """Handle preview updates during text overlay editing"""
        if self.preview_callback:
            # Create temporary overlay list with current edit
            temp_overlays = self.overlays.copy()
            sel = self.overlay_list.curselection()
            if sel:
                idx = sel[0]
                if idx < len(temp_overlays):
                    temp_overlays[idx] = current_settings
                else:
                    temp_overlays.append(current_settings)
            else:
                temp_overlays.append(current_settings)
            
            self.preview_callback(temp_overlays)

