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
            logger.info("Checking PowerShell availability...")
            result = subprocess.run(
                ['powershell.exe', '-Command', 'Write-Host "test"'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10  # 10 second timeout
            )
            logger.info("PowerShell is available")
            return True
        except subprocess.TimeoutExpired:
            logger.error("PowerShell check timed out after 10 seconds")
            return False
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PowerShell not available from WSL2: {e}")
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
            # Enhanced PowerShell script to get comprehensive window information
            ps_script = '''
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                
                public class Win32 {
                    [DllImport("user32.dll")]
                    public static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsIconic(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsZoomed(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetWindowTextLength(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
                }
"@

            $windows = @()

            # Get processes with capturable windows only
            Get-Process | Where-Object { 
                $_.MainWindowHandle -ne 0 -and $_.ProcessName -notmatch "^(dwm|csrss|winlogon|wininit)$"
            } | ForEach-Object {
                $handle = [IntPtr]$_.MainWindowHandle
                $isVisible = [Win32]::IsWindowVisible($handle)
                $isMinimized = [Win32]::IsIconic($handle)
                $isMaximized = [Win32]::IsZoomed($handle)
                
                # Only include windows that are in capturable states
                # Skip hidden windows that can't be meaningfully captured
                if (-not ($isVisible -or $isMinimized)) {
                    return  # Skip this window
                }
                
                # Get window title using Windows API (more reliable than MainWindowTitle)
                $titleLength = [Win32]::GetWindowTextLength($handle)
                if ($titleLength -gt 0) {
                    $title = New-Object System.Text.StringBuilder($titleLength + 1)
                    [Win32]::GetWindowText($handle, $title, $title.Capacity) | Out-Null
                    $windowTitle = $title.ToString()
                } else {
                    $windowTitle = $_.MainWindowTitle
                }
                
                # Include window even if title is empty, but provide useful info
                if ([string]::IsNullOrEmpty($windowTitle)) {
                    $windowTitle = "[$($_.ProcessName) - $($_.Id)]"
                }
                
                # Determine window state - only capturable states
                $windowState = if ($isMinimized) { 
                    "minimized" 
                } elseif ($isMaximized) { 
                    "maximized" 
                } else { 
                    "normal" 
                }
                
                $windows += @{
                    id = $_.MainWindowHandle.ToString()
                    title = $windowTitle
                    process_name = $_.ProcessName
                    process_id = $_.Id.ToString()
                    window_handle = $_.MainWindowHandle.ToString()
                    is_visible = $isVisible
                    is_minimized = $isMinimized
                    is_maximized = $isMaximized
                    window_state = $windowState
                    type = "windows"
                }
            }

            # Convert to JSON
            $windows | ConvertTo-Json -Compress
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,  # 30 second timeout for window enumeration
                encoding='utf-8',
                errors='ignore'  # Ignore encoding errors to handle special characters
            )
            
            import json
            if result.stdout.strip():
                try:
                    # Handle both single object and array responses
                    data = json.loads(result.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]  # Convert single result to list
                    
                    windows = []
                    for window_info in data:
                        # Only include windows with valid window handles (> 0)
                        window_handle = str(window_info.get('window_handle', '0'))
                        if window_handle == '0':
                            continue  # Skip processes without actual windows
                        
                        # Use the enhanced window information from the new PowerShell script
                        windows.append({
                            'id': str(window_info.get('id', '')),
                            'title': window_info.get('title', ''),
                            'process_name': window_info.get('process_name', ''),
                            'process_id': str(window_info.get('process_id', '')),
                            'window_handle': window_handle,
                            'is_visible': window_info.get('is_visible', False),
                            'is_minimized': window_info.get('is_minimized', False),
                            'is_maximized': window_info.get('is_maximized', False),
                            'window_state': window_info.get('window_state', 'normal'),  # Default to normal instead of unknown
                            'type': 'windows'
                        })
                    
                    logger.info(f"Found {len(windows)} capturable windows using enhanced detection")
                    if windows:
                        # Log stats about capturable window states for debugging
                        normal_count = sum(1 for w in windows if w['window_state'] == 'normal')
                        minimized_count = sum(1 for w in windows if w['window_state'] == 'minimized')
                        maximized_count = sum(1 for w in windows if w['window_state'] == 'maximized')
                        logger.info(f"Window states: {normal_count} normal, {minimized_count} minimized, {maximized_count} maximized")
                    
                    return windows
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse PowerShell JSON output: {e}")
                    logger.error(f"PowerShell output was: {result.stdout[:500]}...")  # Log first 500 chars for debugging
                    return []
            else:
                logger.warning("PowerShell returned empty output - no windows detected")
                return []
            
        except subprocess.TimeoutExpired:
            logger.error("PowerShell window enumeration timed out after 30 seconds")
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
            # Enhanced PowerShell script with PrintWindow support for minimized windows
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            
            $windowHandle = [IntPtr]{window_id}
            if ($windowHandle -eq 0) {{
                Write-Error "Invalid window handle"
                exit 1
            }}
            
            # Define comprehensive Windows API functions
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [StructLayout(LayoutKind.Sequential)]
                    public struct RECT {{
                        public int Left, Top, Right, Bottom;
                    }}
                    
                    // Window management APIs
                    [DllImport("user32.dll")]
                    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsIconic(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    
                    [DllImport("user32.dll")]
                    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
                    
                    [DllImport("user32.dll")]
                    public static extern bool SetLayeredWindowAttributes(IntPtr hWnd, uint crKey, byte bAlpha, uint dwFlags);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetWindowLong(IntPtr hWnd, int nIndex);
                    
                    [DllImport("user32.dll")]
                    public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);
                    
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr GetForegroundWindow();
                    
                    // Constants
                    public const int SW_HIDE = 0;
                    public const int SW_RESTORE = 9;
                    public const int SW_MINIMIZE = 6;
                    public const int SW_SHOW = 5;
                    public const int GWL_EXSTYLE = -20;
                    public const int WS_EX_LAYERED = 0x80000;
                    public const int LWA_ALPHA = 0x2;
                    public const uint PW_CLIENTONLY = 0x1;
                    public const uint PW_RENDERFULLCONTENT = 0x2;
                }}
"@
            
            # Check if window is minimized and implement smart capture logic
            $isMinimized = [Win32]::IsIconic($windowHandle)
            $wasMinimized = $false
            $originalExStyle = 0
            
            try {{
                # Get window rectangle
                $rect = New-Object Win32+RECT
                $success = [Win32]::GetWindowRect($windowHandle, [ref]$rect)
                
                if (-not $success) {{
                    Write-Error "Could not get window rectangle"
                    exit 1
                }}
                
                $width = $rect.Right - $rect.Left
                $height = $rect.Bottom - $rect.Top
                
                if ($width -le 0 -or $height -le 0) {{
                    Write-Error "Invalid window dimensions: $($width)x$($height)"
                    exit 1
                }}
                
                # Handle minimized windows with stealth restoration
                if ($isMinimized) {{
                    Write-Verbose "Window is minimized, using stealth restoration technique"
                    $wasMinimized = $true
                    
                    # Make window transparent for stealth operation
                    $originalExStyle = [Win32]::GetWindowLong($windowHandle, [Win32]::GWL_EXSTYLE)
                    $newExStyle = $originalExStyle -bor [Win32]::WS_EX_LAYERED
                    [Win32]::SetWindowLong($windowHandle, [Win32]::GWL_EXSTYLE, $newExStyle) | Out-Null
                    [Win32]::SetLayeredWindowAttributes($windowHandle, 0, 1, [Win32]::LWA_ALPHA) | Out-Null
                    
                    # Restore window temporarily
                    [Win32]::ShowWindow($windowHandle, [Win32]::SW_RESTORE) | Out-Null
                    Start-Sleep -Milliseconds 100  # Brief pause for window to render
                    
                    # Update rectangle after restoration
                    $success = [Win32]::GetWindowRect($windowHandle, [ref]$rect)
                    if ($success) {{
                        $width = $rect.Right - $rect.Left
                        $height = $rect.Bottom - $rect.Top
                    }}
                }}
                
                # Create bitmap for capture
                $bitmap = New-Object System.Drawing.Bitmap($width, $height)
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                
                # Try PrintWindow first (better for minimized/hidden windows)
                $hdcBitmap = $graphics.GetHdc()
                $printSuccess = [Win32]::PrintWindow($windowHandle, $hdcBitmap, [Win32]::PW_RENDERFULLCONTENT)
                $graphics.ReleaseHdc($hdcBitmap)
                
                # Fallback to CopyFromScreen if PrintWindow fails
                if (-not $printSuccess) {{
                    Write-Verbose "PrintWindow failed, falling back to CopyFromScreen"
                    if (-not $isMinimized) {{
                        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, [System.Drawing.Size]::new($width, $height))
                    }} else {{
                        throw "Cannot capture minimized window with CopyFromScreen"
                    }}
                }}
                
                $graphics.Dispose()
                
                # Save to temporary file
                $tempPath = [System.IO.Path]::GetTempFileName() + ".png"
                $bitmap.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
                $bitmap.Dispose()
                
                Write-Output $tempPath
                
            }} finally {{
                # Restore original window state if it was modified
                if ($wasMinimized) {{
                    # Restore original transparency
                    [Win32]::SetWindowLong($windowHandle, [Win32]::GWL_EXSTYLE, $originalExStyle) | Out-Null
                    
                    # Re-minimize the window
                    [Win32]::ShowWindow($windowHandle, [Win32]::SW_MINIMIZE) | Out-Null
                }}
            }}
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,  # 60 second timeout for screenshot capture
                encoding='utf-8',
                errors='ignore'  # Ignore encoding errors to handle special characters
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
            
        except subprocess.TimeoutExpired:
            logger.error(f"PowerShell window capture timed out after 60 seconds")
            raise Exception(f"Capture timeout for window {window_id}")
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
                check=True,
                timeout=5  # 5 second timeout for path conversion
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Fallback: manual conversion for basic cases
            if windows_path.startswith('C:'):
                return windows_path.replace('C:', '/mnt/c').replace('\\', '/')
            return windows_path
    
    def capture_full_screen(self, output_path: Optional[str] = None) -> str:
        """
        Capture full screen screenshot using PowerShell from WSL2.
        """
        if not self.powershell_available:
            raise Exception("PowerShell not available - cannot capture full screen")
        
        logger.info("Capturing full screen using PowerShell...")
        try:
            # PowerShell script to capture full screen
            ps_script = '''
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            
            # Get primary screen dimensions
            $primaryScreen = [System.Windows.Forms.Screen]::PrimaryScreen
            $bounds = $primaryScreen.Bounds
            
            $width = $bounds.Width
            $height = $bounds.Height
            
            Write-Verbose "Screen dimensions: ${width}x${height}"
            
            # Capture full screen
            $bitmap = New-Object System.Drawing.Bitmap($width, $height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen(0, 0, 0, 0, [System.Drawing.Size]::new($width, $height))
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
                check=True,
                timeout=30  # 30 second timeout for full screen capture
            )
            
            temp_windows_path = result.stdout.strip()
            if not temp_windows_path:
                raise Exception("PowerShell did not return temp file path")
            
            # Convert Windows path to WSL path
            wsl_temp_path = self._windows_path_to_wsl(temp_windows_path)
            
            if output_path is None:
                timestamp = int(time.time())
                output_path = f"fullscreen_{timestamp}.png"
            
            # Copy from Windows temp to desired location
            subprocess.run(['cp', wsl_temp_path, output_path], check=True)
            
            # Clean up Windows temp file
            subprocess.run(
                ['powershell.exe', '-Command', f'Remove-Item "{temp_windows_path}" -Force'],
                check=False  # Don't fail if cleanup fails
            )
            
            logger.info(f"Full screen captured: {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            logger.error("PowerShell full screen capture timed out after 30 seconds")
            raise Exception("Full screen capture timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to capture full screen: {e}")
            raise
        except Exception as e:
            logger.error(f"Full screen capture failed: {e}")
            raise
    
    def debug_window_detection(self) -> Dict[str, any]:
        """
        Comprehensive debugging information for window detection.
        Returns detailed diagnostics about the PowerShell environment and window detection.
        """
        debug_info = {
            'powershell_available': self.powershell_available,
            'detection_methods': [],
            'raw_powershell_output': '',
            'parsing_errors': [],
            'process_info': {}
        }
        
        if not self.powershell_available:
            debug_info['error'] = 'PowerShell not available'
            return debug_info
        
        try:
            # Test basic PowerShell functionality
            basic_test = subprocess.run(
                ['powershell.exe', '-Command', 'Get-Process | Select-Object -First 5 Name, Id | ConvertTo-Json'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            debug_info['basic_powershell_test'] = 'SUCCESS'
            debug_info['sample_processes'] = basic_test.stdout.strip()[:200] + '...'
            
        except Exception as e:
            debug_info['basic_powershell_test'] = f'FAILED: {str(e)}'
            return debug_info
        
        # Test our enhanced window detection script with verbose output
        try:
            debug_script = '''
            $VerbosePreference = "Continue"
            Write-Verbose "Starting window detection debug..."
            
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                
                public class Win32 {
                    [DllImport("user32.dll")]
                    public static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsIconic(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsZoomed(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetWindowTextLength(IntPtr hWnd);
                }
"@
            
            $allProcesses = Get-Process | Measure-Object | Select-Object -ExpandProperty Count
            Write-Verbose "Total processes found: $allProcesses"
            
            $processesWithWindows = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } | Measure-Object | Select-Object -ExpandProperty Count
            Write-Verbose "Processes with windows: $processesWithWindows"
            
            $windows = @()
            Get-Process | Where-Object { 
                $_.MainWindowHandle -ne 0 -and $_.ProcessName -notmatch "^(dwm|csrss|winlogon|wininit)$"
            } | ForEach-Object {
                Write-Verbose "Processing: $($_.ProcessName) (ID: $($_.Id))"
                
                $handle = [IntPtr]$_.MainWindowHandle
                $isVisible = [Win32]::IsWindowVisible($handle)
                $isMinimized = [Win32]::IsIconic($handle)
                $isMaximized = [Win32]::IsZoomed($handle)
                
                # Only include capturable windows (same logic as main script)
                if (-not ($isVisible -or $isMinimized)) {
                    Write-Verbose "Skipping hidden window: $($_.ProcessName)"
                    return
                }
                
                $windows += @{
                    process_name = $_.ProcessName
                    process_id = $_.Id
                    window_handle = $_.MainWindowHandle.ToString()
                    main_window_title = $_.MainWindowTitle
                    is_visible = $isVisible
                    is_minimized = $isMinimized
                    is_maximized = $isMaximized
                    window_state = if ($isMinimized) { "minimized" } elseif ($isMaximized) { "maximized" } else { "normal" }
                }
            }
            
            Write-Host "PROCESS_COUNT:$allProcesses"
            Write-Host "WINDOWS_COUNT:$processesWithWindows"
            Write-Host "FILTERED_COUNT:$($windows.Count)"
            $windows | ConvertTo-Json -Depth 2
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', debug_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            debug_info['enhanced_script_exit_code'] = result.returncode
            debug_info['raw_powershell_output'] = result.stdout
            debug_info['powershell_stderr'] = result.stderr
            
            # Parse the debug output
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('PROCESS_COUNT:'):
                    debug_info['total_processes'] = int(line.split(':')[1])
                elif line.startswith('WINDOWS_COUNT:'):
                    debug_info['processes_with_windows'] = int(line.split(':')[1])
                elif line.startswith('FILTERED_COUNT:'):
                    debug_info['filtered_windows'] = int(line.split(':')[1])
            
        except Exception as e:
            debug_info['enhanced_script_error'] = str(e)
        
        return debug_info
    
    def _send_key_to_window(self, window_id: str, key: str) -> bool:
        """
        Send a key press to a specific window using PowerShell SendKeys.
        
        Args:
            window_id: Window handle ID
            key: Key to send (e.g., "{DOWN}", "{PGDN}", "{RIGHT}")
        
        Returns:
            True if key was sent successfully, False otherwise
        """
        if not self.powershell_available:
            logger.error("PowerShell not available - cannot send keys")
            return False
        
        try:
            # PowerShell script to focus window and send key
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            
            $windowHandle = [IntPtr]{window_id}
            if ($windowHandle -eq 0) {{
                Write-Error "Invalid window handle"
                exit 1
            }}
            
            # Define Windows API functions for window management
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr GetForegroundWindow();
                    
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    
                    public const int SW_RESTORE = 9;
                    public const int SW_SHOW = 5;
                }}
"@
            
            try {{
                # Ensure window is visible and restored if minimized
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_RESTORE) | Out-Null
                Start-Sleep -Milliseconds 100
                
                # Set focus to target window
                $focusResult = [Win32]::SetForegroundWindow($windowHandle)
                if (-not $focusResult) {{
                    Write-Warning "Failed to set foreground window"
                }}
                
                # Brief delay to ensure window has focus
                Start-Sleep -Milliseconds 200
                
                # Send the key to the focused window
                [System.Windows.Forms.SendKeys]::SendWait("{key}")
                
                Write-Output "SUCCESS"
                
            }} catch {{
                Write-Error "Failed to send key: $($_.Exception.Message)"
                exit 1
            }}
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,  # 10 second timeout for key sending
                encoding='utf-8',
                errors='ignore'
            )
            
            if "SUCCESS" in result.stdout:
                logger.debug(f"Successfully sent key '{key}' to window {window_id}")
                return True
            else:
                logger.error(f"Failed to send key '{key}' to window {window_id}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"PowerShell key sending timed out after 10 seconds")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send key '{key}' to window {window_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending key: {e}")
            return False
    
    def capture_multiple_pages(self, window_id: str, page_count: int, 
                             output_dir: str = "captures", 
                             navigation_key: str = "{DOWN}",
                             delay_seconds: float = 1.5) -> List[str]:
        """
        Capture multiple pages from a document window with automatic navigation.
        
        Args:
            window_id: Window ID containing the document
            page_count: Number of pages to capture
            output_dir: Directory to save captured pages
            navigation_key: Key to send for navigation (e.g., "{DOWN}", "{PGDN}", "{RIGHT}")
            delay_seconds: Delay between navigation and capture
        
        Returns:
            List of captured file paths
        """
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Convert navigation key names to SendKeys format
            key_mapping = {
                "Down": "{DOWN}",
                "Page_Down": "{PGDN}",
                "Right": "{RIGHT}",
                "Up": "{UP}",
                "Left": "{LEFT}",
                "space": " ",
                "Enter": "{ENTER}",
                "Tab": "{TAB}"
            }
            
            # Use mapping if available, otherwise use key as-is (for direct SendKeys format)
            sendkeys_format = key_mapping.get(navigation_key, navigation_key)
            
            logger.info(f"Starting multi-page capture: {page_count} pages from window {window_id}")
            logger.info(f"Navigation key: {navigation_key} -> {sendkeys_format}, Delay: {delay_seconds}s")
            
            captured_files = []
            
            for page_num in range(1, page_count + 1):
                logger.info(f"Capturing page {page_num}/{page_count}")
                
                # Capture current page
                output_path = os.path.join(output_dir, f"page_{page_num:03d}.png")
                try:
                    captured_path = self.capture_window(window_id, output_path)
                    captured_files.append(captured_path)
                    logger.info(f"Captured page {page_num}: {captured_path}")
                except Exception as e:
                    logger.error(f"Failed to capture page {page_num}: {e}")
                    # Continue with next page even if one fails
                    continue
                
                # Navigate to next page (except for last page)
                if page_num < page_count:
                    logger.debug(f"Navigating to next page using key: {sendkeys_format}")
                    key_sent = self._send_key_to_window(window_id, sendkeys_format)
                    if not key_sent:
                        logger.warning(f"Failed to send navigation key for page {page_num}")
                        # Continue anyway - user might manually navigate
                    
                    # Wait for page to load/render
                    time.sleep(delay_seconds)
            
            logger.info(f"Multi-page capture completed: {len(captured_files)} pages captured to {output_dir}")
            return captured_files
            
        except Exception as e:
            logger.error(f"Failed to capture multiple pages: {e}")
            raise


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
                check=True,
                timeout=10  # 10 second timeout for window listing
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
                check=True,
                timeout=10  # 10 second timeout for window geometry
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
                capture_output=True,
                timeout=5  # 5 second timeout for window focus
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
                capture_output=True,
                timeout=5  # 5 second timeout for key send
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
        subprocess.run(['wmctrl', '--version'], capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        missing.append('wmctrl')
    
    # Check for xdotool
    try:
        subprocess.run(['xdotool', '--version'], capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        missing.append('xdotool')
    
    return missing