"""
Screenshot capture functionality for Linux systems and Windows (via WSL2).
Uses pyscreenshot for cross-platform screenshot capability.
"""

import os
import subprocess
import time
import platform
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pyscreenshot as ImageGrab
from PIL import Image
import logging

logger = logging.getLogger(__name__)


def detect_environment() -> str:
    """
    Detect the current runtime environment.
    
    Returns:
        'wsl' if running in WSL (can access Windows)
        'linux' if running in native Linux
        'windows' if running in native Windows
    """
    try:
        # Check if we're in WSL
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'microsoft' in version_info or 'wsl' in version_info:
                    return 'wsl'
        
        # Check if we're on Windows
        if platform.system() == 'Windows':
            return 'windows'
            
        # Default to Linux
        return 'linux'
        
    except Exception as e:
        logger.warning(f"Could not detect environment: {e}")
        return 'linux'  # Safe default


class WindowsWindowManager:
    """Handles Windows application enumeration and screenshot capture from WSL2."""
    
    def __init__(self):
        self.powershell_available = self._check_powershell()
        
    def _check_powershell(self) -> bool:
        """Check if PowerShell is available from WSL2."""
        try:
            result = subprocess.run(
                ['powershell.exe', '-Command', 'Write-Host "test"'],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("PowerShell not available from WSL2")
            return False
    
    def list_windows(self) -> List[Dict[str, str]]:
        """
        List all Windows applications with visible windows using PowerShell.
        Returns list of window info dictionaries.
        """
        if not self.powershell_available:
            logger.error("PowerShell not available - cannot list Windows applications")
            return []
            
        try:
            # PowerShell script to get window information
            ps_script = '''
            Get-Process | Where-Object { 
                $_.MainWindowTitle -ne "" -and $_.ProcessName -ne "dwm" 
            } | Select-Object Id, ProcessName, MainWindowTitle, @{
                Name="WindowHandle"; Expression={$_.MainWindowHandle}
            } | ConvertTo-Json -Compress
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True
            )
            
            import json
            if result.stdout.strip():
                try:
                    # Handle both single object and array responses
                    data = json.loads(result.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]  # Convert single result to list
                    
                    windows = []
                    for proc in data:
                        windows.append({
                            'id': str(proc.get('WindowHandle', proc.get('Id', ''))),
                            'title': proc.get('MainWindowTitle', ''),
                            'process_name': proc.get('ProcessName', ''),
                            'process_id': str(proc.get('Id', '')),
                            'type': 'windows'
                        })
                    
                    return windows
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse PowerShell JSON output: {e}")
                    return []
            else:
                return []
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list Windows applications: {e}")
            return []
    
    def capture_window(self, window_id: str, output_path: Optional[str] = None) -> str:
        """
        Capture screenshot of a Windows application window.
        """
        if not self.powershell_available:
            raise Exception("PowerShell not available - cannot capture Windows applications")
        
        try:
            # PowerShell script to capture window screenshot
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            
            $windowHandle = [IntPtr]{window_id}
            if ($windowHandle -eq 0) {{
                Write-Error "Invalid window handle"
                exit 1
            }}
            
            # Get window rectangle
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [StructLayout(LayoutKind.Sequential)]
                    public struct RECT {{
                        public int Left, Top, Right, Bottom;
                    }}
                    [DllImport("user32.dll")]
                    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
                }}
"@
            
            $rect = New-Object Win32+RECT
            $success = [Win32]::GetWindowRect($windowHandle, [ref]$rect)
            
            if (-not $success) {{
                Write-Error "Could not get window rectangle"
                exit 1
            }}
            
            $width = $rect.Right - $rect.Left
            $height = $rect.Bottom - $rect.Top
            
            if ($width -le 0 -or $height -le 0) {{
                Write-Error "Invalid window dimensions"
                exit 1
            }}
            
            # Capture screenshot
            $bitmap = New-Object System.Drawing.Bitmap($width, $height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, [System.Drawing.Size]::new($width, $height))
            $graphics.Dispose()
            
            # Save to temporary file in Windows temp directory
            $tempPath = [System.IO.Path]::GetTempFileName() + ".png"
            $bitmap.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
            $bitmap.Dispose()
            
            Write-Output $tempPath
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True
            )
            
            temp_windows_path = result.stdout.strip()
            if not temp_windows_path:
                raise Exception("PowerShell did not return temp file path")
            
            # Convert Windows path to WSL path
            wsl_temp_path = self._windows_path_to_wsl(temp_windows_path)
            
            if output_path is None:
                timestamp = int(time.time())
                output_path = f"windows_capture_{window_id}_{timestamp}.png"
            
            # Copy from Windows temp to desired location
            subprocess.run(['cp', wsl_temp_path, output_path], check=True)
            
            # Clean up Windows temp file
            subprocess.run(
                ['powershell.exe', '-Command', f'Remove-Item "{temp_windows_path}" -Force'],
                check=False  # Don't fail if cleanup fails
            )
            
            logger.info(f"Windows application captured: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to capture Windows application {window_id}: {e}")
            raise
    
    def _windows_path_to_wsl(self, windows_path: str) -> str:
        """Convert Windows path to WSL path."""
        try:
            result = subprocess.run(
                ['wslpath', windows_path],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # Fallback: manual conversion for basic cases
            if windows_path.startswith('C:'):
                return windows_path.replace('C:', '/mnt/c').replace('\\', '/')
            return windows_path


class CrossPlatformWindowManager:
    """
    Unified interface that automatically selects the appropriate window manager
    based on the runtime environment.
    """
    
    def __init__(self):
        self.environment = detect_environment()
        self.manager = self._create_manager()
        
    def _create_manager(self):
        """Create appropriate window manager based on environment."""
        if self.environment == 'wsl':
            # In WSL, try Windows manager first, fallback to Linux
            windows_manager = WindowsWindowManager()
            if windows_manager.powershell_available:
                logger.info("Using Windows application manager (PowerShell from WSL2)")
                return windows_manager
            else:
                logger.info("PowerShell unavailable, falling back to Linux X11 manager")
                return WindowCapture()
        elif self.environment == 'windows':
            logger.info("Using Windows application manager")
            return WindowsWindowManager()
        else:  # linux
            logger.info("Using Linux X11 window manager")
            return WindowCapture()
    
    def list_windows(self) -> List[Dict[str, str]]:
        """List all available windows using the appropriate manager."""
        try:
            windows = self.manager.list_windows()
            
            # Add environment info to each window
            for window in windows:
                window['environment'] = self.environment
                if 'type' not in window:
                    window['type'] = 'x11' if self.environment == 'linux' else self.environment
                    
            return windows
        except Exception as e:
            logger.error(f"Failed to list windows: {e}")
            return []
    
    def capture_window(self, window_id: str, output_path: Optional[str] = None) -> str:
        """Capture screenshot of a specific window."""
        return self.manager.capture_window(window_id, output_path)
    
    def capture_full_screen(self, output_path: Optional[str] = None) -> str:
        """Capture full screen screenshot."""
        if hasattr(self.manager, 'capture_full_screen'):
            return self.manager.capture_full_screen(output_path)
        else:
            # Fallback using pyscreenshot
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
    
    def get_environment_info(self) -> Dict[str, str]:
        """Get information about the current environment and capabilities."""
        info = {
            'environment': self.environment,
            'manager_type': type(self.manager).__name__
        }
        
        if isinstance(self.manager, WindowsWindowManager):
            info['powershell_available'] = self.manager.powershell_available
        elif isinstance(self.manager, WindowCapture):
            missing_deps = check_dependencies()
            info['missing_dependencies'] = missing_deps
            info['x11_available'] = len(missing_deps) == 0
            
        return info


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