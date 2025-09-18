# common.py - Compatibility wrapper for shared camera functionality
"""
This module provides backward compatibility for modules that still import from common.py
All functionality has been moved to shared_camera.py
"""

from shared_camera import init_shared_camera, capture_shared_frame, stop_shared_camera

# Re-export functions for backward compatibility
__all__ = ['init_shared_camera', 'capture_shared_frame', 'stop_shared_camera']