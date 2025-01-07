import os
import sys
import pandas as pd
import schedule
import time
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path
from instabot import Bot
import threading
import logging

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty, ListProperty
from kivy.clock import Clock
from kivy.uix.recycleview import RecycleView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.checkbox import CheckBox
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recyclegridlayout import RecycleGridLayout

# =========================
# Configuration and Setup
# =========================

# Setup logging
logging.basicConfig(
    filename='instagram_uploader.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def logger(message, level='info'):
    if level == 'info':
        logging.info(message)
    elif level == 'error':
        logging.error(message)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

# =========================
# Helper Functions
# =========================

def get_processed_videos(folder_path):
    try:
        videos = []
        logger(f"Scanning directory: {folder_path}")
        logger(f"Directory contents: {os.listdir(folder_path)}")
        
        for file in os.listdir(folder_path):
            file_lower = file.lower()
            # Log each file being checked
            logger(f"Checking file: {file}")
            
            # More flexible pattern matching
            is_video = file_lower.endswith(('.mp4', '.mov', '.avi'))
            is_processed = (
                file_lower.startswith('processed_') or 
                'processed' in file_lower or 
                file_lower.startswith('p_')
            )
            
            if is_video:
                full_path = os.path.join(folder_path, file)
                if not os.access(full_path, os.R_OK):
                    logger(f"File not accessible: {full_path}", level='error')
                    continue
                    
                base_name = file
                if is_processed:
                    base_name = file[file.find('_')+1:] if '_' in file else file
                
                videos.append({
                    'full_path': full_path,
                    'base_name': base_name
                })
                logger(f"Added video: {base_name}")

        if not videos:
            logger("No video files found in the selected folder.", level='error')
            return None
            
        logger(f"Found {len(videos)} video(s).")
        return videos
        
    except Exception as e:
        logger(f"Error scanning directory: {str(e)}", level='error')
        return None

def read_excel(excel_path):
    try:
        df = pd.read_excel(excel_path, engine='openpyxl')
        required_columns = ['Video Title', 'Description', 'Hashtags', 'Likes', 'Views', 'Date', 'Filename']
        if not all(col in df.columns for col in required_columns):
            logger(f"Excel file is missing one of the required columns: {required_columns}", level='error')
            return None
        logger("Excel file read successfully.")
        return df
    except Exception as e:
        logger(f"Error reading Excel file: {e}", level='error')
        return None

def prepare_uploads(videos, df):
    uploads = []
    for video in videos:
        matching_rows = df[df['Filename'] == video['base_name']]
        if not matching_rows.empty:
            row = matching_rows.iloc[0]
            uploads.append({
                'video_path': video['full_path'],
                'title': row['Video Title'],
                'description': row['Description'],
                'hashtags': row['Hashtags'],
                'likes': row['Likes'],
                'views': row['Views'],
                'date': row['Date']
            })
        else:
            logger(f"No matching entry found in Excel for video: {video['base_name']}", level='error')
    if not uploads:
        logger("No uploads prepared.", level='error')
        return None
    logger(f"Prepared {len(uploads)} upload(s).")
    return uploads

def upload_single_video(bot, username, upload_details):
    try:
        caption = f"{upload_details['description']} {upload_details['hashtags']}"
        video_path = upload_details['video_path']
        logger(f"Uploading video: {video_path}")
        bot.upload_video(video_path, caption=caption)
        logger(f"Successfully uploaded: {video_path}")
    except Exception as e:
        logger(f"Failed to upload {video_path}: {e}", level='error')

def upload_job(bot, username, uploads):
    for upload in uploads:
        upload_single_video(bot, username, upload)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# =========================
# Kivy UI Components
# =========================

class LoadDialog(Popup):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)
    filechooser = ObjectProperty(None)
    select_folder = BooleanProperty(True)

