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
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.clock import Clock

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
    videos = []
    for file in os.listdir(folder_path):
        if file.startswith("processed_") and file.endswith(".mp4"):
            base_name = file[len("processed_"):-4]  # Remove 'processed_' and '.mp4'
            videos.append({
                'full_path': os.path.join(folder_path, file),
                'base_name': base_name
            })
    if not videos:
        logger("No processed video files found in the selected folder.", level='error')
        return None
    logger(f"Found {len(videos)} processed video(s).")
    return videos

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

class InstagramUploaderGUI(BoxLayout):
    video_folder = StringProperty("")
    excel_file = StringProperty("")
    num_uploads_per_day = StringProperty("1")
    start_time = StringProperty("09:00")
    end_time = StringProperty("18:00")
    upload_in_chunks = BooleanProperty(False)
    chunk_size = StringProperty("1")
    is_scheduling = BooleanProperty(False)

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

    def load(self, path, filename, select_folder=True):
        if select_folder:
            self.video_folder = path
            self.ids.video_folder_label.text = f"Selected Folder: {self.video_folder}"
        else:
            if filename:
                self.excel_file = filename[0]
                self.ids.excel_file_label.text = f"Selected Excel File: {self.excel_file}"
        self.dismiss_popup()

    def dismiss_popup(self):
        self._popup.dismiss()

    def toggle_chunking(self, instance, value):
        self.upload_in_chunks = value
        self.ids.chunk_size_input.disabled = not self.upload_in_chunks

    def authenticate_instagram(self):
        # Prompt for username and password
        content = BoxLayout(orientation='vertical')
        username_input = TextInput(hint_text='Instagram Username', multiline=False)
        password_input = TextInput(hint_text='Instagram Password', multiline=False, password=True)
        btn_layout = BoxLayout(size_hint_y=None, height=50)
        submit_btn = Button(text='Submit')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(submit_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(Label(text='Enter Instagram Credentials'))
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
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text=message))
        btn = Button(text='OK', size_hint=(1, 0.3))
        content.add_widget(btn)
        popup = Popup(title=title,
                      content=content,
                      size_hint=(0.6, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def start_upload_process(self):
        # Validate inputs
        if not self.video_folder or not self.excel_file:
            self.show_message("Error", "Please select both video folder and Excel file.")
            return

        # Authenticate with Instagram
        self.authenticate_instagram()

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

        # Get scheduling preferences
        try:
            self.num_uploads_per_day = int(self.num_uploads_per_day)
            if self.num_uploads_per_day <= 0:
                raise ValueError
        except ValueError:
            self.show_message("Error", "Number of uploads per day must be a positive integer.")
            return

        # Get time range
        try:
            start_time_obj = datetime.strptime(self.start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(self.end_time, "%H:%M").time()
            if start_time_obj >= end_time_obj:
                self.show_message("Error", "Start time must be earlier than end time.")
                return
        except ValueError:
            self.show_message("Error", "Time must be in HH:MM format.")
            return

        # Check for chunking
        if self.upload_in_chunks:
            try:
                self.chunk_size = int(self.chunk_size)
                if self.chunk_size <= 0:
                    raise ValueError
            except ValueError:
                self.show_message("Error", "Chunk size must be a positive integer.")
                return

        # Proceed with scheduling or immediate upload
        if self.num_uploads_per_day > 0:
            self.is_scheduling = True
            Clock.schedule_once(lambda dt: self.setup_scheduler(start_time_obj, end_time_obj), 0)
        else:
            self.is_scheduling = False
            self.perform_uploads()

    def perform_uploads(self):
        if self.upload_in_chunks:
            self.upload_in_chunks_method()
        else:
            # Immediate upload without chunking
            threading.Thread(target=upload_job, args=(self.bot, self.username, self.uploads)).start()
            self.show_message("Success", "Uploads have been initiated.")

    def upload_in_chunks_method(self):
        chunk_size = self.chunk_size
        chunks = [self.uploads[i:i + chunk_size] for i in range(0, len(self.uploads), chunk_size)]
        def upload_chunk(chunk, idx):
            logger(f"Uploading chunk {idx + 1}/{len(chunks)} with {len(chunk)} video(s).")
            upload_job(self.bot, self.username, chunk)
            logger(f"Chunk {idx + 1} uploaded successfully.")
        
        for idx, chunk in enumerate(chunks):
            threading.Thread(target=upload_chunk, args=(chunk, idx+1)).start()
            time.sleep(5)  # Delay between chunks to avoid rate limiting
        self.show_message("Success", "All chunks have been uploaded.")

    def setup_scheduler(self, start_time, end_time):
        total_uploads = len(self.uploads)
        num_per_day = self.num_uploads_per_day
        days_needed = (total_uploads // num_per_day) + (1 if total_uploads % num_per_day else 0)
        logger(f"Scheduling uploads over {days_needed} day(s).")

        uploads_iter = iter(self.uploads)

        for day in range(days_needed):
            for i in range(num_per_day):
                try:
                    upload = next(uploads_iter)
                    # Calculate scheduled time
                    interval = (datetime.combine(datetime.today(), end_time) - 
                                datetime.combine(datetime.today(), start_time))
                    interval_seconds = interval.total_seconds() / num_per_day
                    scheduled_time = (datetime.combine(datetime.today(), start_time) + 
                                      timedelta(seconds=interval_seconds * i)).time()
                    # Format time as HH:MM
                    time_str = scheduled_time.strftime("%H:%M")
                    # Schedule the upload
                    schedule.every().day.at(time_str).do(upload_single_video, self.bot, self.username, upload)
                    logger(f"Scheduled upload for {upload['video_path']} at {time_str} daily.")
                except StopIteration:
                    break

        # Start the scheduler in a separate thread
        if not self.scheduler_thread or not self.scheduler_thread.is_alive():
            self.scheduler_thread = threading.Thread(target=run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger("Scheduler started.")
        self.show_message("Success", "Uploads have been scheduled.")

class InstagramUploaderApp(App):
    def build(self):
        return InstagramUploaderGUI()

# =========================
# Kivy UI Definitions
# =========================

from kivy.lang import Builder

kv = """
<LoadDialog>:
    BoxLayout:
        orientation: 'vertical'
        FileChooserIconView:
            id: filechooser
            filters: ["*/"] if root.select_folder else ["*.xlsx", "*.xls"]
            path: root.initial_path if hasattr(root, 'initial_path') else '.'
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
        height: 150
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
        orientation: 'vertical'
        spacing: 10

        Label:
            text: "Scheduling Preferences"
            font_size: 18
            size_hint_y: None
            height: 30

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10

            Label:
                text: "Uploads per Day:"
                size_hint_x: 0.4
            TextInput:
                id: uploads_per_day
                text: root.num_uploads_per_day
                multiline: False
                input_filter: 'int'
                on_text: root.num_uploads_per_day = self.text

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10

            Label:
                text: "Start Time (HH:MM):"
                size_hint_x: 0.4
            TextInput:
                id: start_time
                text: root.start_time
                multiline: False
                input_filter: 'int'
                on_text: root.start_time = self.text

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10

            Label:
                text: "End Time (HH:MM):"
                size_hint_x: 0.4
            TextInput:
                id: end_time
                text: root.end_time
                multiline: False
                input_filter: 'int'
                on_text: root.end_time = self.text

    BoxLayout:
        orientation: 'horizontal'
        size_hint_y: None
        height: 50
        spacing: 10
        padding: 10

        ToggleButton:
            text: "Enable Chunk Uploading"
            state: 'down' if root.upload_in_chunks else 'normal'
            on_state: root.toggle_chunking(self, self.state == 'down')
        TextInput:
            id: chunk_size_input
            text: root.chunk_size
            multiline: False
            input_filter: 'int'
            disabled: not root.upload_in_chunks
            hint_text: "Chunk Size"

    Button:
        text: "Start Upload"
        size_hint_y: None
        height: 50
        on_release: root.start_upload_process()

    Label:
        text: "© 2025 Instagram Uploader"
        size_hint_y: None
        height: 30
"""

Builder.load_string(kv)

# =========================
# Main Execution Flow
# =========================

def main():
    InstagramUploaderApp().run()

if __name__ == "__main__":
    main()
