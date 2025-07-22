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
                    
                    [DllImport("user32.dll")]
                    public static extern bool EnumChildWindows(IntPtr hWndParent, EnumChildProc lpEnumFunc, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder lpClassName, int nMaxCount);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr FindWindowEx(IntPtr hWndParent, IntPtr hWndChildAfter, string lpszClass, string lpszWindow);
                    
                    [DllImport("user32.dll")]
                    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern bool BringWindowToTop(IntPtr hWnd);
                    
                    public delegate bool EnumChildProc(IntPtr hWnd, IntPtr lParam);
                    
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
                    
                    // Windows Messages
                    public const uint WM_KEYDOWN = 0x0100;
                    public const uint WM_KEYUP = 0x0101;
                    public const uint WM_CHAR = 0x0102;
                    public const uint WM_COMMAND = 0x0111;
                    public const uint WM_VSCROLL = 0x0115;
                    
                    // Virtual Key Codes
                    public const int VK_SPACE = 0x20;
                    public const int VK_PRIOR = 0x21;  // Page Up
                    public const int VK_NEXT = 0x22;   // Page Down
                    public const int VK_DOWN = 0x28;   // Down Arrow
                    public const int VK_UP = 0x26;     // Up Arrow
                    public const int VK_LEFT = 0x25;   // Left Arrow
                    public const int VK_RIGHT = 0x27;  // Right Arrow
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
    
    def _find_pdf_viewer_window(self, parent_window_id: str) -> str:
        """
        Find the child window that handles PDF viewer functionality within Adobe Reader.
        
        Args:
            parent_window_id: Parent window handle ID (Adobe Reader main window)
        
        Returns:
            Child window handle ID that should receive navigation keys, or parent if not found
        """
        if not self.powershell_available:
            logger.error("PowerShell not available - cannot enumerate child windows")
            return parent_window_id
        
        try:
            # PowerShell script to find PDF viewer child window
            ps_script = f'''
            $parentHandle = [IntPtr]{parent_window_id}
            if ($parentHandle -eq 0) {{
                Write-Output "{parent_window_id}"
                exit 0
            }}
            
            # Define Windows API functions for child window enumeration
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern bool EnumChildWindows(IntPtr hWndParent, EnumChildProc lpEnumFunc, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr FindWindowEx(IntPtr hWndParent, IntPtr hWndChildAfter, string lpszClass, string lpszWindow);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    public delegate bool EnumChildProc(IntPtr hWnd, IntPtr lParam);
                }}
"@
            
            $foundWindows = @()
            
            # Strategy 1: Look for common Adobe Reader PDF viewer window classes
            $knownPDFClasses = @(
                "AVPageView",           # Adobe Reader page view
                "AVScrolledPageView",   # Adobe Reader scrolled view  
                "AcroRd32Class",       # Adobe Reader document
                "AcrobatClass",        # Adobe Acrobat document
                "AVL_AVView",          # Adobe Viewer
                "AVPageViewWnd32",     # Adobe page view window
                "AVThumbnailView"      # Adobe thumbnail view
            )
            
            foreach ($className in $knownPDFClasses) {{
                $childHandle = [Win32]::FindWindowEx($parentHandle, [IntPtr]::Zero, $className, $null)
                if ($childHandle -ne [IntPtr]::Zero -and [Win32]::IsWindowVisible($childHandle)) {{
                    Write-Verbose "Found PDF viewer window with class: $className"
                    $foundWindows += $childHandle.ToString()
                }}
            }}
            
            # Strategy 2: Enumerate all child windows and look for likely candidates
            $allChildWindows = @()
            
            # Define callback function for EnumChildWindows
            $callback = {{
                param($hWnd, $lParam)
                
                $className = New-Object System.Text.StringBuilder(256)
                $result = [Win32]::GetClassName($hWnd, $className, $className.Capacity)
                
                if ($result -gt 0) {{
                    $class = $className.ToString()
                    $isVisible = [Win32]::IsWindowVisible($hWnd)
                    
                    # Look for classes that might contain PDF content
                    if ($isVisible -and ($class -match "(View|Page|Document|PDF|Acro|AVL)" -or $class.Length -gt 10)) {{
                        $allChildWindows += @{{
                            Handle = $hWnd.ToString()
                            ClassName = $class
                            IsVisible = $isVisible
                        }}
                    }}
                }}
                
                return $true  # Continue enumeration
            }}
            
            # This won't work directly in PowerShell due to delegate limitations
            # But we'll try the FindWindowEx approach which is more reliable
            
            # Strategy 3: Try to find the most likely candidate window
            # Look for windows with specific patterns in class names
            $candidateHandle = [IntPtr]::Zero
            $childAfter = [IntPtr]::Zero
            
            do {{
                $childAfter = [Win32]::FindWindowEx($parentHandle, $childAfter, $null, $null)
                if ($childAfter -ne [IntPtr]::Zero) {{
                    $className = New-Object System.Text.StringBuilder(256)
                    $result = [Win32]::GetClassName($childAfter, $className, $className.Capacity)
                    
                    if ($result -gt 0) {{
                        $class = $className.ToString()
                        $isVisible = [Win32]::IsWindowVisible($childAfter)
                        
                        # Prioritize windows with PDF-related class names
                        if ($isVisible -and ($class -match "(AVPageView|AVScrolled|AcroRd|Acrobat|AVL_AVView)" -or 
                                          ($class.Length -gt 8 -and $class -notmatch "(Button|Static|Edit|ComboBox|ListBox)"))) {{
                            $foundWindows += $childAfter.ToString()
                            Write-Verbose "Found candidate window: $class ($($childAfter.ToString()))"
                        }}
                    }}
                }}
            }} while ($childAfter -ne [IntPtr]::Zero)
            
            # Return the best candidate or the parent if none found
            if ($foundWindows.Count -gt 0) {{
                # Return the first likely PDF viewer window
                Write-Output $foundWindows[0]
            }} else {{
                # Fallback to parent window
                Write-Output "{parent_window_id}"
            }}
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,  # 15 second timeout for child window enumeration
                encoding='utf-8',
                errors='ignore'
            )
            
            child_window_id = result.stdout.strip()
            if child_window_id and child_window_id != parent_window_id:
                logger.info(f"Found PDF viewer child window: {child_window_id} (parent: {parent_window_id})")
                return child_window_id
            else:
                logger.info(f"No suitable PDF viewer child window found, using parent: {parent_window_id}")
                return parent_window_id
                
        except subprocess.TimeoutExpired:
            logger.error("PowerShell child window enumeration timed out after 15 seconds")
            return parent_window_id
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to enumerate child windows: {e}")
            return parent_window_id
        except Exception as e:
            logger.error(f"Unexpected error finding PDF viewer window: {e}")
            return parent_window_id
    
    def _send_key_to_window(self, window_id: str, key: str) -> bool:
        """
        Send a key press to a specific window using PostMessage for direct window messaging.
        First tries to find PDF viewer child window, then sends key directly via Windows API.
        
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
            # First, find the PDF viewer child window that should receive the keys
            target_window_id = self._find_pdf_viewer_window(window_id)
            logger.debug(f"Target window for key sending: {target_window_id} (original: {window_id})")
            
            # PowerShell script using PostMessage for direct key sending
            ps_script = f'''
            $targetHandle = [IntPtr]{target_window_id}
            if ($targetHandle -eq 0) {{
                Write-Error "Invalid target window handle"
                exit 1
            }}
            
            # Define comprehensive Windows API functions
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool BringWindowToTop(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    
                    [DllImport("user32.dll")]
                    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    // Windows Messages
                    public const uint WM_KEYDOWN = 0x0100;
                    public const uint WM_KEYUP = 0x0101;
                    public const uint WM_CHAR = 0x0102;
                    
                    // Virtual Key Codes
                    public const int VK_SPACE = 0x20;
                    public const int VK_PRIOR = 0x21;  // Page Up
                    public const int VK_NEXT = 0x22;   // Page Down
                    public const int VK_DOWN = 0x28;   // Down Arrow
                    public const int VK_UP = 0x26;     // Up Arrow
                    public const int VK_LEFT = 0x25;   // Left Arrow
                    public const int VK_RIGHT = 0x27; // Right Arrow
                    
                    public const int SW_RESTORE = 9;
                    public const int SW_SHOW = 5;
                }}
