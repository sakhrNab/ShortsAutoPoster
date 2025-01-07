import os
import sys
import glob
import time
import uuid
import logging
import random
import hashlib
import requests
import schedule
import threading
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Kivy imports
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import (
    StringProperty,
    ObjectProperty,
    BooleanProperty,
    ListProperty
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.checkbox import CheckBox
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recyclegridlayout import RecycleGridLayout

# Keep instabot for uploading
from instabot import Bot

# ========== Logging Setup ==========
logging.basicConfig(
    filename='instagram_uploader.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def logger(message, level='info'):
    """Unified logger to console + file."""
    if level == 'info':
        logging.info(message)
    elif level == 'error':
        logging.error(message)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")


# ========== Dependency Check ==========
def check_dependencies():
    required = {
        'requests': 'requests',
        'instabot': 'instabot',
        'kivy': 'kivy',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl'
    }
    missing = []
    for package, pip_name in required.items():
        try:
            __import__(package)
            logger(f"Package {package} is installed")
        except ImportError:
            missing.append(pip_name)
            logger(f"Missing required package: {pip_name}", level='error')
    
    if missing:
        raise ImportError(
            f"Missing required packages. Install with: pip install {' '.join(missing)}"
        )


# ========== Cookie Cleanup ==========
def cleanup_instagram_cookies():
    cookie_files = [
        'config/skhr_uuid_and_cookie.json',
        'config/skhr.checkpoint',
        'config/*.json'
    ]
    for pattern in cookie_files:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                logger(f"Removed cookie file: {f}")
            except:
                pass


# ========== Helpers for Generating Device IDs ==========
def generate_android_device_id():
    """Generate a valid Android device ID."""
    return 'android-' + hashlib.md5(str(time.time()).encode()).hexdigest()[:16]


# ========== Manual Login & Instabot Cookie Injection ==========
def manual_instagram_login(username, password):
    """
    Enhanced Instagram login with proper headers
    to avoid 'old app version' errors.
    Returns (requests.Session, cookie_dict).
    """
    session = requests.Session()

    # Generate device info
    android_id = generate_android_device_id()
    device_id = str(uuid.uuid4())
    phone_id = str(uuid.uuid4())
    uuid_id = str(uuid.uuid4())
    adid = str(uuid.uuid4())

    # Base headers
    session.headers.update({
        'User-Agent': 'Instagram 266.0.0.19.301 Android (31/12; 420dpi; 1080x2400; samsung; SM-G991B; o1s; exynos2100)',
        'Accept': '*/*',
        'Accept-Language': 'en-US',
        'Accept-Encoding': 'gzip, deflate',
        'X-IG-Capabilities': '3brTvw==',
        'X-IG-Connection-Type': 'WIFI',
        'X-IG-App-ID': '567067343352427',
        'X-IG-Device-ID': device_id,
        'X-IG-Android-ID': android_id
    })

    # GET initial cookies
    try:
        session.get('https://i.instagram.com/api/v1/si/fetch_headers/?challenge_type=signup')
    except Exception as e:
        logger(f"Failed to get initial cookies: {e}", level='error')
        raise

    # Build the login payload
    data = {
        'jazoest': '22387',
        'phone_id': phone_id,
        'device_id': android_id,
        '_csrftoken': session.cookies.get('csrftoken', 'missing'),
        'username': username,
        'adid': adid,
        'guid': uuid_id,
        'login_attempt_count': '0',
        '_uuid': uuid_id,
        # Use enc_password with a timestamp
        'enc_password': f"#PWD_INSTAGRAM:0:{int(time.time())}:{password}"
    }

    # Attempt login
    response = session.post(
        'https://i.instagram.com/api/v1/accounts/login/',
        data=data,
        allow_redirects=True
    )
    logger(f"Login response: {response.status_code} - {response.text}")

    if response.status_code == 200:
        json_response = response.json()
        if json_response.get('status') == 'ok':
            return session, requests.utils.dict_from_cookiejar(session.cookies)
        else:
            raise Exception(f"Login JSON error: {json_response}")
    else:
        raise Exception(f"Login failed: {response.status_code} - {response.text}")


def inject_cookies_into_instabot(bot, session, cookies):
    """
    Copy session cookies from manual login to instabot's internal session
    WITHOUT setting read-only user_id property.
    """
    try:
        # Force a fresh session
        bot.api.session = requests.Session()
        # Copy all cookies
        bot.api.session.cookies.update(cookies)
        # Also copy headers
        bot.api.session.headers.update(session.headers)
        # Mark as logged in
        bot.api.is_logged_in = True

        logger("Successfully injected cookies into instabot.")
    except Exception as e:
        logger(f"Failed to inject cookies: {e}", level='error')
        raise


# ========== Helper Functions for Reading Files & Uploading ==========

def get_processed_videos(folder_path):
    try:
        videos = []
        logger(f"Scanning directory: {folder_path}")
        logger(f"Directory contents: {os.listdir(folder_path)}")
        
        for file in os.listdir(folder_path):
            file_lower = file.lower()
            logger(f"Checking file: {file}")

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
        logger(f"Error scanning directory: {e}", level='error')
        return None

def read_excel(excel_path):
    try:
        df = pd.read_excel(excel_path, engine='openpyxl')
        required_columns = ['Video Title', 'Description', 'Hashtags', 'Likes', 'Views', 'Date', 'Filename']
        if not all(col in df.columns for col in required_columns):
            logger(f"Excel file missing required columns: {required_columns}", level='error')
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
    """Upload a single video with error handling for different instabot versions"""
    try:
        caption = f"{upload_details['description']} {upload_details['hashtags']}"
        video_path = upload_details['video_path']
        logger(f"Uploading video: {video_path}")

        # Some versions of instabot return bool, some return tuple
        try:
            uploaded = bot.upload_video(video_path, caption=caption)
            
            # Handle different return types
            if isinstance(uploaded, bool):
                if not uploaded:
                    raise Exception("Upload failed - returned False")
            elif isinstance(uploaded, tuple):
                status, response = uploaded
                if not status:
                    raise Exception(f"Upload failed: {response}")
                    
            logger(f"Successfully uploaded: {video_path}")
            return True
            
        except ValueError as e:
            # Handle unpacking error specifically
            if "cannot unpack" in str(e):
                # Try alternate upload method for older versions
                uploaded = bot.upload_video(video_path, caption)
                if not uploaded:
                    raise Exception("Upload failed with legacy method")
                logger(f"Successfully uploaded with legacy method: {video_path}")
                return True
            else:
                raise
                
    except Exception as e:
        logger(f"Failed to upload {video_path}: {e}", level='error')
        return False

def upload_job(bot, username, uploads):
    for upload in uploads:
        upload_single_video(bot, username, upload)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# ========== Kivy UI Classes ==========

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
        name = data.get('video_name', '')
        logger(f"Setting video name in item: {name}")
        self.video_name = name
        self.video_path = data.get('video_path', '')
        self.selected = data.get('selected', False)
        return super(VideoItem, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.selected = not self.selected
            self.parent.parent.data[self.index]['selected'] = self.selected
            logger(f"Video {self.video_name} selection: {self.selected}")
            return True
        return super(VideoItem, self).on_touch_down(touch)

class VideoRecycleView(RecycleView):
    def __init__(self, **kwargs):
        super(VideoRecycleView, self).__init__(**kwargs)
        self.data = []

    def populate_videos(self, videos):
        if not videos:
            logger("No videos to populate", level='error')
            return
        try:
            self.data = []
            for video in videos:
                if isinstance(video, dict):
                    name = video.get('base_name', '')
                    if not name:
                        path = video.get('video_path', video.get('full_path', ''))
                        if path:
                            name = os.path.basename(path)
                            name = os.path.splitext(name)[0]
                    name = name.replace('processed_', '')
                    logger(f"Processing video name: {name}")
                    path = video.get('video_path', video.get('full_path', ''))
                    entry = {
                        'video_name': name or 'Unnamed Video',
                        'video_path': path,
                        'selected': False
                    }
                    self.data.append(entry)
                    logger(f"Added video to list: {entry['video_name']}")
            
            logger(f"Populated RecycleView with {len(self.data)} videos")
            for item in self.data:
                logger(f"Video in list: {item['video_name']}")
                
        except Exception as e:
            logger(f"Error populating videos: {e}", level='error')

    def get_selected_videos(self):
        selected = [
            item['video_path']
            for item in self.data
            if item.get('selected', False)
        ]
        logger(f"Selected videos: {len(selected)}")
        return selected

class ScheduleItem(RecycleDataViewBehavior, BoxLayout):
    index = None
    schedule_time = StringProperty("")
    num_uploads = StringProperty("")
    assigned_videos = StringProperty("")

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


# ========== Main GUI Class with Manual + Instabot Hybrid Login ==========
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
        self.session = None
        self.cookies = None
        self.bot = None
        self.username = ""
        self.password = ""
        self.uploads = []
        self.scheduler_thread = None

    def show_load(self, select_folder=True):
        content = LoadDialog(
            load=self.load,
            cancel=self.dismiss_popup,
            select_folder=select_folder
        )
        content.select_folder = select_folder
        self._popup = Popup(
            title="Select Folder" if select_folder else "Select Excel File",
            content=content,
            size_hint=(0.9, 0.9)
        )
        self._popup.open()

    def load(self, path, selection, select_folder=True):
        try:
            logger(f"Loading {'folder' if select_folder else 'file'}: {path}")
            logger(f"Selection: {selection}")
            if select_folder:
                if not os.path.isdir(path):
                    self.show_message("Error", f"Invalid directory path: {path}")
                    return
                self.video_folder = path
                self.ids.video_folder_label.text = f"Selected Folder: {self.video_folder}"
                videos = get_processed_videos(self.video_folder)
                if videos:
                    self.ids.video_rv.populate_videos(videos)
                    logger(f"Loaded {len(videos)} videos.")
                else:
                    self.show_message("Error", "No suitable videos found.")
            elif selection:
                self.excel_file = selection[0]
                self.ids.excel_file_label.text = f"Selected Excel File: {self.excel_file}"
                logger(f"Excel file selected: {self.excel_file}")
            else:
                self.show_message("Error", "No selection made.")
            self.dismiss_popup()
        except Exception as e:
            logger(f"Error in load method: {e}", level='error')
            self.show_message("Error", f"Failed to load: {str(e)}")

    def dismiss_popup(self):
        self._popup.dismiss()

    def toggle_chunking(self, instance, value):
        self.upload_in_chunks = value
        self.ids.chunk_size_input.disabled = not self.upload_in_chunks

    def authenticate_instagram(self):
        # Prompt for username/password
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

        popup = Popup(
            title='Instagram Login',
            content=content,
            size_hint=(0.8, 0.6)
        )

        def on_submit(_):
            self.username = username_input.text.strip()
            self.password = password_input.text.strip()
            popup.dismiss()
            Clock.schedule_once(lambda dt: self.login_instagram(), 0)

        def on_cancel(_):
            popup.dismiss()

        submit_btn.bind(on_release=on_submit)
        cancel_btn.bind(on_release=on_cancel)
        popup.open()

    def login_instagram(self):
        if not self.username or not self.password:
            self.show_message("Error", "Username or Password cannot be empty.")
            return
        try:
            cleanup_instagram_cookies()

            # 1) Manual login
            session, cookies = manual_instagram_login(self.username, self.password)
            self.session = session
            self.cookies = cookies

            # 2) Create a fresh instabot
            self.bot = Bot()
            # Example device settings
            self.bot.api.device_settings = {
                'manufacturer': 'samsung',
                'model': 'SM-G991B',
                'android_version': 31,
                'android_release': '12'
            }
            self.bot.api.user_agent = (
                "Instagram 266.0.0.19.301 Android "
                "(31/12; 420dpi; 1080x2400; samsung; SM-G991B; o1s; exynos2100)"
            )

            # 3) Inject cookies so we can use .upload_video
            inject_cookies_into_instabot(self.bot, session, cookies)

            self.show_message("Success", "Logged in (manual + instabot)!")
            logger("Instagram login successful (manual + instabot).")

        except Exception as e:
            error_msg = str(e)
            self.show_message("Error", f"Login failed: {error_msg}")
            logger(f"Instagram login failed: {error_msg}", level='error')

    def show_message(self, title, message):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=message))
        btn = Button(text='OK', size_hint_y=None, height=40)
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.6, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def initiate_uploads(self):
        videos = get_processed_videos(self.video_folder)
        if not videos:
            self.show_message("Error", "No processed videos found.")
            return
        df = read_excel(self.excel_file)
        if df is None:
            self.show_message("Error", "Failed to read Excel file.")
            return
        self.uploads = prepare_uploads(videos, df)
        if self.uploads is None:
            self.show_message("Error", "No uploads prepared.")
            return
        self.show_message("Success", "Uploads have been prepared. Now you can upload or schedule.")

    def upload_now(self):
        # Ensure we have a bot and it is "logged in"
        if not self.bot or not self.bot.api.is_logged_in:
            self.show_message("Error", "Please authenticate with Instagram first.")
            return
        if not self.uploads:
            self.show_message("Error", "Please initiate uploads first.")
            return

        selected_videos = self.ids.video_rv.get_selected_videos()
        logger(f"Selected videos for upload: {len(selected_videos)}")
        if not selected_videos:
            self.show_message("Error", "No videos selected for upload.")
            return

        uploads_to_upload = []
        for upload in self.uploads:
            if upload['video_path'] in selected_videos:
                if os.path.exists(upload['video_path']):
                    uploads_to_upload.append(upload)
                else:
                    logger(f"Video not found: {upload['video_path']}", level='error')

        if not uploads_to_upload:
            self.show_message("Error", "No valid videos found.")
            return

        upload_thread = threading.Thread(
            target=upload_job,
            args=(self.bot, self.username, uploads_to_upload)
        )
        upload_thread.daemon = True
        upload_thread.start()

        self.show_message("Success", f"Started uploading {len(uploads_to_upload)} videos.")

    def add_schedule(self):
        if not self.uploads:
            self.show_message("Error", "Please initiate uploads first.")
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
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
        video_selection_rv = VideoRecycleView(size_hint_y=None, height=200)
        video_selection_rv.populate_videos(self.uploads)

        content.add_widget(Label(text='Add New Schedule', font_size=18, size_hint_y=None, height=30))
        content.add_widget(time_layout)
        content.add_widget(num_uploads_input)
        content.add_widget(Label(text='Select Videos:', size_hint_y=None, height=30))
        content.add_widget(video_selection_rv)

        btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
        submit_btn = Button(text='Add Schedule')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(submit_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='Add Schedule', content=content, size_hint=(0.9, 0.9))

        def on_submit(_):
            selected_videos = video_selection_rv.get_selected_videos()
            logger(f"Schedule submission: {len(selected_videos)} videos.")
            # TODO: implement schedule logic
            popup.dismiss()

        def on_cancel(_):
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

            interval = (
                datetime.combine(datetime.today(), end_time)
                - datetime.combine(datetime.today(), start_time)
            )
            if num_uploads > 0:
                interval_seconds = interval.total_seconds() / num_uploads
            else:
                interval_seconds = 0

            for i in range(num_uploads):
                scheduled_time = (
                    datetime.combine(datetime.today(), start_time)
                    + timedelta(seconds=interval_seconds * i)
                ).time()
                time_str = scheduled_time.strftime("%H:%M")
                if i < len(assigned_videos):
                    video_path = assigned_videos[i]
                else:
                    video_path = assigned_videos[-1]
                schedule.every().day.at(time_str).do(
                    upload_single_video,
                    self.bot, self.username,
                    next(
                        (up for up in self.uploads if up['video_path'] == video_path),
                        None
                    )
                )
                logger(f"Scheduled upload for {video_path} at {time_str}.")

        if not self.scheduler_thread or not self.scheduler_thread.is_alive():
            self.scheduler_thread = threading.Thread(target=run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger("Scheduler started.")

        self.show_message("Success", "All schedules set up.")

    def upload_scheduled_videos(self, video_path):
        upload_details = next(
            (up for up in self.uploads if up['video_path'] == video_path),
            None
        )
        if upload_details:
            upload_single_video(self.bot, self.username, upload_details)
        else:
            logger(f"No upload details found for: {video_path}", level='error')


# ========== Kivy Layout ==========

kv = """
<LoadDialog>:
    filechooser: filechooser
    BoxLayout:
        orientation: 'vertical'
        FileChooserIconView:
            id: filechooser
            filters: ["*/"] if root.select_folder else ["*.xlsx", "*.xls"]
            path: root.initial_path if hasattr(root, 'initial_path') else '.'
            select_dirs: root.select_folder
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
    height: 50
    padding: 10
    spacing: 15
    canvas.before:
        Color:
            rgba: 0.9, 0.9, 1, 1 if self.selected else 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size
    CheckBox:
        id: checkbox
        size_hint_x: None
        width: 30
        active: root.selected
        on_active:
            root.selected = self.active
            if root.parent: root.parent.parent.data[root.index]['selected'] = self.active
    Label:
        text: root.video_name if root.video_name else 'No name'
        color: 0, 0, 0, 1
        text_size: self.size
        halign: 'left'
        valign: 'middle'
        shorten: True
        shorten_from: 'right'
        size_hint_x: 1
        font_size: '14sp'

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
            size_hint_x: 0.2

    Label:
        text: "© 2025 Instagram Uploader"
        size_hint_y: None
        height: 30
"""

Builder.load_string(kv)

class InstagramUploaderApp(App):
    def build(self):
        return InstagramUploaderGUI()

def main():
    try:
        check_dependencies()
        InstagramUploaderApp().run()
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
