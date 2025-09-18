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

# Import local modules (with error handling)
try:
    logger.info("Initializing robot modules...")
    from motor_control import init_motor_control, cleanup as motor_cleanup, move_forward, move_backward, turn_left, turn_right
    from audio_module import get_audio_stream, shutdown_audio_stream, porcupine, listen_for_command
    import tts_module
    from commands import handle_command
    import face_module
    from temporal_memory import temporal_memory
    # FIX: Import from shared_camera.py instead of common
    from shared_camera import init_shared_camera, capture_shared_frame, stop_shared_camera
    from place_recognition import place_recognizer
    logger.info("All modules imported successfully")
except ImportError as e:
    logger.critical(f"Failed to import required modules: {e}")
    sys.exit(1)

# ============= Configuration Constants =============
# Display modes and settings
DISPLAY_MODES = ["face", "video", "motor"]
DEFAULT_MODE = 0  # Start with face mode
FPS = 30  # Target frames per second for display

# UI Settings
BUTTON_SIZE = 30
UI_MARGIN = 10
UI_FONT_SIZE = 36
ICON_SIZE = 24
HIGHLIGHT_COLOR = (100, 200, 255)  # Bright cyan for highlights

# Interaction settings
WAKE_WORD_TIMEOUT = 10  # Seconds to wait after wake word before timing out
INTERACTION_COOLDOWN = 0.5  # Seconds to wait between interactions

# Recognition confidence settings
FACE_RECOGNITION_THRESHOLD = 0.5
SPEECH_CONFIDENCE_THRESHOLD = 0.7

# Animation settings
MOUTH_CHANGE_TIME = 0.15  # Faster mouth animation for talking

# Speech timing settings
TTS_STARTUP_DELAY = 0.2  # Seconds to wait before starting mouth animation
SPEECH_RATE = 2.5  # Words per second for your TTS system

# Image paths
CLOSED_MOUTH_IMAGE = "/home/Izzy/TERI/closed.png"
OPEN_MOUTH_IMAGE = "/home/Izzy/TERI/open.png"

# ============= Global State =============
class State:
    """Container for global state variables to avoid cluttering global namespace"""
    def __init__(self):
        # Display state
        self.display_mode = DEFAULT_MODE
        self.mouth_state = "closed"
        self.last_mouth_change = time.time()
        
        # Interaction state
        self.processing_command = False
        self.is_speaking = False  # Flag to track when TTS is active
        self.last_interaction = time.time()
        
        # Motion UI elements
        self.motion_controls = {
            "forward": None,
            "backward": None,
            "left": None,
            "right": None
        }
        
        # Recognition state
        self.last_recognition = None
        self.recognition_time = 0
        
        # Face images (will be loaded during initialization)
        self.closed_mouth_img = None
        self.open_mouth_img = None
        self.closed_mouth_scaled = None
        self.open_mouth_scaled = None

        # Hold / continuous movement support
        self.hold_direction = None  # "forward"|"backward"|"left"|"right"|None
        self.last_move_times = {
            "forward": 0.0,
            "backward": 0.0,
            "left": 0.0,
            "right": 0.0
        }
        # How often to send repeated move commands while held (seconds)
        self.move_throttle = 0.12
        # How long each repeated movement command should ask the motors to move (seconds)
        # (keeps each small so repeated calls feel smooth)
        self.move_duration = 0.15

# Initialize state object
state = State()

# ============= Speech Synchronization Functions =============
def speak_with_mouth_sync(text, pre_delay=None):
    """Speak text with properly synchronized mouth animation"""
    if pre_delay is None:
        pre_delay = TTS_STARTUP_DELAY
    
    def speech_thread():
        try:
            # Start TTS in background
            tts_thread = threading.Thread(target=lambda: tts_module.speak(text))
            tts_thread.daemon = True
            tts_thread.start()
            
            # Wait for TTS to actually start producing audio
            time.sleep(pre_delay)
            
            # Start mouth animation
            state.is_speaking = True
            logger.info(f"Started mouth animation for: '{text}'")
            
            # Estimate speech duration and wait
            word_count = len(text.split())
            duration = max(1.0, (word_count / SPEECH_RATE))  # Minimum 1 second
            logger.info(f"Estimated speech duration: {duration:.1f}s for {word_count} words")
            time.sleep(duration)
            
            # Stop mouth animation
            state.is_speaking = False
            logger.info("Stopped mouth animation")
            
        except Exception as e:
            logger.error(f"Error in speech synchronization: {e}")
            state.is_speaking = False
    
    thread = threading.Thread(target=speech_thread)
    thread.daemon = True
    thread.start()
    
    # Return the thread so caller can wait for it if needed
    return thread