class VideoItem(RecycleDataViewBehavior, BoxLayout):
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    video_name = StringProperty("")
    video_path = StringProperty("")

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.video_name = data.get('video_name', '')
        self.video_path = data.get('video_path', '')
        self.selected = data.get('selected', False)
        return super(VideoItem, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.selected = not self.selected
            self.parent.parent.data[self.index]['selected'] = self.selected
            logger(f"Video {self.video_name} selection state changed to: {self.selected}")
            return True
        return super(VideoItem, self).on_touch_down(touch)

class VideoRecycleView(RecycleView):
    def __init__(self, **kwargs):
        super(VideoRecycleView, self).__init__(**kwargs)
        self.data = []

    def populate_videos(self, videos):
        if isinstance(videos, list) and videos:
            # Check if videos is list of dicts or upload details
            if 'video_path' in videos[0]:  # Upload details format
                self.data = [{
                    'video_name': os.path.basename(video['video_path']),
                    'video_path': video['video_path'],
                    'selected': False
                } for video in videos]
            else:  # Original video list format
                self.data = [{
                    'video_name': video['base_name'],
                    'video_path': video['full_path'],
                    'selected': False
                } for video in videos]
            logger(f"Populated RecycleView with {len(self.data)} videos.")
        else:
            logger("Invalid video data format", level='error')
            self.data = []

    def get_selected_videos(self):
        selected = [item['video_path'] for item in self.data if item.get('selected', False)]
        logger(f"Getting selected videos: {len(selected)} videos selected")
        return selected

class ScheduleItem(RecycleDataViewBehavior, BoxLayout):
    index = None
    schedule_time = StringProperty("")
    num_uploads = StringProperty("")
    assigned_videos = StringProperty("")  # Changed from ListProperty to StringProperty

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        return super(ScheduleItem, self).refresh_view_attrs(rv, index, data)

class ScheduleRecycleView(RecycleView):
    def __init__(self, **kwargs):
        super(ScheduleRecycleView, self).__init__(**kwargs)
        self.data = []

    def add_schedule(self, schedule_entry):
        self.data.append({
            'schedule_time': schedule_entry['time_range'],
            'num_uploads': str(schedule_entry['num_uploads']),
            'assigned_videos': ', '.join(schedule_entry['assigned_videos'])
        })
        logger(f"Added schedule: {schedule_entry['time_range']} with {schedule_entry['num_uploads']} uploads.")

class InstagramUploaderGUI(BoxLayout):
    video_folder = StringProperty("")
    excel_file = StringProperty("")
    num_uploads_per_day = StringProperty("1")
    start_time = StringProperty("09:00")
    end_time = StringProperty("18:00")
    upload_in_chunks = BooleanProperty(False)
    chunk_size = StringProperty("1")
    is_scheduling = BooleanProperty(False)
    schedules = ListProperty([])

    def __init__(self, **kwargs):
        super(InstagramUploaderGUI, self).__init__(**kwargs)
        self.bot = None
        self.username = ""
        self.password = ""
        self.uploads = []
        self.scheduler_thread = None

    def show_load(self, select_folder=True):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup, select_folder=select_folder)
        content.select_folder = select_folder
        self._popup = Popup(title="Select Folder" if select_folder else "Select Excel File",
                            content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, selection, select_folder=True):
        try:
            logger(f"Loading {'folder' if select_folder else 'file'} from path: {path}")
            logger(f"Selection: {selection}")
            logger(f"Directory exists: {os.path.exists(path)}")
            logger(f"Is directory: {os.path.isdir(path)}")
            
            if select_folder:
                if not os.path.isdir(path):
                    self.show_message("Error", f"Invalid directory path: {path}")
                    return
                    
                self.video_folder = path
                self.ids.video_folder_label.text = f"Selected Folder: {self.video_folder}"
                
                videos = get_processed_videos(self.video_folder)
                if videos:
                    self.ids.video_rv.populate_videos(videos)
                    logger(f"Successfully loaded {len(videos)} videos from folder")
                else:
                    self.show_message("Error", "No suitable videos found in the selected folder.")
            elif selection:
                self.excel_file = selection[0]
                self.ids.excel_file_label.text = f"Selected Excel File: {self.excel_file}"
                logger(f"Successfully loaded Excel file: {self.excel_file}")
            else:
                self.show_message("Error", "No selection made.")
                
            self.dismiss_popup()
            
        except Exception as e:
            logger(f"Error in load method: {str(e)}", level='error')
            self.show_message("Error", f"Failed to load: {str(e)}")

    def dismiss_popup(self):
        self._popup.dismiss()

    def toggle_chunking(self, instance, value):
        self.upload_in_chunks = value
        self.ids.chunk_size_input.disabled = not self.upload_in_chunks

    def authenticate_instagram(self):
        # Prompt for username and password via popup
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        username_input = TextInput(hint_text='Instagram Username', multiline=False)
        password_input = TextInput(hint_text='Instagram Password', multiline=False, password=True)
        btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
        submit_btn = Button(text='Submit')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(submit_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(Label(text='Enter Instagram Credentials', size_hint_y=None, height=30))
        content.add_widget(username_input)
        content.add_widget(password_input)
        content.add_widget(btn_layout)

        popup = Popup(title='Instagram Login',
                      content=content,
                      size_hint=(0.8, 0.6))

        def on_submit(instance):
            self.username = username_input.text.strip()
            self.password = password_input.text.strip()
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.login_instagram(), 0)

        def on_cancel(instance):
            popup.dismiss()

        submit_btn.bind(on_release=on_submit)
        cancel_btn.bind(on_release=on_cancel)

        popup.open()

    def login_instagram(self):
        if not self.username or not self.password:
            self.show_message("Error", "Username or Password cannot be empty.")
            return
        self.bot = Bot()
        try:
            self.bot.login(username=self.username, password=self.password)
            self.show_message("Success", "Logged in to Instagram successfully.")
            logger("Logged in to Instagram successfully.")
        except Exception as e:
            self.show_message("Error", f"Failed to login to Instagram: {e}")
            logger(f"Failed to login to Instagram: {e}", level='error')

    def show_message(self, title, message):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=message))
        btn = Button(text='OK', size_hint_y=None, height=40)
        content.add_widget(btn)
        popup = Popup(title=title,
                      content=content,
                      size_hint=(0.6, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def initiate_uploads(self):
        # Read videos and Excel
        videos = get_processed_videos(self.video_folder)
        if not videos:
            self.show_message("Error", "No processed videos found.")
            return

        df = read_excel(self.excel_file)
        if df is None:
            self.show_message("Error", "Failed to read Excel file.")
            return

        # Prepare uploads
        self.uploads = prepare_uploads(videos, df)
        if self.uploads is None:
            self.show_message("Error", "No uploads prepared.")
            return

        self.show_message("Success", "Uploads have been prepared. You can now upload selected videos or set schedules.")

    def upload_now(self):
        # Get selected videos using the new method
        selected_videos = self.ids.video_rv.get_selected_videos()
        logger(f"Attempting to upload {len(selected_videos)} selected videos")
        
        if not selected_videos:
            self.show_message("Error", "No videos selected for upload.")
            return

        # Filter uploads
        uploads_to_upload = [upload for upload in self.uploads if upload['video_path'] in selected_videos]
        
        if not uploads_to_upload:
            self.show_message("Error", "No matching uploads found for selected videos.")
            return

        threading.Thread(target=upload_job, args=(self.bot, self.username, uploads_to_upload)).start()
        self.show_message("Success", f"Uploading {len(uploads_to_upload)} videos.")

    def add_schedule(self):
        if not self.uploads:
            self.show_message("Error", "Please initiate uploads first.")
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # Time inputs in horizontal layout
        time_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        start_time_input = TextInput(hint_text='Start Time (HH:MM)', multiline=False)
        end_time_input = TextInput(hint_text='End Time (HH:MM)', multiline=False)
        time_layout.add_widget(start_time_input)
        time_layout.add_widget(end_time_input)
        
        num_uploads_input = TextInput(
            hint_text='Number of Uploads',
            multiline=False,
            input_filter='int',
            size_hint_y=None,
            height=40
        )
        
        # Video selection with scrollview
        video_selection_rv = VideoRecycleView(size_hint_y=None, height=200)
        video_selection_rv.populate_videos(self.uploads)

        # Add widgets to content
        content.add_widget(Label(text='Add New Schedule', font_size=18, size_hint_y=None, height=30))
        content.add_widget(time_layout)
        content.add_widget(num_uploads_input)
        content.add_widget(Label(text='Select Videos:', size_hint_y=None, height=30))
        content.add_widget(video_selection_rv)
        
        # Button layout
        btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
        submit_btn = Button(text='Add Schedule')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(submit_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='Add Schedule', content=content, size_hint=(0.9, 0.9))

        def on_submit(instance):
            selected_videos = video_selection_rv.get_selected_videos()
            logger(f"Schedule submission - Selected videos: {len(selected_videos)}")
            
            # ... rest of the submission logic ...

        def on_cancel(instance):
            popup.dismiss()

        submit_btn.bind(on_release=on_submit)
        cancel_btn.bind(on_release=on_cancel)

        popup.open()

    def calculate_rv_height(self, num_items):
        return num_items * 40 if num_items * 40 < 300 else 300

    def setup_scheduler(self):
        if not self.schedules:
            self.show_message("Error", "No schedules to set up.")
            return

        for schedule_entry in self.schedules:
            time_range = schedule_entry['time_range']
            start_time = schedule_entry['start_time']
            end_time = schedule_entry['end_time']
            num_uploads = schedule_entry['num_uploads']
            assigned_videos = schedule_entry['assigned_videos']

            # Calculate the interval between uploads within the time range
            interval = (datetime.combine(datetime.today(), end_time) - 
                        datetime.combine(datetime.today(), start_time))
            if num_uploads > 0:
                interval_seconds = interval.total_seconds() / num_uploads
            else:
                interval_seconds = 0

            for i in range(num_uploads):
                scheduled_time = (datetime.combine(datetime.today(), start_time) + 
                                  timedelta(seconds=interval_seconds * i)).time()
                time_str = scheduled_time.strftime("%H:%M")
                # Schedule the upload
                # Ensure index does not go out of range
                if i < len(assigned_videos):
                    video_path = assigned_videos[i]
                else:
                    video_path = assigned_videos[-1]
                schedule.every().day.at(time_str).do(upload_single_video, self.bot, self.username, next((upload for upload in self.uploads if upload['video_path'] == video_path), None))
                logger(f"Scheduled upload for {video_path} at {time_str}.")

        # Start the scheduler in a separate thread
        if not self.scheduler_thread or not self.scheduler_thread.is_alive():
            self.scheduler_thread = threading.Thread(target=run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger("Scheduler started.")

        self.show_message("Success", "All schedules have been set up.")

    def upload_scheduled_videos(self, video_path):
        # Find the upload details for the video
        upload_details = next((upload for upload in self.uploads if upload['video_path'] == video_path), None)
        if upload_details:
            upload_single_video(self.bot, self.username, upload_details)
        else:
            logger(f"No upload details found for video: {video_path}", level='error')

# =========================
# Kivy UI Definitions
# =========================

from kivy.lang import Builder

kv = """
<LoadDialog>:
    filechooser: filechooser  # Bind the filechooser property
    BoxLayout:
        orientation: 'vertical'
        FileChooserIconView:
            id: filechooser
            filters: ["*/"] if root.select_folder else ["*.xlsx", "*.xls"]
            path: root.initial_path if hasattr(root, 'initial_path') else '.'
            select_dirs: root.select_folder  # Enable directory selection when needed
        BoxLayout:
            size_hint_y: None
            height: 40
            spacing: 10
            padding: 10
            Button:
                text: "Load"
                on_release: root.load(filechooser.path, filechooser.selection, root.select_folder)
            Button:
                text: "Cancel"
                on_release: root.cancel()
                
<VideoItem>:
    orientation: 'horizontal'
    size_hint_y: None
    height: 40
    padding: 5
    spacing: 10
    canvas.before:
        Color:
            rgba: 0.9, 0.9, 1, 1 if self.selected else 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    CheckBox:
        id: checkbox
        active: root.selected
        on_active: 
            root.selected = self.active
            root.parent.parent.data[root.index]['selected'] = self.active if root.parent else False

    Label:
        text: root.video_name if root.video_name else 'No name'
        halign: "left"
        valign: "middle"
        text_size: self.size

<ScheduleItem>:
    orientation: 'horizontal'
    size_hint_y: None
    height: 40
    padding: 5
    spacing: 10

    Label:
        text: root.schedule_time
        halign: "left"
        valign: "middle"
        text_size: self.size

    Label:
        text: root.num_uploads
        halign: "center"
        valign: "middle"
        text_size: self.size

    Label:
        text: root.assigned_videos
        halign: "left"
        valign: "middle"
        text_size: self.size

<InstagramUploaderGUI>:
    orientation: 'vertical'
    padding: 20
    spacing: 20

    Label:
        text: "Instagram Video Uploader"
        font_size: 24
        size_hint_y: None
        height: 40

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: 200
        spacing: 10

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10

            Button:
                text: "Select Video Folder"
                on_release: root.show_load(select_folder=True)
            Label:
                id: video_folder_label
                text: "No folder selected."
                text_size: self.size
                halign: "left"
                valign: "middle"

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10

            Button:
                text: "Select Excel File"
                on_release: root.show_load(select_folder=False)
            Label:
                id: excel_file_label
                text: "No file selected."
                text_size: self.size
                halign: "left"
                valign: "middle"

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        size_hint_y: None
        height: 50

        Button:
            text: "Authenticate Instagram"
            on_release: root.authenticate_instagram()
        Button:
            text: "Initiate Uploads"
            on_release: root.initiate_uploads()

    Label:
        text: "Select Videos to Upload:"
        font_size: 18
        size_hint_y: None
        height: 30

    VideoRecycleView:
        id: video_rv
        viewclass: 'VideoItem'
        RecycleBoxLayout:
            default_size: None, dp(40)
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height
            orientation: 'vertical'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        size_hint_y: None
        height: 50

        Button:
            text: "Upload Now"
            on_release: root.upload_now()
        Button:
            text: "Add Schedule"
            on_release: root.add_schedule()
        Button:
            text: "Setup Scheduler"
            on_release: root.setup_scheduler()

    Label:
        text: "Schedules:"
        font_size: 18
        size_hint_y: None
        height: 30

    ScheduleRecycleView:
        id: schedule_rv
        viewclass: 'ScheduleItem'
        RecycleBoxLayout:
            default_size: None, dp(40)
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height
            orientation: 'vertical'

    BoxLayout:
        orientation: 'horizontal'
        spacing: 10
        size_hint_y: None
        height: 50

        ToggleButton:
            text: "Enable Chunk Uploading"
            state: 'down' if root.upload_in_chunks else 'normal'
            on_state: root.toggle_chunking(self, self.state == 'down')

        Label:
            text: "Chunk Size:"
            size_hint_x: 0.3
            halign: "left"
            valign: "middle"
            text_size: self.size

        TextInput:
            id: chunk_size_input
            text: root.chunk_size
            multiline: False
            input_filter: 'int'
            disabled: not root.upload_in_chunks
            hint_text: "Number of Videos per Chunk"
            size_hint_x: 0.2  # Increased width for better visibility

    Label:
        text: "© 2025 Instagram Uploader"
        size_hint_y: None
        height: 30
"""

Builder.load_string(kv)

# =========================
# Main Execution Flow
# =========================

class InstagramUploaderApp(App):
    def build(self):
        return InstagramUploaderGUI()

def main():
    InstagramUploaderApp().run()

if __name__ == "__main__":
    main()