"@
            
            # Validate target window
            if (-not [Win32]::IsWindow($targetHandle)) {{
                Write-Error "Target window handle is not valid"
                exit 1
            }}
            
            # Map SendKeys format to virtual key codes
            $virtualKey = 0
            switch ("{key}") {{
                "{{DOWN}}" {{ $virtualKey = [Win32]::VK_DOWN }}
                "{{PGDN}}" {{ $virtualKey = [Win32]::VK_NEXT }}
                "{{RIGHT}}" {{ $virtualKey = [Win32]::VK_RIGHT }}
                "{{UP}}" {{ $virtualKey = [Win32]::VK_UP }}
                "{{LEFT}}" {{ $virtualKey = [Win32]::VK_LEFT }}
                " " {{ $virtualKey = [Win32]::VK_SPACE }}
                default {{
                    # Try to handle other keys - fallback to space
                    $virtualKey = [Win32]::VK_NEXT  # Default to Page Down for PDF navigation
                }}
            }}
            
            if ($virtualKey -eq 0) {{
                Write-Error "Unknown key mapping for: {key}"
                exit 1
            }}
            
            try {{
                # Send key messages directly to target window (no window state changes needed)
                $keyDownResult = [Win32]::PostMessage($targetHandle, [Win32]::WM_KEYDOWN, [IntPtr]$virtualKey, [IntPtr]0)
                Start-Sleep -Milliseconds 50
                $keyUpResult = [Win32]::PostMessage($targetHandle, [Win32]::WM_KEYUP, [IntPtr]$virtualKey, [IntPtr]0)
                
                if ($keyDownResult -and $keyUpResult) {{
                    Write-Output "SUCCESS: PostMessage sent VK=$virtualKey to window $($targetHandle.ToString())"
                }} else {{
                    Write-Warning "PostMessage may have failed: KeyDown=$keyDownResult KeyUp=$keyUpResult"
                    
                    # Fallback: try SendMessage instead of PostMessage
                    [Win32]::SendMessage($targetHandle, [Win32]::WM_KEYDOWN, [IntPtr]$virtualKey, [IntPtr]0) | Out-Null
                    Start-Sleep -Milliseconds 50  
                    [Win32]::SendMessage($targetHandle, [Win32]::WM_KEYUP, [IntPtr]$virtualKey, [IntPtr]0) | Out-Null
                    Write-Output "FALLBACK: SendMessage used as fallback"
                }}
                
            }} catch {{
                Write-Error "Failed to send key message: $($_.Exception.Message)"
                exit 1
            }}
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,  # 15 second timeout for enhanced key sending
                encoding='utf-8',
                errors='ignore'
            )
            
            if "SUCCESS" in result.stdout or "FALLBACK" in result.stdout:
                logger.debug(f"Successfully sent key '{key}' to target window {target_window_id}")
                return True
            else:
                logger.error(f"Failed to send key '{key}' to target window {target_window_id}")
                logger.error(f"PowerShell output: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"PowerShell enhanced key sending timed out after 15 seconds")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send key '{key}' using PostMessage: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in enhanced key sending: {e}")
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
            
            # Detect and preserve original window state
            logger.info(f"Starting multi-page capture: {page_count} pages from window {window_id}")
            logger.info(f"Navigation key: {navigation_key} -> {sendkeys_format}, Delay: {delay_seconds}s")
            
            original_window_state = self._detect_and_prepare_window_state(window_id)
            logger.info(f"Original window state: {original_window_state}")
            
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
            
            # Restore original window state
            if original_window_state:
                self._restore_window_state(window_id, original_window_state)
                logger.info(f"Restored window to original state: {original_window_state}")
            
            return captured_files
            
        except Exception as e:
            # Restore original window state even on error
            if 'original_window_state' in locals() and original_window_state:
                try:
                    self._restore_window_state(window_id, original_window_state)
                    logger.info(f"Restored window state after error: {original_window_state}")
                except Exception as restore_error:
                    logger.warning(f"Failed to restore window state after error: {restore_error}")
            
            logger.error(f"Failed to capture multiple pages: {e}")
            raise
    
    def _detect_and_prepare_window_state(self, window_id: str) -> dict:
        """
        Detect current window state and prepare for capture session.
        Only modifies window state if necessary for capture operations.
        
        Args:
            window_id: Window handle ID
        
        Returns:
            Dictionary with original window state information
        """
        if not self.powershell_available:
            logger.warning("PowerShell not available - cannot detect window state")
            return {}
        
        try:
            ps_script = f'''
            $windowHandle = [IntPtr]{window_id}
            if ($windowHandle -eq 0) {{
                Write-Output "invalid_handle"
                exit 0
            }}
            
            # Define Windows API functions for state detection
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern bool IsWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsIconic(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool IsZoomed(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern IntPtr GetForegroundWindow();
                    
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    public static extern bool BringWindowToTop(IntPtr hWnd);
                    
                    public const int SW_RESTORE = 9;
                    public const int SW_SHOW = 5;
                    public const int SW_MINIMIZE = 6;
                    public const int SW_MAXIMIZE = 3;
                }}
"@
            
            if (-not [Win32]::IsWindow($windowHandle)) {{
                Write-Output "invalid_window"
                exit 0
            }}
            
            # Detect current state
            $isVisible = [Win32]::IsWindowVisible($windowHandle)
            $isMinimized = [Win32]::IsIconic($windowHandle)
            $isMaximized = [Win32]::IsZoomed($windowHandle)
            $isForeground = ([Win32]::GetForegroundWindow() -eq $windowHandle)
            
            # Determine state name
            $stateName = if ($isMinimized) {{ 
                "minimized" 
            }} elseif ($isMaximized) {{ 
                "maximized" 
            }} elseif ($isVisible) {{ 
                "normal" 
            }} else {{ 
                "hidden" 
            }}
            
            # Determine if we need to prepare the window for capture
            $needsPreparation = $false
            
            if ($isMinimized -or -not $isVisible) {{
                Write-Verbose "Window needs preparation: restoring from minimized/hidden state"
                $needsPreparation = $true
                
                # Only restore if minimized or hidden
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_RESTORE) | Out-Null
                Start-Sleep -Milliseconds 200
            }}
            
            if (-not $isForeground) {{
                Write-Verbose "Window needs focus preparation"
                $needsPreparation = $true
                
                # Only set focus if not already foreground
                [Win32]::BringWindowToTop($windowHandle) | Out-Null
                [Win32]::SetForegroundWindow($windowHandle) | Out-Null
                Start-Sleep -Milliseconds 100
            }}
            
            # Output state information
            Write-Output "$stateName|$isVisible|$isMinimized|$isMaximized|$isForeground|$needsPreparation"
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
                encoding='utf-8',
                errors='ignore'
            )
            
            output = result.stdout.strip()
            if output in ["invalid_handle", "invalid_window"]:
                logger.warning(f"Invalid window for state detection: {output}")
                return {}
            
            # Parse state information
            parts = output.split('|')
            if len(parts) >= 6:
                state_info = {
                    'state_name': parts[0],
                    'was_visible': parts[1] == 'True',
                    'was_minimized': parts[2] == 'True', 
                    'was_maximized': parts[3] == 'True',
                    'was_foreground': parts[4] == 'True',
                    'was_prepared': parts[5] == 'True'
                }
                
                logger.debug(f"Detected window state: {state_info}")
                return state_info
            else:
                logger.warning(f"Could not parse window state: {output}")
                return {}
                
        except subprocess.TimeoutExpired:
            logger.error("Window state detection timed out")
            return {}
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to detect window state: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in window state detection: {e}")
            return {}
    
    def _restore_window_state(self, window_id: str, original_state: dict) -> bool:
        """
        Restore window to its original state after capture session.
        
        Args:
            window_id: Window handle ID
            original_state: State information from _detect_and_prepare_window_state
        
        Returns:
            True if restoration was successful, False otherwise
        """
        if not self.powershell_available or not original_state:
            return False
        
        try:
            # Only restore if we made changes during preparation
            if not original_state.get('was_prepared', False):
                logger.debug("No window state changes were made, skipping restoration")
                return True
            
            ps_script = f'''
            $windowHandle = [IntPtr]{window_id}
            if ($windowHandle -eq 0) {{
                exit 1
            }}
            
            # Define Windows API functions  
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    
                    public const int SW_RESTORE = 9;
                    public const int SW_MINIMIZE = 6;
                    public const int SW_MAXIMIZE = 3;
                    public const int SW_HIDE = 0;
                }}
