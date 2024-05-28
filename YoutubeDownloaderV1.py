import os
from yt_dlp import YoutubeDL
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import queue

def download_and_convert_video(url, output_format, output_folder, progress_bar, progress_label, msg_queue):
    ydl_opts = {
        'format': f'bestvideo[height<=720]+bestaudio/best[height<=720]' if output_format == 'mp4' else 'bestaudio',
        'merge_output_format': 'mp4' if output_format == 'mp4' else None,
        'noplaylist': True,
        'outtmpl': os.path.join(output_folder, '%(title)s [%(id)s].%(ext)s')
    }

    def hook(d):
        if d['status'] == 'downloading':
            progress_label.config(text=f"Downloading: {d['_percent_str']}")
            progress_bar['value'] = float(d['_percent_str'].strip('%'))
            progress_bar.update_idletasks()
        elif d['status'] == 'finished':
            progress_label.config(text="Download complete. Converting...")
            progress_bar['value'] = 100
            progress_bar.update_idletasks()

    ydl_opts['progress_hooks'] = [hook]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', None)
            downloaded_file = ydl.prepare_filename(info_dict)

        if output_format == 'mp4':
            output_file = sanitize_filename(title) + '_QT.mp4'
            output_file = os.path.join(output_folder, output_file)

            command = [
                'ffmpeg', '-y', '-i', downloaded_file,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'aac', '-b:a', '128k',
                output_file
            ]

            process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    progress = parse_ffmpeg_progress(output)
                    if progress:
                        progress_bar['value'] = progress
                        progress_label.config(text=f"Converting: {progress}%")
                        progress_bar.update_idletasks()
            process.wait()

            if process.returncode != 0:
                raise Exception("FFmpeg conversion failed")

            os.remove(downloaded_file)

        else:
            output_file = sanitize_filename(title) + '.mp3'
            output_file = os.path.join(output_folder, output_file)

            command = [
                'ffmpeg', '-y', '-i', downloaded_file,
                '-vn', '-acodec', 'libmp3lame', '-b:a', '192k',
                output_file
            ]

            process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    progress = parse_ffmpeg_progress(output)
                    if progress:
                        progress_bar['value'] = progress
                        progress_label.config(text=f"Converting: {progress}%")
                        progress_bar.update_idletasks()
            process.wait()

            if process.returncode != 0:
                raise Exception("FFmpeg conversion to MP3 failed")

            os.remove(downloaded_file)

        msg_queue.put(("success", f"Downloaded '{title}' successfully.\nOutput file: {output_file}"))
    except Exception as e:
        msg_queue.put(("error", f"An error occurred: {e}"))

    progress_bar['value'] = 100
    progress_label.config(text="Conversion complete")
    progress_bar.update_idletasks()

def parse_ffmpeg_progress(output):
    if "frame=" in output:
        parts = output.split(' ')
        for part in parts:
            if "time=" in part:
                time_str = part.split('=')[1]
                h, m, s = map(float, time_str.split(':'))
                time_in_seconds = h * 3600 + m * 60 + s
                total_time = 3600
                return (time_in_seconds / total_time) * 100
    return None

def sanitize_filename(filename):
    invalid_chars = '\\/:*?"<>|'
    return ''.join(c if c.isalnum() or c in [' ', '.', '_'] else '_' for c in filename if c not in invalid_chars)

def start_download():
    url = url_entry.get().strip()
    output_format = format_var.get()
    output_folder = folder_path.get()

    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL.")
        return
    if not output_folder:
        messagebox.showerror("Error", "Please choose a download folder.")
        return

    progress_bar['value'] = 0
    progress_label.config(text="Starting download...")
    progress_bar.update_idletasks()

    def run():
        download_and_convert_video(url, output_format, output_folder, progress_bar, progress_label, msg_queue)

    threading.Thread(target=run).start()

def process_queue():
    try:
        msg_type, msg = msg_queue.get_nowait()
        if msg_type == "success":
            messagebox.showinfo("Success", msg)
        elif msg_type == "error":
            messagebox.showerror("Error", msg)
    except queue.Empty:
        root.after(100, process_queue)

def choose_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_path.set(folder_selected)

def main():
    global url_entry, format_var, folder_path, progress_bar, progress_label, msg_queue, root

    root = tk.Tk()
    root.title("YouTube Video Downloader")

    tk.Label(root, text="YouTube URL:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
    url_entry = tk.Entry(root, width=50)
    url_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(root, text="Format:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
    format_var = tk.StringVar(value='mp4')
    tk.Radiobutton(root, text="MP4", variable=format_var, value='mp4').grid(row=1, column=1, padx=5, pady=5, sticky='w')
    tk.Radiobutton(root, text="MP3", variable=format_var, value='mp3').grid(row=1, column=1, padx=5, pady=5)

    tk.Label(root, text="Download Folder:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
    folder_path = tk.StringVar()
    tk.Entry(root, textvariable=folder_path, width=50).grid(row=2, column=1, padx=5, pady=5)
    tk.Button(root, text="Browse", command=choose_folder).grid(row=2, column=2, padx=5, pady=5)

    tk.Button(root, text="Download", command=start_download).grid(row=3, column=1, padx=5, pady=10)

    progress_label = tk.Label(root, text="")
    progress_label.grid(row=4, column=1, padx=5, pady=5)
    progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
    progress_bar.grid(row=5, column=1, padx=5, pady=5)

    warning_label = tk.Label(root, text="DO NOT CLOSE THIS APP WHILE DOWNLOADING", fg="red", font=("Helvetica", 10, "bold"))
    warning_label.grid(row=6, column=1, padx=5, pady=10)

    msg_queue = queue.Queue()
    root.after(100, process_queue)

    root.mainloop()

if __name__ == "__main__":
    main()
