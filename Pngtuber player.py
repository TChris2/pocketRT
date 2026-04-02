
import pygame
import sys
import os
import time
import threading
import random
import tkinter as tk


def resource_path(relative_path: str) -> str:
    """Resolve a path both when running from source and from a bundled EXE."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


MEDIA_FOLDER = "Media"
SPRITESHEET_FILE = "RT_PngTuber.png"
ICON_FILE = "Icon.ico"

SPRITESHEET_PATH = resource_path(os.path.join(MEDIA_FOLDER, SPRITESHEET_FILE))
ICON_PATH = resource_path(os.path.join(MEDIA_FOLDER, ICON_FILE))

SPRITESHEET_COLS = 5
SPRITESHEET_ROWS = 2
IDLE_FRAME_NUMBERS = list(range(1, 10))
ACTIVE_FRAME_NUMBER = 10

AUDIO_INTERVAL = 30
PNGTUBER_SIZE = 380
PNGTUBER_MARGIN = 16
TALK_FPS = 8
CORNER = "bottom-right"
BOTTOM_LIFT = 26

# Clip Types
CLIPTYPE_LIST = {"Drift King"}
ALL_CLIPTYPES = {"Drift King", "Hurt SFX", "Noises", "NSFW", "SFW", "Toad", "Youtube"}


def load_png(path: str, size: int) -> pygame.Surface:
    """Load a PNG (with alpha) and scale it to size×size."""
    if not os.path.exists(path):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        colour = (80, 200, 120, 200) if "idle" in path else (255, 140, 60, 200)
        pygame.draw.ellipse(surf, colour, surf.get_rect())
        font = pygame.font.SysFont(None, 22)
        label = "idle" if "idle" in path else "talk"
        text = font.render(label, True, (255, 255, 255))
        surf.blit(text, text.get_rect(center=(size // 2, size // 2)))
        print(f"[warn] '{path}' not found – using placeholder.")
        return surf
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))

def list_mp3_files(folder_path: str) -> list[str]:
    """Return absolute paths for all MP3 files found in subfolders of the given folder."""
    if not os.path.isdir(folder_path):
        return []

    files: list[str] = []
    for subfolder in os.listdir(folder_path):
        subfolder_path = os.path.join(folder_path, subfolder)
        # Checks to see if current subfolder is in Cliptype list
        if os.path.isdir(subfolder_path) and subfolder in CLIPTYPE_LIST:
            for name in os.listdir(subfolder_path):
                path = os.path.join(subfolder_path, name)
                if os.path.isfile(path) and name.lower().endswith(".mp3"):
                    files.append(path)
    return files


def build_audio_cycle(audio_files: list[str], last_played: str | None = None) -> list[str]:
    """Return a shuffled queue that uses every clip once before repeating."""
    queue = audio_files[:]
    random.shuffle(queue)
    if last_played and len(queue) > 1 and queue[0] == last_played:
        queue[0], queue[1] = queue[1], queue[0]
    return queue


def load_spritesheet(path: str, cols: int, rows: int, size: int) -> list[pygame.Surface]:
    """Load a grid spritesheet and return scaled frame surfaces."""
    if not os.path.exists(path):
        print(f"[warn] '{path}' not found – falling back to the two-image setup.")
        return []

    sheet = pygame.image.load(path).convert_alpha()
    sheet_w, sheet_h = sheet.get_size()
    frame_w = sheet_w // cols
    frame_h = sheet_h // rows
    frames: list[pygame.Surface] = []

    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            frames.append(pygame.transform.smoothscale(frame, (size, size)))

    return frames


def build_idle_playback_frames(idle_frames: list[pygame.Surface]) -> list[pygame.Surface]:
    """Build a ping-pong sequence so idle does not snap from last frame to first."""
    if len(idle_frames) <= 2:
        return idle_frames
    return idle_frames + idle_frames[-2:0:-1]


def sheet_frame_index(frame_number: int) -> int:
    """Convert a 1-based sheet frame number to a zero-based list index."""
    return frame_number - 1


def corner_pos(screen_w, screen_h, size, margin, corner, bottom_lift):
    """Return the (x, y) screen position for the window."""
    if corner == "bottom-right":
        return screen_w - size - margin, screen_h - size - margin - bottom_lift
    if corner == "bottom-left":
        return margin, screen_h - size - margin - bottom_lift
    if corner == "top-right":
        return screen_w - size - margin, margin
    return margin, margin  # top-left


def apply_windows_transparency(hwnd, win_x, win_y):
    """
    On Windows: make the pygame window truly transparent + always-on-top
    + click-through using the Win32 API via pywin32.
    """
    try:
        import win32api, win32con, win32gui
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_LAYERED
        ex_style |= win32con.WS_EX_TRANSPARENT   # click-through
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)

       
        win32gui.SetLayeredWindowAttributes(
            hwnd, win32api.RGB(255, 0, 255), 0, win32con.LWA_COLORKEY
        )
        # Always on top + reposition
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST,
            win_x, win_y,
            PNGTUBER_SIZE, PNGTUBER_SIZE,
            0
        )
        print("[info] Windows transparency + click-through applied.")
    except ImportError:
        print("[warn] pywin32 not found – install with: pip install pywin32")
        print("       Window will be on-top but not click-through.")
        # Fallback: at least keep it on top via ctypes
        import ctypes
        ctypes.windll.user32.SetWindowPos(
            hwnd, -1, win_x, win_y,
            PNGTUBER_SIZE, PNGTUBER_SIZE, 0x0040
        )
    except Exception as e:
        print(f"[warn] Could not apply Windows transparency: {e}")


def audio_thread_fn(audio_path: str, is_talking: threading.Event):
    """Play the MP3 and keep is_talking set for its duration."""
    try:
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        is_talking.set()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    except Exception as e:
        print(f"[error] Audio playback failed: {e}")
    finally:
        is_talking.clear()


def main():
    pygame.init()
    pygame.mixer.init()

    info     = pygame.display.Info()
    screen_w = info.current_w
    screen_h = info.current_h

    win_x, win_y = corner_pos(screen_w, screen_h,
                               PNGTUBER_SIZE, PNGTUBER_MARGIN, CORNER, BOTTOM_LIFT)

    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{win_x},{win_y}"

    screen = pygame.display.set_mode(
        (PNGTUBER_SIZE, PNGTUBER_SIZE),
        pygame.NOFRAME
    )
    pygame.display.set_caption("PNGtuber")
    if os.path.exists(ICON_PATH):
        icon = pygame.image.load(ICON_PATH).convert_alpha()
        pygame.display.set_icon(pygame.transform.smoothscale(icon, (32, 32)))

    hwnd = pygame.display.get_wm_info()["window"]
    apply_windows_transparency(hwnd, win_x, win_y)

    sheet_frames = load_spritesheet(
        SPRITESHEET_PATH,
        SPRITESHEET_COLS,
        SPRITESHEET_ROWS,
        PNGTUBER_SIZE,
    )
    if sheet_frames:
        idle_indices = [sheet_frame_index(frame_number) for frame_number in IDLE_FRAME_NUMBERS]
        active_index = sheet_frame_index(ACTIVE_FRAME_NUMBER)
        if any(index >= len(sheet_frames) for index in idle_indices) or active_index >= len(sheet_frames):
            raise IndexError(
                f"Spritesheet has {len(sheet_frames)} frames, but the configured indices "
                f"idle={IDLE_FRAME_NUMBERS} active={ACTIVE_FRAME_NUMBER} are out of range."
            )
        idle_frames = [sheet_frames[index] for index in idle_indices]
        frame_talk = sheet_frames[active_index]
    else:
        idle_frames = [load_png(resource_path("Media/Resting.png"), PNGTUBER_SIZE)]
        frame_talk = load_png(resource_path("Media/Talking.png"), PNGTUBER_SIZE)

    idle_playback_frames = build_idle_playback_frames(idle_frames)

    media_path = resource_path(MEDIA_FOLDER)
    audio_files = list_mp3_files(media_path)
    current_cliptypes = CLIPTYPE_LIST.copy()
    audio_ok = len(audio_files) > 0
    if not audio_ok:
        print(f"[warn] No MP3 files found in '{media_path}' – audio will be skipped.")
    audio_queue: list[str] = build_audio_cycle(audio_files) if audio_ok else []
    last_played_audio: str | None = None

    is_talking      = threading.Event()
    last_audio_time = -AUDIO_INTERVAL  

    CHROMA_KEY = (255, 0, 255)

    clock   = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_1:
                open_settings()

        if CLIPTYPE_LIST != current_cliptypes and len(CLIPTYPE_LIST) != 0:
            print(f"[info] Folder change detected, reloading audio files.") 
            current_cliptypes = CLIPTYPE_LIST.copy()
            audio_files = list_mp3_files(media_path)
            audio_ok = len(audio_files) > 0
            audio_queue = build_audio_cycle(audio_files) if audio_ok else []
            last_played_audio = None

        now = time.time()

        if audio_ok and not is_talking.is_set() \
                and (now - last_audio_time >= AUDIO_INTERVAL):
            last_audio_time = now
            if not audio_queue:
                audio_queue = build_audio_cycle(audio_files, last_played_audio)
            selected_audio = audio_queue.pop(0)
            last_played_audio = selected_audio
            threading.Thread(
                target=audio_thread_fn,
                args=(selected_audio, is_talking),
                daemon=True
            ).start()


        screen.fill(CHROMA_KEY)

        if is_talking.is_set():
            current_frame = frame_talk
        else:
            frame_idx = int(now * TALK_FPS) % len(idle_playback_frames)
            current_frame = idle_playback_frames[frame_idx]

        screen.blit(current_frame, (0, 0))
        pygame.display.update()
        clock.tick(60)



    pygame.mixer.music.stop()
    pygame.quit()
    sys.exit()

# Settings Menu
def open_settings():
    root = tk.Tk()
    root.title("Clip Types")
    root.geometry("200x270")
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    # Cliptype Toggles
    toggle_vars = {}
    for folder in ALL_CLIPTYPES:
        var = tk.BooleanVar(value=folder in CLIPTYPE_LIST)
        toggle_vars[folder] = var

        def make_toggle(f, v):
            def toggle():
                if v.get():
                    CLIPTYPE_LIST.add(f)
                else:
                    CLIPTYPE_LIST.discard(f)
                print(f"CLIPTYPE_LIST: {CLIPTYPE_LIST}")
            return toggle

        cb = tk.Checkbutton(
            root,
            text=folder,
            variable=var,
            command=make_toggle(folder, var)
        )
        cb.pack(anchor="w", padx=20, pady=4)

    # Audio Interval
    interval_frame = tk.Frame(root)
    interval_frame.pack(anchor="w", padx=20, pady=(8, 8))

    tk.Label(interval_frame, text="Audio Interval (s):").pack(side="left")

    interval_var = tk.StringVar(value=str(AUDIO_INTERVAL))
    interval_entry = tk.Entry(interval_frame, textvariable=interval_var, width=6)
    interval_entry.pack(side="left", padx=(6, 0))

    def on_interval_change(*args):
        global AUDIO_INTERVAL
        try:
            value = float(interval_var.get())
            if value >= 0:
                AUDIO_INTERVAL = value
                print(f"[info] AUDIO_INTERVAL set to {AUDIO_INTERVAL}s")
        # Ignores invalid inputs and uses the previous value
        except ValueError:
            pass
            print(f"[error] Invalid input inputted for AUDIO_INTERVAL")

    interval_var.trace_add("write", on_interval_change)

    root.mainloop()


if __name__ == "__main__":
    main()