"@
            
            $wasMinimized = [bool]::Parse("{str(original_state.get('was_minimized', False)).lower()}")
            $wasMaximized = [bool]::Parse("{str(original_state.get('was_maximized', False)).lower()}")
            $wasVisible = [bool]::Parse("{str(original_state.get('was_visible', True)).lower()}")
            
            # Restore original window state
            if ($wasMinimized) {{
                Write-Verbose "Restoring to minimized state"
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_MINIMIZE) | Out-Null
            }} elseif ($wasMaximized) {{
                Write-Verbose "Restoring to maximized state" 
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_MAXIMIZE) | Out-Null
            }} elseif (-not $wasVisible) {{
                Write-Verbose "Restoring to hidden state"
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_HIDE) | Out-Null
            }} else {{
                Write-Verbose "Restoring to normal state"
                [Win32]::ShowWindow($windowHandle, [Win32]::SW_RESTORE) | Out-Null
            }}
            
            Write-Output "SUCCESS"
            '''
            
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
                encoding='utf-8',
                errors='ignore'
            )
            
            if "SUCCESS" in result.stdout:
                logger.debug("Successfully restored window state")
                return True
            else:
                logger.warning("Failed to restore window state")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Window state restoration timed out")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restore window state: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in window state restoration: {e}")
            return False


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