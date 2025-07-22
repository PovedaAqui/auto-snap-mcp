"""
Screenshot capture functionality for Linux systems.
Uses pyscreenshot for cross-platform screenshot capability.
"""

import os
import subprocess
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pyscreenshot as ImageGrab
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class WindowCapture:
    """Handles window enumeration and screenshot capture on Linux."""
    
    def __init__(self):
        self.display = os.environ.get('DISPLAY', ':0')
        
    def list_windows(self) -> List[Dict[str, str]]:
        """
        List all available windows using wmctrl command.
        Returns list of window info dictionaries.
        """
        try:
            # Use wmctrl to list windows
            result = subprocess.run(
                ['wmctrl', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            
            windows = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        window_id = parts[0]
                        desktop = parts[1]
                        machine = parts[2]
                        title = parts[3]
                        
                        windows.append({
                            'id': window_id,
                            'title': title,
                            'desktop': desktop,
                            'machine': machine
                        })
            
            return windows
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list windows with wmctrl: {e}")
            return []
        except FileNotFoundError:
            logger.error("wmctrl not found. Please install: sudo apt-get install wmctrl")
            return []
    
    def get_window_geometry(self, window_id: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Get window geometry (x, y, width, height) for a window ID.
        """
        try:
            result = subprocess.run(
                ['wmctrl', '-G'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line.startswith(window_id):
                    parts = line.split()
                    if len(parts) >= 7:
                        x = int(parts[2])
                        y = int(parts[3])
                        width = int(parts[4])
                        height = int(parts[5])
                        return (x, y, width, height)
            
            return None
            
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get window geometry: {e}")
            return None
    
    def focus_window(self, window_id: str) -> bool:
        """
        Focus a window by its ID.
        """
        try:
            subprocess.run(
                ['wmctrl', '-i', '-a', window_id],
                check=True,
                capture_output=True
            )
            time.sleep(0.5)  # Give window time to focus
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to focus window {window_id}: {e}")
            return False
    
    def capture_full_screen(self, output_path: Optional[str] = None) -> str:
        """
        Capture full screen screenshot.
        """
        try:
            screenshot = ImageGrab.grab()
            
            if output_path is None:
                timestamp = int(time.time())
                output_path = f"screenshot_{timestamp}.png"
            
            screenshot.save(output_path)
            logger.info(f"Full screen captured: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to capture full screen: {e}")
            raise
    
    def capture_window(self, window_id: str, output_path: Optional[str] = None) -> str:
        """
        Capture screenshot of a specific window.
        """
        try:
            # First focus the window
            if not self.focus_window(window_id):
                logger.warning(f"Could not focus window {window_id}, trying capture anyway")
            
            # Get window geometry
            geometry = self.get_window_geometry(window_id)
            
            if geometry:
                x, y, width, height = geometry
                # Capture the specific region
                screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            else:
                logger.warning(f"Could not get geometry for window {window_id}, capturing full screen")
                screenshot = ImageGrab.grab()
            
            if output_path is None:
                timestamp = int(time.time())
                output_path = f"window_{window_id}_{timestamp}.png"
            
            screenshot.save(output_path)
            logger.info(f"Window captured: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to capture window {window_id}: {e}")
            raise
    
    def capture_multiple_pages(self, window_id: str, page_count: int, 
                             output_dir: str = "captures", 
                             navigation_key: str = "Page_Down",
                             delay_seconds: float = 1.0) -> List[str]:
        """
        Capture multiple pages from a document window.
        
        Args:
            window_id: Window to capture
            page_count: Number of pages to capture
            output_dir: Directory to save captures
            navigation_key: Key to press for page navigation (Page_Down, Right, space)
            delay_seconds: Delay between page navigation and capture
        
        Returns:
            List of captured file paths
        """
        try:
            # Create output directory
            Path(output_dir).mkdir(exist_ok=True)
            
            # Focus the window
            if not self.focus_window(window_id):
                raise Exception(f"Could not focus window {window_id}")
            
            captured_files = []
            
            for page_num in range(1, page_count + 1):
                # Capture current page
                output_path = os.path.join(output_dir, f"page_{page_num:03d}.png")
                self.capture_window(window_id, output_path)
                captured_files.append(output_path)
                
                # Navigate to next page (except for last page)
                if page_num < page_count:
                    self._send_key_to_window(window_id, navigation_key)
                    time.sleep(delay_seconds)
            
            logger.info(f"Captured {len(captured_files)} pages to {output_dir}")
            return captured_files
            
        except Exception as e:
            logger.error(f"Failed to capture multiple pages: {e}")
            raise
    
    def _send_key_to_window(self, window_id: str, key: str) -> bool:
        """
        Send a key press to a specific window using xdotool.
        """
        try:
            subprocess.run(
                ['xdotool', 'key', '--window', window_id, key],
                check=True,
                capture_output=True
            )
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send key {key} to window {window_id}: {e}")
            return False
        except FileNotFoundError:
            logger.error("xdotool not found. Please install: sudo apt-get install xdotool")
            return False


def check_dependencies() -> List[str]:
    """
    Check if required system dependencies are installed.
    Returns list of missing dependencies.
    """
    missing = []
    
    # Check for wmctrl
    try:
        subprocess.run(['wmctrl', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append('wmctrl')
    
    # Check for xdotool
    try:
        subprocess.run(['xdotool', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append('xdotool')
    
    return missing