# ============= Image Loading Functions =============
def load_face_images():
    """Load and prepare the face images"""
    try:
        # Check if image files exist
        if not os.path.exists(CLOSED_MOUTH_IMAGE):
            logger.error(f"Closed mouth image not found: {CLOSED_MOUTH_IMAGE}")
            return False
        if not os.path.exists(OPEN_MOUTH_IMAGE):
            logger.error(f"Open mouth image not found: {OPEN_MOUTH_IMAGE}")
            return False
        
        # Load images
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
        
        # Scale images to full screen
        state.closed_mouth_scaled = pygame.transform.scale(state.closed_mouth_img, (width, height))
        state.open_mouth_scaled = pygame.transform.scale(state.open_mouth_img, (width, height))
        
        logger.info(f"Face images scaled to {width}x{height}")
        return True
    except Exception as e:
        logger.error(f"Failed to scale face images: {e}")
        return False

# ============= UI Initialization =============
def initialize_ui():
    """Initialize pygame and UI elements"""
    logger.info("Initializing UI...")
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception as e:
        logger.warning(f"pygame.mixer.init() failed: {e} (continuing without sound mixer)")

    window_info = pygame.display.Info()
    width, height = window_info.current_w, window_info.current_h
    
    try:
        window = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
        pygame.display.set_caption("Teri Robot Interface")
        
        # Load face images
        if not load_face_images():
            logger.warning("Failed to load face images, face mode will show placeholder")
        else:
            # Scale images to screen size
            scale_face_images(width, height)
        
        # Create buttons
        exit_button = pygame.Rect(
            width - BUTTON_SIZE - UI_MARGIN, 
            UI_MARGIN, 
            BUTTON_SIZE, 
            BUTTON_SIZE
        )
        
        mode_button = pygame.Rect(
            width - 2 * BUTTON_SIZE - 2 * UI_MARGIN, 
            UI_MARGIN, 
            BUTTON_SIZE, 
            BUTTON_SIZE
        )
        
        # Initialize modern motion control areas (in motor mode)
        control_size = 120
        padding = 20
        center_x = width // 2
        center_y = height // 2

        # Compute the centered X for forward/back buttons
        center_rect_x = center_x - control_size // 2

        forward_rect = pygame.Rect(
            center_rect_x,
            center_y - control_size - padding,
            control_size,
            control_size
        )

        backward_rect = pygame.Rect(
            center_rect_x,
            center_y + padding,
            control_size,
            control_size
        )

        # Left is exactly one control-size to the left of the center_rect_x
        left_rect = pygame.Rect(
            center_rect_x - control_size - padding,
            center_y - control_size // 2,
            control_size,
            control_size
        )

        # Right is exactly one control-size to the right of the center_rect_x
        right_rect = pygame.Rect(
            center_rect_x + control_size + padding,
            center_y - control_size // 2,
            control_size,
            control_size
        )
        
        state.motion_controls = {
            "forward": forward_rect,
            "backward": backward_rect,
            "left": left_rect,
            "right": right_rect
        }
        
        logger.info(f"UI initialized at {width}x{height}")
        return window, exit_button, mode_button, width, height
    
    except Exception as e:
        logger.critical(f"Failed to initialize UI: {e}")
        pygame.quit()
        sys.exit(1)

