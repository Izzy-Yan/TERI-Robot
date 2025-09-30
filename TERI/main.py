import sys
import time
import threading
import struct
import traceback
import logging
import pygame
import cv2
import numpy as np
import random
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('Teri')

# Import local modules
try:
    logger.info("Initializing robot modules...")
    from motor_control import init_motor_control, cleanup as motor_cleanup, move_forward, move_backward, turn_left, turn_right
    from audio_module import get_audio_stream, shutdown_audio_stream, porcupine, listen_for_command_fast
    import tts_module
    from commands import handle_command
    import face_module
    from temporal_memory import temporal_memory
    from shared_camera import init_shared_camera, capture_shared_frame, stop_shared_camera
    from place_recognition import place_recognizer
    from sleep_mode import sleep_mode
    logger.info("All modules imported successfully")
except ImportError as e:
    logger.critical(f"Failed to import required modules: {e}")
    sys.exit(1)

# Configuration Constants
DISPLAY_MODES = ["face", "video", "motor"]
DEFAULT_MODE = 0
FPS = 30

UI_MARGIN = 10
UI_FONT_SIZE = 36
STATUS_FONT_SIZE = 42
BUTTON_SIZE = 30

MOUTH_CHANGE_TIME = 0.15
TTS_STARTUP_DELAY = 0.1
SPEECH_RATE = 3.0

SLEEP_BRIGHTNESS_MULTIPLIER = 0.4
NORMAL_BRIGHTNESS_MULTIPLIER = 1.0

CLOSED_MOUTH_IMAGE = "/home/Izzy/TERI/TERI/closed.png"
OPEN_MOUTH_IMAGE = "/home/Izzy/TERI/TERI/open.png"

# Global State
class State:
    def __init__(self):
        self.display_mode = DEFAULT_MODE
        self.mouth_state = "closed"
        self.last_mouth_change = time.time()
        
        self.processing_command = False
        self.is_speaking = False
        self.is_listening = False
        self.is_thinking = False
        self.last_interaction = time.time()
        
        self.motion_controls = {
            "forward": None,
            "backward": None,
            "left": None,
            "right": None
        }
        
        self.last_recognition = None
        self.recognition_time = 0
        
        self.closed_mouth_img = None
        self.open_mouth_img = None
        self.closed_mouth_scaled = None
        self.open_mouth_scaled = None

        self.hold_direction = None
        self.last_move_times = {
            "forward": 0.0,
            "backward": 0.0,
            "left": 0.0,
            "right": 0.0
        }
        self.move_throttle = 0.12
        self.move_duration = 0.15
        
        self.sleep_brightness = SLEEP_BRIGHTNESS_MULTIPLIER
        self.normal_brightness = NORMAL_BRIGHTNESS_MULTIPLIER

state = State()

# Status Display Functions
def draw_status_header(window, width):
    """Draw status at the top of screen"""
    brightness = get_current_brightness()
    font = pygame.font.Font(None, STATUS_FONT_SIZE)
    
    status_text = None
    status_color = None
    
    if state.is_listening:
        status_text = "Listening..."
        status_color = (100, 200, 255)  # Blue
    elif state.is_thinking:
        status_text = "Thinking..."
        status_color = (255, 200, 100)  # Orange
    
    if status_text:
        # Apply brightness
        color = (
            int(status_color[0] * brightness),
            int(status_color[1] * brightness),
            int(status_color[2] * brightness)
        )
        
        text_surface = font.render(status_text, True, color)
        
        # Position at top center
        x = width // 2 - text_surface.get_width() // 2
        y = 30
        
        # Draw semi-transparent background
        bg_rect = pygame.Rect(x - 20, y - 10, text_surface.get_width() + 40, text_surface.get_height() + 20)
        bg_surface = pygame.Surface((bg_rect.width, bg_rect.height))
        bg_surface.fill((20, 20, 30))
        bg_surface.set_alpha(180)
        window.blit(bg_surface, bg_rect)
        
        window.blit(text_surface, (x, y))

