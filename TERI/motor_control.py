# motor_control.py
import sys
import time
import lgpio
from time import sleep

GPIOchip = 0  # Use the default GPIO chip

# Group A Motor pins (Left side) - VERIFIED WORKING
ENA_A = 12    # Enable A
LN1_A = 17    # IN1
LN2_A = 5     # IN2
LN3_A = 27    # IN3
LN4_A = 6     # IN4
ENB_A = 13    # Enable B

# Group B Motor pins (Right side) - CRITICAL FIX FROM TEST CODE
ENA_B = 18    # Enable A
LN1_B = 23    # IN1
LN2_B = 24    # IN2
LN3_B = 20    # IN3
LN4_B = 21    # IN4
ENB_B = 19    # Enable B

motor_pins = [
    ENA_A, LN1_A, LN2_A, LN3_A, LN4_A, ENB_A,
    ENA_B, LN1_B, LN2_B, LN3_B, LN4_B, ENB_B
]

handle = None

def init_motor_control():
    """Initialize the LGPIO chip and claim motor pins."""
    global handle
    try:
        handle = lgpio.gpiochip_open(GPIOchip)
        print("GPIO chip opened successfully.")
    except Exception as e:
        print(f"Error opening GPIO chip: {e}")
        sys.exit(1)
        
    for pin in motor_pins:
        ret = lgpio.gpio_claim_output(handle, pin)
        if ret < 0:
            print(f"Error claiming pin {pin}")
        sleep(0.05)
    return handle

def stop_motors():
    """Disable both motor groups."""
    global handle
    lgpio.gpio_write(handle, ENA_A, 0)
    lgpio.gpio_write(handle, ENA_B, 0)

def set_direction_forward():
    """Set direction pins for forward movement (TESTED)."""
    # Left side (Group A)
    lgpio.gpio_write(handle, LN1_A, 1)
    lgpio.gpio_write(handle, LN2_A, 0)
    lgpio.gpio_write(handle, LN3_A, 1)
    lgpio.gpio_write(handle, LN4_A, 0)
    
    # Right side (Group B) - FIXED FROM TEST CODE
    lgpio.gpio_write(handle, LN1_B, 1)
    lgpio.gpio_write(handle, LN2_B, 0)
    lgpio.gpio_write(handle, LN3_B, 1)
    lgpio.gpio_write(handle, LN4_B, 0)

def set_direction_backward():
    """Set direction pins for backward movement (TESTED)."""
    # Left side (Group A)
    lgpio.gpio_write(handle, LN1_A, 0)
    lgpio.gpio_write(handle, LN2_A, 1)
    lgpio.gpio_write(handle, LN3_A, 0)
    lgpio.gpio_write(handle, LN4_A, 1)
    
    # Right side (Group B) - FIXED FROM TEST CODE
    lgpio.gpio_write(handle, LN1_B, 0)
    lgpio.gpio_write(handle, LN2_B, 1)
    lgpio.gpio_write(handle, LN3_B, 0)
    lgpio.gpio_write(handle, LN4_B, 1)

def move_forward(duration):
    print(f"[Motor] Moving forward for {duration} sec.")
    global handle
    set_direction_forward()
    lgpio.gpio_write(handle, ENA_A, 1)
    lgpio.gpio_write(handle, ENA_B, 1)
    sleep(duration)
    stop_motors()

def move_backward(duration):
    print(f"[Motor] Moving backward for {duration} sec.")
    global handle
    set_direction_backward()
    lgpio.gpio_write(handle, ENA_A, 1)
    lgpio.gpio_write(handle, ENA_B, 1)
    sleep(duration)
    stop_motors()

def turn_left():
    print("[Motor] Turning left.")
    # Stop right motors (Group B), enable left motors (Group A)
    lgpio.gpio_write(handle, ENA_B, 0)
    lgpio.gpio_write(handle, ENA_A, 1)
    set_direction_forward()
    sleep(0.5)
    stop_motors()

def turn_right():
    print("[Motor] Turning right.")
    # Stop left motors (Group A), enable right motors (Group B)
    lgpio.gpio_write(handle, ENA_A, 0)
    lgpio.gpio_write(handle, ENA_B, 1)
    set_direction_forward()
    sleep(0.5)
    stop_motors()

def cleanup():
    """Release GPIO resources."""
    global handle
    if handle:
        lgpio.gpiochip_close(handle)
        print("GPIO released.")
