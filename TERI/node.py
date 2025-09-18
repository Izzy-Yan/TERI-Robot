import subprocess
import cv2
import numpy as np

# Build the libcamera-vid command.
# Note: --nopreview ensures that no preview window is created,
# and all encoded MJPEG data is sent to stdout.
cmd = [
    "libcamera-vid",
    "-t", "0",             # Run indefinitely
    "--nopreview",         # Disable preview to send data to stdout
    "-o", "-",             # Output to stdout
    "--codec", "mjpeg",    # Use MJPEG encoding
    "--width", "640",      
    "--height", "480",
    "--framerate", "30"
]

# Start the libcamera-vid process.
# stderr is silenced to avoid mixing logs with the video stream.
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

# Persistent buffer for accumulating the MJPEG data.
buffer = bytearray()

def read_frame():
    """
    Reads from the MJPEG stream until a complete JPEG frame (ending with 0xFFD9) is found.
    Once found, decodes the JPEG image using OpenCV.
    """
    global buffer
    while True:
        # Look for the JPEG End Of Image (EOI) marker in the buffer.
        pos = buffer.find(b'\xff\xd9')
        if pos != -1:
            # We found a complete JPEG frame.
            frame_data = buffer[:pos+2]
            # Remove the extracted frame from the buffer.
            buffer = buffer[pos+2:]
            # Decode the JPEG image into an OpenCV BGR image.
            frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            return frame

        # Read more data if we haven't found a complete frame.
        chunk = proc.stdout.read(1024)
        if not chunk:
            return None
        buffer.extend(chunk)

# Main loop: Read frames and display them.
while True:
    frame = read_frame()
    if frame is None:
        print("Failed to decode frame.")
        break

    cv2.imshow("Camera via libcamera", frame)
    if cv2.waitKey(1) == ord("q"):
        break

proc.terminate()
cv2.destroyAllWindows()