def get_current_brightness():
    """Get current brightness multiplier based on sleep mode"""
    return state.sleep_brightness if sleep_mode.is_sleeping else state.normal_brightness

# Speech Synchronization
def speak_with_mouth_sync(text, pre_delay=None):
    """Speech with mouth animation"""
    if pre_delay is None:
        pre_delay = TTS_STARTUP_DELAY
    
    def speech_thread():
        try:
            tts_thread = threading.Thread(target=lambda: tts_module.speak(text))
            tts_thread.daemon = True
            tts_thread.start()
            
            time.sleep(pre_delay)
            state.is_speaking = True
            
            word_count = len(text.split())
            duration = max(0.8, (word_count / SPEECH_RATE))
            time.sleep(duration)
            
            state.is_speaking = False
            
        except Exception as e:
            logger.error(f"Error in speech synchronization: {e}")
            state.is_speaking = False
    
    thread = threading.Thread(target=speech_thread)
    thread.daemon = True
    thread.start()
    return thread

# Image Loading
def load_face_images():
    """Load and prepare the face images"""
    try:
        if not os.path.exists(CLOSED_MOUTH_IMAGE):
            logger.error(f"Closed mouth image not found: {CLOSED_MOUTH_IMAGE}")
            return False
        if not os.path.exists(OPEN_MOUTH_IMAGE):
            logger.error(f"Open mouth image not found: {OPEN_MOUTH_IMAGE}")
            return False
        
        state.closed_mouth_img = pygame.image.load(CLOSED_MOUTH_IMAGE)
        state.open_mouth_img = pygame.image.load(OPEN_MOUTH_IMAGE)
        
        logger.info("Face images loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load face images: {e}")
        return False

def scale_face_images(width, height):
    """Scale face images to fit the screen"""
    try:
        if state.closed_mouth_img is None or state.open_mouth_img is None:
            return False
        
        state.closed_mouth_scaled = pygame.transform.scale(state.closed_mouth_img, (width, height))
        state.open_mouth_scaled = pygame.transform.scale(state.open_mouth_img, (width, height))
        
        logger.info(f"Face images scaled to {width}x{height}")
        return True
    except Exception as e:
        logger.error(f"Failed to scale face images: {e}")
        return False

# Sleep Mode Functions
def apply_sleep_brightness(surface):
    """Apply sleep mode brightness to a surface"""
    if sleep_mode.is_sleeping:
        overlay = pygame.Surface(surface.get_size())
        overlay.fill((0, 0, 0))
        overlay.set_alpha(int(255 * (1.0 - state.sleep_brightness)))
        surface.blit(overlay, (0, 0))
    return surface