# ============= Core Animation and Display Functions =============
def update_mouth_animation():
    """Update mouth animation states based on speaking status"""
    current_time = time.time()
    
    # Animate mouth while speaking (TTS is active)
    if state.is_speaking:
        # Animate mouth while speaking (open/close every MOUTH_CHANGE_TIME seconds)
        if current_time - state.last_mouth_change > MOUTH_CHANGE_TIME:
            state.mouth_state = "closed" if state.mouth_state == "open" else "open"
            state.last_mouth_change = current_time
    # Auto-close mouth if not speaking
    elif state.mouth_state == "open":
        state.mouth_state = "closed"
        state.last_mouth_change = current_time

def draw_buttons(window, exit_button, mode_button):
    """Draw control buttons on screen"""
    # Exit button (red X)
    pygame.draw.rect(window, (255, 0, 0), exit_button)
    pygame.draw.line(window, (255, 255, 255), 
                   (exit_button.left + 5, exit_button.top + 5),
                   (exit_button.right - 5, exit_button.bottom - 5), 3)
    pygame.draw.line(window, (255, 255, 255), 
                   (exit_button.right - 5, exit_button.top + 5),
                   (exit_button.left + 5, exit_button.bottom - 5), 3)
    
    # Mode button (circular arrow)
    pygame.draw.rect(window, (0, 0, 255), mode_button)
    pygame.draw.circle(window, (255, 255, 255), 
                     (mode_button.centerx, mode_button.centery), 
                     10, 2)
    # Draw arrow part of the mode toggle
    pygame.draw.line(window, (255, 255, 255),
                   (mode_button.centerx, mode_button.centery - 5),
                   (mode_button.centerx + 5, mode_button.centery), 2)
    pygame.draw.line(window, (255, 255, 255),
                   (mode_button.centerx + 5, mode_button.centery),
                   (mode_button.centerx, mode_button.centery + 5), 2)