# UI Initialization
def initialize_ui():
    """Initialize pygame and UI elements"""
    logger.info("Initializing UI...")
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception as e:
        logger.warning(f"pygame.mixer.init() failed: {e}")

    window_info = pygame.display.Info()
    width, height = window_info.current_w, window_info.current_h
    
    try:
        window = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
        pygame.display.set_caption("Teri Robot Interface")
        pygame.mouse.set_visible(False)
        
        if not load_face_images():
            logger.warning("Failed to load face images")
        else:
            scale_face_images(width, height)
        
        exit_button = pygame.Rect(width - BUTTON_SIZE - UI_MARGIN, UI_MARGIN, BUTTON_SIZE, BUTTON_SIZE)
        mode_button = pygame.Rect(width - 2 * BUTTON_SIZE - 2 * UI_MARGIN, UI_MARGIN, BUTTON_SIZE, BUTTON_SIZE)
        
        control_size = 120
        padding = 20
        center_x = width // 2
        center_y = height // 2
        center_rect_x = center_x - control_size // 2

        state.motion_controls = {
            "forward": pygame.Rect(center_rect_x, center_y - control_size - padding, control_size, control_size),
            "backward": pygame.Rect(center_rect_x, center_y + padding, control_size, control_size),
            "left": pygame.Rect(center_rect_x - control_size - padding, center_y - control_size // 2, control_size, control_size),
            "right": pygame.Rect(center_rect_x + control_size + padding, center_y - control_size // 2, control_size, control_size)
        }
        
        logger.info(f"UI initialized at {width}x{height}")
        return window, exit_button, mode_button, width, height
    
    except Exception as e:
        logger.critical(f"Failed to initialize UI: {e}")
        pygame.quit()
        sys.exit(1)

# Animation Functions
def update_mouth_animation():
    """Update mouth animation states"""
    current_time = time.time()
    
    if state.is_speaking:
        if current_time - state.last_mouth_change > MOUTH_CHANGE_TIME:
            state.mouth_state = "closed" if state.mouth_state == "open" else "open"
            state.last_mouth_change = current_time
    elif state.mouth_state == "open":
        state.mouth_state = "closed"
        state.last_mouth_change = current_time

def draw_buttons(window, exit_button, mode_button):
    """Draw control buttons"""
    brightness = get_current_brightness()
    
    exit_color = (int(255 * brightness), 0, 0)
    mode_color = (0, 0, int(255 * brightness))
    line_color = (int(255 * brightness), int(255 * brightness), int(255 * brightness))
    
    pygame.draw.rect(window, exit_color, exit_button)
    pygame.draw.line(window, line_color, 
                   (exit_button.left + 5, exit_button.top + 5),
                   (exit_button.right - 5, exit_button.bottom - 5), 3)
    pygame.draw.line(window, line_color, 
                   (exit_button.right - 5, exit_button.top + 5),
                   (exit_button.left + 5, exit_button.bottom - 5), 3)
    
    pygame.draw.rect(window, mode_color, mode_button)
    pygame.draw.circle(window, line_color, 
                     (mode_button.centerx, mode_button.centery), 10, 2)

def draw_face_display(window, width, height):
    """Draw the face display"""
    if state.closed_mouth_scaled is None or state.open_mouth_scaled is None:
        window.fill((0, 0, 0))
        return
    
    if state.mouth_state == "open":
        face_surface = state.open_mouth_scaled.copy()
    else:
        face_surface = state.closed_mouth_scaled.copy()
    
    if sleep_mode.is_sleeping:
        face_surface = apply_sleep_brightness(face_surface)
    
    window.blit(face_surface, (0, 0))

def draw_video_display(window, width, height):
    """Draw camera feed"""
    frame = capture_shared_frame()
    if frame is not None:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (width, height))
        
        try:
            current_recognition = face_module.get_current_recognition()
        except Exception:
            current_recognition = {"name": None, "location": None, "timestamp": 0}
        
        if (current_recognition and current_recognition.get("name") and 
            current_recognition.get("location") and 
            time.time() - current_recognition.get("timestamp", 0) < 5):
            
            top, right, bottom, left = current_recognition["location"]
            scale_x = width / 640
            scale_y = height / 480
            
            cv2.rectangle(frame, 
                        (int(left * scale_x), int(top * scale_y)), 
                        (int(right * scale_x), int(bottom * scale_y)), 
                        (0, 255, 0), 2)
            cv2.putText(frame, 
                      current_recognition["name"], 
                      (int(left * scale_x), int(top * scale_y - 10)), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        pygame_frame = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
        
        if sleep_mode.is_sleeping:
            pygame_frame = apply_sleep_brightness(pygame_frame)
        
        window.blit(pygame_frame, (0, 0))

def draw_modern_motor_controls(window, width, height):
    """Draw motor control interface"""
    brightness = get_current_brightness()
    
    bg_color = (int(20 * brightness), int(20 * brightness), int(30 * brightness))
    window.fill(bg_color)
    
    font = pygame.font.Font(None, UI_FONT_SIZE)
    title_color = (int(220 * brightness), int(220 * brightness), int(240 * brightness))
    title = font.render("Movement Control", True, title_color)
    window.blit(title, (width // 2 - title.get_width() // 2, height // 8))
    
    control_colors = {
        "normal": (int(40 * brightness), int(42 * brightness), int(54 * brightness)),
        "hover": (int(80 * brightness), int(82 * brightness), int(94 * brightness)),
        "border": (int(100 * brightness), int(180 * brightness), int(220 * brightness)),
        "text": (int(220 * brightness), int(220 * brightness), int(240 * brightness))
    }
    
    mouse_pos = pygame.mouse.get_pos()
    
    for direction, rect in state.motion_controls.items():
        if rect.collidepoint(mouse_pos):
            color = control_colors["hover"]
            border_width = 3
        else:
            color = control_colors["normal"]
            border_width = 2
            
        pygame.draw.rect(window, control_colors["border"], rect, border_radius=15)
        inner_rect = pygame.Rect(rect.x + border_width, rect.y + border_width, 
                               rect.width - 2*border_width, rect.height - 2*border_width)
        pygame.draw.rect(window, color, inner_rect, border_radius=15)
        
        label = font.render(direction.capitalize(), True, control_colors["text"])
        window.blit(label, (rect.centerx - label.get_width() // 2, 
                          rect.centery + rect.height // 3))

def update_display(window, exit_button, mode_button, width, height):
    """Update the display"""
    window.fill((0, 0, 0))
    
    current_mode = DISPLAY_MODES[state.display_mode]
    
    if current_mode == "face":
        draw_face_display(window, width, height)
    elif current_mode == "video":
        draw_video_display(window, width, height)
    elif current_mode == "motor":
        draw_modern_motor_controls(window, width, height)
    
    draw_buttons(window, exit_button, mode_button)
    draw_status_header(window, width)  # Draw status at top
    
    pygame.display.flip()

# Audio Processing
def audio_processing_thread(audio_stream):
    """Audio processing thread - NO THROTTLING"""
    logger.info("Starting audio processing thread")
    
    while True:
        try:
            if state.processing_command:
                time.sleep(0.01)  # Minimal sleep when processing
                continue
                
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                logger.info("Wake word detected!")
                process_command_sequence()
                
        except Exception as e:
            logger.error(f"Error in audio processing: {e}")
            time.sleep(0.1)

def process_command_sequence():
    """Command processing with visual feedback"""
    try:
        state.processing_command = True
        state.is_listening = True  # Show "Listening..."
        
        speak_with_mouth_sync("Yes?")
        time.sleep(0.3)  # Brief pause
        
        command = listen_for_command_fast()
        
        state.is_listening = False  # Stop showing "Listening..."
        
        if command:
            logger.info(f"Command: {command}")
            state.is_thinking = True  # Show "Thinking..."
            
            handle_command(command, face_module)
            
            state.is_thinking = False  # Stop showing "Thinking..."
        else:
            logger.info("No command detected")
            speak_with_mouth_sync("I didn't catch that.")
        
        time.sleep(0.1)  # Minimal delay before next wake word
        
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        state.is_thinking = False
        state.is_listening = False
    finally:
        state.mouth_state = "closed"
        state.last_mouth_change = time.time()
        state.processing_command = False
        state.is_speaking = False

# Motor Commands
def send_move_command(direction, duration=None):
    """Non-blocking motor command"""
    def do_cmd():
        try:
            if direction == "forward":
                move_forward(duration if duration else 1)
            elif direction == "backward":
                move_backward(duration if duration else 1)
            elif direction == "left":
                turn_left()
            elif direction == "right":
                turn_right()
        except Exception as e:
            logger.error(f"Motor error ({direction}): {e}")

    threading.Thread(target=do_cmd, daemon=True).start()

# Event Handling
def handle_mouse_events(event, exit_button, mode_button):
    """Handle mouse events"""
    pos = pygame.mouse.get_pos()

    if event.type == pygame.MOUSEBUTTONDOWN and exit_button.collidepoint(pos):
        logger.info("Exit button clicked")
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and mode_button.collidepoint(pos):
        state.display_mode = (state.display_mode + 1) % len(DISPLAY_MODES)
        logger.info(f"Switched to {DISPLAY_MODES[state.display_mode]} mode")
        return False

    if DISPLAY_MODES[state.display_mode] == "motor":
        if event.type == pygame.MOUSEBUTTONDOWN:
            for direction, rect in state.motion_controls.items():
                if rect.collidepoint(pos):
                    state.hold_direction = direction
                    send_move_command(direction, duration=state.move_duration)
                    state.last_move_times[direction] = time.time()
                    return False

        if event.type == pygame.MOUSEBUTTONUP:
            if state.hold_direction is not None:
                state.hold_direction = None
            return False

    return False

def handle_keyboard_events(event):
    """Handle keyboard events"""
    if event.type != pygame.KEYDOWN and event.type != pygame.KEYUP:
        return False
        
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return True
        
    if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
        state.display_mode = (state.display_mode + 1) % len(DISPLAY_MODES)
        logger.info(f"Switched to {DISPLAY_MODES[state.display_mode]} mode")
    
    return False

def process_hold_controls():
    """Process continuous motor commands"""
    now = time.time()

    if state.hold_direction is not None:
        mouse_pressed = pygame.mouse.get_pressed()[0]
        if not mouse_pressed:
            state.hold_direction = None
        else:
            direction = state.hold_direction
            if now - state.last_move_times.get(direction, 0) >= state.move_throttle:
                send_move_command(direction, duration=state.move_duration)
                state.last_move_times[direction] = now

# Hardware Initialization
def initialize_hardware():
    """Initialize hardware"""
    logger.info("Initializing hardware...")
    
    try:
        init_motor_control()
        logger.info("Motor control initialized")
    except Exception as e:
        logger.error(f"Motor control failed: {e}")
    
    try:
        init_shared_camera()
        logger.info("Camera initialized")
    except Exception as e:
        logger.error(f"Camera failed: {e}")
    
    try:
        place_recognizer.load_places()
        logger.info("Place recognition initialized")
    except Exception as e:
        logger.error(f"Place recognition failed: {e}")

    try:
        temporal_memory.clear_expired()
        logger.info("Temporal memory cleaned")
    except Exception as e:
        logger.error(f"Temporal memory failed: {e}")

# Main Function
def main():
    """Main function"""
    initialize_hardware()
    window, exit_button, mode_button, width, height = initialize_ui()
    
    try:
        audio_stream = get_audio_stream()
        logger.info("Audio stream started")
        
        audio_thread = threading.Thread(target=audio_processing_thread, args=(audio_stream,))
        audio_thread.daemon = True
        audio_thread.start()
        
        speak_with_mouth_sync("Teri online.")
        
        logger.info("Entering main loop")
        clock = pygame.time.Clock()
        
        while True:
            should_exit = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    should_exit = True
                
                should_exit = should_exit or handle_mouse_events(event, exit_button, mode_button)
                should_exit = should_exit or handle_keyboard_events(event)
            
            if should_exit:
                break
            
            update_mouth_animation()
            process_hold_controls()
            update_display(window, exit_button, mode_button, width, height)
            
            clock.tick(FPS)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()
    finally:
        logger.info("Shutting down...")
        if 'audio_stream' in locals():
            shutdown_audio_stream(audio_stream)
        try:
            motor_cleanup()
        except Exception as e:
            logger.error(f"Motor cleanup error: {e}")
        try:
            stop_shared_camera()
        except Exception as e:
            logger.error(f"Camera cleanup error: {e}")
        pygame.quit()
        sys.exit(0)

if __name__ == "__main__":
    logger.info("Starting Teri robot system")
    main()
    logger.info("System terminated normally")