def draw_face_display(window, width, height):
    """Draw the face display using images"""
    # Check if images are loaded
    if state.closed_mouth_scaled is None or state.open_mouth_scaled is None:
        # Show placeholder if images not loaded
        window.fill((0, 0, 0))
        font = pygame.font.Font(None, UI_FONT_SIZE)
        text = font.render("Face images not loaded", True, (255, 255, 255))
        window.blit(text, (width // 2 - text.get_width() // 2, height // 2))
        return
    
    # Display the appropriate image based on mouth state
    if state.mouth_state == "open":
        window.blit(state.open_mouth_scaled, (0, 0))
    else:
        window.blit(state.closed_mouth_scaled, (0, 0))

def draw_video_display(window, width, height):
    """Draw the camera video feed display"""
    frame = capture_shared_frame()
    if frame is not None:
        # Convert frame to pygame surface and display
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (width, height))
        
        # Add face recognition highlights if available
        try:
            current_recognition = face_module.get_current_recognition()
        except Exception:
            current_recognition = {"name": None, "location": None, "timestamp": 0}
        if (current_recognition and current_recognition.get("name") and 
            current_recognition.get("location") and 
            time.time() - current_recognition.get("timestamp", 0) < 5):
            
            # Scale face location to current display size
            top, right, bottom, left = current_recognition["location"]
            scale_x = width / 640
            scale_y = height / 480
            
            # Draw rectangle and name
            cv2.rectangle(frame, 
                        (int(left * scale_x), int(top * scale_y)), 
                        (int(right * scale_x), int(bottom * scale_y)), 
                        (0, 255, 0), 2)
            cv2.putText(frame, 
                      current_recognition["name"], 
                      (int(left * scale_x), int(top * scale_y - 10)), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        # Convert to pygame surface
        pygame_frame = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
        window.blit(pygame_frame, (0, 0))
    else:
        # Show "No Camera Feed" message
        font = pygame.font.Font(None, UI_FONT_SIZE)
        text = font.render("No Camera Feed Available", True, (255, 0, 0))
        window.blit(text, (width // 2 - text.get_width() // 2, height // 2))

def draw_modern_motor_controls(window, width, height):
    """Draw a modern motor control interface"""
    # Fill with dark background
    window.fill((20, 20, 30))
    
    # Add title
    font = pygame.font.Font(None, UI_FONT_SIZE)
    title = font.render("Movement Control", True, (220, 220, 240))
    window.blit(title, (width // 2 - title.get_width() // 2, height // 8))
    
    # Draw modern control buttons
    control_colors = {
        "normal": (40, 42, 54),
        "hover": (80, 82, 94),
        "border": (100, 180, 220),
        "text": (220, 220, 240)
    }
    
    # Get mouse position for hover effects
    mouse_pos = pygame.mouse.get_pos()
    
    # Draw each control with hover effect and rounded corners
    for direction, rect in state.motion_controls.items():
        # Determine button color (hover effect)
        if rect.collidepoint(mouse_pos):
            color = control_colors["hover"]
            border_width = 3
        else:
            color = control_colors["normal"]
            border_width = 2
            
        # Draw button with border
        pygame.draw.rect(window, control_colors["border"], rect, border_radius=15)
        inner_rect = pygame.Rect(rect.x + border_width, rect.y + border_width, 
                               rect.width - 2*border_width, rect.height - 2*border_width)
        pygame.draw.rect(window, color, inner_rect, border_radius=15)
        
        # Direction label
        label = font.render(direction.capitalize(), True, control_colors["text"])
        window.blit(label, (rect.centerx - label.get_width() // 2, 
                          rect.centery + rect.height // 3))
        
        # Draw directional arrows
        arrow_color = control_colors["text"]
        
        if direction == "forward":
            points = [
                (rect.centerx, rect.centery - rect.height // 4),
                (rect.centerx - rect.width // 5, rect.centery),
                (rect.centerx + rect.width // 5, rect.centery)
            ]
            pygame.draw.polygon(window, arrow_color, points)
        elif direction == "backward":
            points = [
                (rect.centerx, rect.centery + rect.height // 4 - 10),
                (rect.centerx - rect.width // 5, rect.centery - 10),
                (rect.centerx + rect.width // 5, rect.centery - 10)
            ]
            pygame.draw.polygon(window, arrow_color, points)
        elif direction == "left":
            points = [
                (rect.centerx - rect.width // 4, rect.centery),
                (rect.centerx, rect.centery - rect.height // 5),
                (rect.centerx, rect.centery + rect.height // 5)
            ]
            pygame.draw.polygon(window, arrow_color, points)
        elif direction == "right":
            points = [
                (rect.centerx + rect.width // 4, rect.centery),
                (rect.centerx, rect.centery - rect.height // 5),
                (rect.centerx, rect.centery + rect.height // 5)
            ]
            pygame.draw.polygon(window, arrow_color, points)

def update_display(window, exit_button, mode_button, width, height):
    """Update the display based on current mode"""
    # Clear the screen
    window.fill((0, 0, 0))
    
    # Update display based on current mode
    current_mode = DISPLAY_MODES[state.display_mode]
    
    if current_mode == "face":
        draw_face_display(window, width, height)
    elif current_mode == "video":
        draw_video_display(window, width, height)
    elif current_mode == "motor":
        draw_modern_motor_controls(window, width, height)
    
    # Always draw control buttons on top
    draw_buttons(window, exit_button, mode_button)
    
    # Update the display
    pygame.display.flip()

# ============= Audio Processing =============
def audio_processing_thread(audio_stream):
    """Background thread for audio processing and wake word detection"""
    logger.info("Starting audio processing thread")
    
    while True:
        try:
            # Skip if currently processing a command
            if state.processing_command:
                time.sleep(0.1)
                continue
                
            # Read audio data
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            # Process for wake word detection
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                logger.info("Wake word detected!")
                
                # Process command sequence
                process_command_sequence()
                
        except Exception as e:
            logger.error(f"Error in audio processing: {e}")
            time.sleep(1)  # Add delay to avoid tight error loops

def process_command_sequence():
    """Handle the full command processing sequence with improved speech timing"""
    try:
        # Mark as processing command to prevent overlapping audio operations
        state.processing_command = True
        
        # Speak confirmation with proper timing
        speech_thread = speak_with_mouth_sync("Yes?")
        
        # Wait for the confirmation to complete before listening
        speech_thread.join()
        
        # Wait for command
        command = listen_for_command()
        if command:
            logger.info(f"Command detected: {command}")
            # Handle command - commands.py should handle responses internally
            handle_command(command, face_module)
        else:
            logger.info("No command detected")
            
        # Small delay before returning to listening mode
        time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error processing command: {e}")
    finally:
        # Return to default state
        state.mouth_state = "closed"
        state.last_mouth_change = time.time()
        state.processing_command = False
        state.is_speaking = False

# ============= Motor Command Helper (non-blocking & robust) =============
def send_move_command(direction, duration=None):
    """Call motor control functions in a background thread to avoid blocking UI."""
    def do_cmd():
        try:
            if direction == "forward":
                if duration is not None:
                    try:
                        move_forward(duration)
                    except TypeError:
                        try:
                            move_forward()
                        except Exception as e:
                            logger.error(f"move_forward() failed: {e}")
                else:
                    try:
                        move_forward(1)  # Default 1 second
                    except Exception as e:
                        logger.error(f"move_forward() failed: {e}")
            elif direction == "backward":
                if duration is not None:
                    try:
                        move_backward(duration)
                    except TypeError:
                        try:
                            move_backward()
                        except Exception as e:
                            logger.error(f"move_backward() failed: {e}")
                else:
                    try:
                        move_backward(1)  # Default 1 second
                    except Exception as e:
                        logger.error(f"move_backward() failed: {e}")
            elif direction == "left":
                try:
                    turn_left()
                except Exception as e:
                    logger.error(f"turn_left() failed: {e}")
            elif direction == "right":
                try:
                    turn_right()
                except Exception as e:
                    logger.error(f"turn_right() failed: {e}")
        except Exception as e:
            logger.error(f"Motor command error ({direction}): {e}")

    threading.Thread(target=do_cmd, daemon=True).start()

# ============= Event Handling =============
def handle_mouse_events(event, exit_button, mode_button):
    """Handle mouse events including press-and-hold for motor controls."""
    pos = pygame.mouse.get_pos()

    # Exit button (mouse down)
    if event.type == pygame.MOUSEBUTTONDOWN and exit_button.collidepoint(pos):
        logger.info("Exit button clicked")
        return True

    # Mode switch button (mouse down)
    if event.type == pygame.MOUSEBUTTONDOWN and mode_button.collidepoint(pos):
        state.display_mode = (state.display_mode + 1) % len(DISPLAY_MODES)
        logger.info(f"Switched to {DISPLAY_MODES[state.display_mode]} mode")
        return False

    # Motor controls: respond to MOUSEBUTTONDOWN to begin hold, and MOUSEBUTTONUP to stop hold
    if DISPLAY_MODES[state.display_mode] == "motor":
        # start hold
        if event.type == pygame.MOUSEBUTTONDOWN:
            for direction, rect in state.motion_controls.items():
                if rect.collidepoint(pos):
                    logger.info(f"{direction.capitalize()} button pressed (start hold)")
                    state.hold_direction = direction
                    # send an immediate movement tick
                    send_move_command(direction, duration=state.move_duration)
                    state.last_move_times[direction] = time.time()
                    return False

        # stop hold
        if event.type == pygame.MOUSEBUTTONUP:
            # Clear hold direction when any mouse button released
            if state.hold_direction is not None:
                logger.info(f"{state.hold_direction.capitalize()} button released (stop hold)")
                state.hold_direction = None
            return False

    return False

def handle_keyboard_events(event):
    """Handle keyboard events"""
    if event.type != pygame.KEYDOWN and event.type != pygame.KEYUP:
        return False
        
    # Exit on Escape (KEYDOWN)
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return True
        
    # Mode switching with M key
    if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
        state.display_mode = (state.display_mode + 1) % len(DISPLAY_MODES)
        logger.info(f"Switched to {DISPLAY_MODES[state.display_mode]} mode (keyboard)")
        
    # Motor control via keyboard (when in motor mode)
    # On KEYDOWN send an immediate tick; continuous hold handled in process_hold_controls()
    if DISPLAY_MODES[state.display_mode] == "motor" and event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_UP, pygame.K_w):
            send_move_command("forward", duration=state.move_duration)
            state.last_move_times["forward"] = time.time()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            send_move_command("backward", duration=state.move_duration)
            state.last_move_times["backward"] = time.time()
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            send_move_command("left")
            state.last_move_times["left"] = time.time()
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            send_move_command("right")
            state.last_move_times["right"] = time.time()
    
    return False

def process_hold_controls():
    """Called each frame to send repeated motor commands while a control is held."""
    now = time.time()

    # Mouse-hold driven repeated commands
    if state.hold_direction is not None:
        mouse_pressed = pygame.mouse.get_pressed()[0]  # left button
        # If left mouse button is not currently pressed, clear the hold flag
        if not mouse_pressed:
            state.hold_direction = None
        else:
            direction = state.hold_direction
            if now - state.last_move_times.get(direction, 0) >= state.move_throttle:
                send_move_command(direction, duration=state.move_duration)
                state.last_move_times[direction] = now

    # Keyboard-hold driven repeated commands when in motor mode
    if DISPLAY_MODES[state.display_mode] == "motor":
        keys = pygame.key.get_pressed()
        # mapping keys to directions
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            if now - state.last_move_times["forward"] >= state.move_throttle:
                send_move_command("forward", duration=state.move_duration)
                state.last_move_times["forward"] = now
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            if now - state.last_move_times["backward"] >= state.move_throttle:
                send_move_command("backward", duration=state.move_duration)
                state.last_move_times["backward"] = now
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            if now - state.last_move_times["left"] >= state.move_throttle:
                send_move_command("left")
                state.last_move_times["left"] = now
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            if now - state.last_move_times["right"] >= state.move_throttle:
                send_move_command("right")
                state.last_move_times["right"] = now

# ============= Main Functions =============
def initialize_hardware():
    """Initialize all hardware components"""
    logger.info("Initializing hardware components...")
    
    try:
        init_motor_control()
        logger.info("Motor control initialized")
    except Exception as e:
        logger.error(f"Failed to initialize motor control: {e}")
    
    try:
        init_shared_camera()
        logger.info("Camera initialized")
    except Exception as e:
        logger.error(f"Failed to initialize camera: {e}")
    
    try:
        place_recognizer.load_places()
        logger.info("Place recognition initialized")
    except Exception as e:
        logger.error(f"Failed to initialize place recognition: {e}")

    # Clean expired temporal events
    try:
        temporal_memory.clear_expired()
        logger.info("Temporal memory cleaned")
    except Exception as e:
        logger.error(f"Failed to clean temporal memory: {e}")

def main():
    """Main function"""
    # Initialize hardware components first
    initialize_hardware()
    
    # Initialize UI
    window, exit_button, mode_button, width, height = initialize_ui()
    
    try:
        # Start audio processing
        audio_stream = get_audio_stream()
        logger.info("Audio stream started")
        
        # Start audio processing in a separate thread
        audio_thread = threading.Thread(target=audio_processing_thread, args=(audio_stream,))
        audio_thread.daemon = True
        audio_thread.start()
        
        # Startup announcement with improved mouth animation
        startup_thread = speak_with_mouth_sync("Teri is online and ready.")
        startup_thread.join()  # Wait for startup message to complete
        
        # Main event loop
        logger.info("Entering main loop")
        clock = pygame.time.Clock()
        
        while True:
            # Process events
            should_exit = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    should_exit = True
                
                # Handle mouse and keyboard events
                should_exit = should_exit or handle_mouse_events(event, exit_button, mode_button)
                should_exit = should_exit or handle_keyboard_events(event)
            
            if should_exit:
                break
            
            # Update mouth animation
            update_mouth_animation()

            # Process held controls (mouse or keyboard) - call every frame
            process_hold_controls()
            
            # Update the display
            update_display(window, exit_button, mode_button, width, height)
            
            # Cap the frame rate
            clock.tick(FPS)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()
    finally:
        # Clean up resources
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