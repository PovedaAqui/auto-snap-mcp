"""
MCP Server for automated screenshot capture and PDF conversion.
"""

import asyncio
import logging
import json
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from capture import CrossPlatformWindowManager, WindowCapture, check_dependencies
from processing import ImageProcessor, check_tesseract
from pdf_utils import PDFConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize MCP server
logger.info("Initializing MCP server...")
mcp = FastMCP("Auto-Snap MCP")
logger.info("MCP server initialized")

# Initialize components lazily to avoid blocking MCP initialization
window_manager = None
image_processor = None
pdf_converter = None

def get_window_manager():
    """Lazy initialization of window manager."""
    global window_manager
    if window_manager is None:
        logger.info("Initializing CrossPlatformWindowManager...")
        try:
            window_manager = CrossPlatformWindowManager()
            logger.info("CrossPlatformWindowManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CrossPlatformWindowManager: {e}")
            raise
    return window_manager

def get_image_processor():
    """Lazy initialization of image processor."""
    global image_processor
    if image_processor is None:
        logger.info("Initializing ImageProcessor...")
        image_processor = ImageProcessor()
        logger.info("ImageProcessor initialized successfully")
    return image_processor

def get_pdf_converter():
    """Lazy initialization of PDF converter."""
    global pdf_converter
    if pdf_converter is None:
        logger.info("Initializing PDFConverter...")
        pdf_converter = PDFConverter()
        logger.info("PDFConverter initialized successfully")
    return pdf_converter


@mcp.tool()
async def list_windows() -> str:
    """
    List all available windows for screenshot capture.
    
    Returns:
        JSON string containing list of windows with their IDs, titles, and properties.
    """
    try:
        wm = get_window_manager()
        windows = wm.list_windows()
        env_info = wm.get_environment_info()
        
        result = {
            "status": "success",
            "windows": windows,
            "count": len(windows),
            "environment": env_info
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to list windows: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "windows": [],
            "count": 0,
            "environment": {"error": "Could not determine environment"}
        })


@mcp.tool()
async def capture_window(window_id: str, output_path: Optional[str] = None) -> str:
    """
    Capture screenshot of a specific window.
    
    Args:
        window_id: Window ID to capture (from list_windows)
        output_path: Optional path to save the screenshot
    
    Returns:
        JSON string with capture results and file path.
    """
    try:
        wm = get_window_manager()
        captured_path = wm.capture_window(window_id, output_path)
        
        result = {
            "status": "success",
            "window_id": window_id,
            "output_path": captured_path,
            "file_exists": Path(captured_path).exists(),
            "file_size_mb": round(Path(captured_path).stat().st_size / (1024 * 1024), 2)
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to capture window {window_id}: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "window_id": window_id,
            "output_path": output_path
        })


@mcp.tool()
async def capture_full_screen(output_path: Optional[str] = None) -> str:
    """
    Capture screenshot of the entire screen.
    
    Args:
        output_path: Optional path to save the screenshot
    
    Returns:
        JSON string with capture results and file path.
    """
    try:
        wm = get_window_manager()
        captured_path = wm.capture_full_screen(output_path)
        
        result = {
            "status": "success",
            "output_path": captured_path,
            "file_exists": Path(captured_path).exists(),
            "file_size_mb": round(Path(captured_path).stat().st_size / (1024 * 1024), 2)
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to capture full screen: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "output_path": output_path
        })


@mcp.tool()
async def capture_document_pages(
    window_id: str, 
    page_count: int,
    output_dir: str = "captures",
    navigation_key: str = "Page_Down",
    delay_seconds: float = 1.0
) -> str:
    """
    Capture multiple pages from a document window with automatic navigation.
    
    Args:
        window_id: Window ID containing the document
        page_count: Number of pages to capture
        output_dir: Directory to save captured pages
        navigation_key: Key to press for navigation (Page_Down, Right, space)
        delay_seconds: Delay between navigation and capture
    
    Returns:
        JSON string with capture results and list of captured files.
    """
    try:
        # For multi-page capture, use the underlying manager if it supports it
        wm = get_window_manager()
        if hasattr(wm.manager, 'capture_multiple_pages'):
            captured_files = wm.manager.capture_multiple_pages(
                window_id=window_id,
                page_count=page_count,
                output_dir=output_dir,
                navigation_key=navigation_key,
                delay_seconds=delay_seconds
            )
        else:
            # Fallback: capture individual pages manually
            from pathlib import Path
            Path(output_dir).mkdir(exist_ok=True)
            
            captured_files = []
            for page_num in range(1, page_count + 1):
                output_path = f"{output_dir}/page_{page_num:03d}.png"
                captured_path = wm.capture_window(window_id, output_path)
                captured_files.append(captured_path)
                
                # Simple delay between captures (no navigation for Windows apps yet)
                if page_num < page_count:
                    time.sleep(delay_seconds)
        
        import os
        total_size = sum(os.path.getsize(f) for f in captured_files if os.path.exists(f))
        
        result = {
            "status": "success",
            "window_id": window_id,
            "pages_captured": len(captured_files),
            "output_directory": output_dir,
            "captured_files": captured_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to capture document pages: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "window_id": window_id,
            "page_count": page_count,
            "captured_files": []
        })


@mcp.tool()
async def process_images(
    image_dir: str,
    operations: List[str] = ["enhance"],
    ocr_language: str = "eng"
) -> str:
    """
    Process images in a directory with various operations.
    
    Args:
        image_dir: Directory containing images to process
        operations: List of operations (enhance, ocr, resize, deduplicate)
        ocr_language: Language for OCR processing (default: eng)
    
    Returns:
        JSON string with processing results.
    """
    try:
        ip = get_image_processor()
        results = ip.process_batch(image_dir, operations)
        
        # Add OCR language info to results if OCR was performed
        if "ocr" in operations:
            for ocr_result in results.get("ocr_results", []):
                ocr_result["language"] = ocr_language
        
        result = {
            "status": "success",
            "image_directory": image_dir,
            "operations": operations,
            "results": results
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to process images: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "image_directory": image_dir,
            "operations": operations
        })


@mcp.tool()
async def convert_to_pdf(
    image_paths: List[str],
    output_path: str,
    title: Optional[str] = None,
    sort_files: bool = True
) -> str:
    """
    Convert a list of images to a PDF document.
    
    Args:
        image_paths: List of image file paths to convert
        output_path: Path for the output PDF file
        title: Optional title for the PDF document
        sort_files: Whether to sort files by name before conversion
    
    Returns:
        JSON string with conversion results.
    """
    try:
        # Validate images first
        pc = get_pdf_converter()
        validation = pc.validate_images_for_pdf(image_paths)
        
        if not validation["valid_images"]:
            return json.dumps({
                "status": "error",
                "error": "No valid images found for conversion",
                "validation": validation
            })
        
        # Convert to PDF
        pdf_path = pc.images_to_pdf(
            validation["valid_images"],
            output_path,
            sort_files=sort_files,
            title=title
        )
        
        pdf_info = pc.get_pdf_info(pdf_path)
        
        result = {
            "status": "success",
            "input_images": len(image_paths),
            "valid_images": len(validation["valid_images"]),
            "output_pdf": pdf_path,
            "pdf_info": pdf_info,
            "validation": validation
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to convert to PDF: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "input_images": len(image_paths) if image_paths else 0,
            "output_pdf": output_path
        })


@mcp.tool()
async def directory_to_pdf(
    image_dir: str,
    output_path: str,
    title: Optional[str] = None,
    pattern: str = "*"
) -> str:
    """
    Convert all images in a directory to a PDF document.
    
    Args:
        image_dir: Directory containing images
        output_path: Path for the output PDF file
        title: Optional title for the PDF document
        pattern: File pattern to match (default: all files)
    
    Returns:
        JSON string with conversion results.
    """
    try:
        pc = get_pdf_converter()
        pdf_path = pc.directory_to_pdf(
            image_dir=image_dir,
            output_path=output_path,
            pattern=pattern,
            title=title
        )
        
        pdf_info = pc.get_pdf_info(pdf_path)
        
        result = {
            "status": "success",
            "input_directory": image_dir,
            "pattern": pattern,
            "output_pdf": pdf_path,
            "pdf_info": pdf_info
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to convert directory to PDF: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "input_directory": image_dir,
            "output_pdf": output_path
        })


@mcp.tool()
async def full_document_workflow(
    window_id: str,
    page_count: int,
    output_pdf: str,
    capture_dir: str = "temp_captures",
    title: Optional[str] = None,
    navigation_key: str = "Page_Down",
    delay_seconds: float = 1.0,
    process_images_flag: bool = True
) -> str:
    """
    Complete workflow: capture document pages, optionally process them, and convert to PDF.
    
    Args:
        window_id: Window ID containing the document
        page_count: Number of pages to capture
        output_pdf: Path for the final PDF file
        capture_dir: Temporary directory for captures
        title: Optional PDF title
        navigation_key: Key for page navigation
        delay_seconds: Delay between navigation and capture
        process_images_flag: Whether to enhance images before PDF conversion
    
    Returns:
        JSON string with complete workflow results.
    """
    try:
        workflow_results = {
            "status": "success",
            "steps": []
        }
        
        # Step 1: Capture pages
        logger.info("Step 1: Capturing document pages")
        wm = get_window_manager()
        if hasattr(wm.manager, 'capture_multiple_pages'):
            captured_files = wm.manager.capture_multiple_pages(
                window_id=window_id,
                page_count=page_count,
                output_dir=capture_dir,
                navigation_key=navigation_key,
                delay_seconds=delay_seconds
            )
        else:
            # Fallback for Windows applications
            Path(capture_dir).mkdir(exist_ok=True)
            captured_files = []
            for page_num in range(1, page_count + 1):
                output_path = f"{capture_dir}/page_{page_num:03d}.png"
                captured_path = wm.capture_window(window_id, output_path)
                captured_files.append(captured_path)
                
                if page_num < page_count:
                    time.sleep(delay_seconds)
        
        workflow_results["steps"].append({
            "step": "capture",
            "status": "success",
            "files_captured": len(captured_files),
            "output_directory": capture_dir
        })
        
        # Step 2: Process images (if requested)
        processed_files = captured_files
        if process_images_flag:
            logger.info("Step 2: Processing captured images")
            ip = get_image_processor()
            processing_results = ip.process_batch(
                capture_dir, 
                ["enhance"]
            )
            
            if processing_results["enhanced_files"]:
                processed_files = processing_results["enhanced_files"]
                
            workflow_results["steps"].append({
                "step": "processing",
                "status": "success",
                "enhanced_files": len(processing_results["enhanced_files"])
            })
        
        # Step 3: Convert to PDF
        logger.info("Step 3: Converting to PDF")
        pc = get_pdf_converter()
        pdf_path = pc.images_to_pdf(
            processed_files,
            output_pdf,
            sort_files=True,
            title=title or f"Document captured from window {window_id}"
        )
        
        pdf_info = pc.get_pdf_info(pdf_path)
        
        workflow_results["steps"].append({
            "step": "pdf_conversion",
            "status": "success",
            "output_pdf": pdf_path,
            "pdf_info": pdf_info
        })
        
        # Step 4: Cleanup temporary files (optional)
        import shutil
        try:
            if capture_dir.startswith("temp_"):
                shutil.rmtree(capture_dir)
                workflow_results["steps"].append({
                    "step": "cleanup",
                    "status": "success",
                    "cleaned_directory": capture_dir
                })
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup {capture_dir}: {cleanup_error}")
        
        workflow_results.update({
            "window_id": window_id,
            "pages_captured": len(captured_files),
            "final_pdf": pdf_path,
            "pdf_info": pdf_info
        })
        
        return json.dumps(workflow_results, indent=2)
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "window_id": window_id,
            "page_count": page_count,
            "output_pdf": output_pdf
        })


@mcp.tool()
async def check_system_dependencies() -> str:
    """
    Check if all required system dependencies are installed.
    
    Returns:
        JSON string with dependency check results.
    """
    try:
        missing_deps = check_dependencies()
        tesseract_available = check_tesseract()
        
        result = {
            "status": "success",
            "dependencies": {
                "wmctrl": "wmctrl" not in missing_deps,
                "xdotool": "xdotool" not in missing_deps,
                "tesseract": tesseract_available
            },
            "missing_dependencies": missing_deps,
            "install_commands": {
                "wmctrl": "sudo apt-get install wmctrl",
                "xdotool": "sudo apt-get install xdotool",
                "tesseract": "sudo apt-get install tesseract-ocr"
            }
        }
        
        if missing_deps or not tesseract_available:
            result["status"] = "warning"
            result["message"] = "Some dependencies are missing"
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to check dependencies: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        })


@mcp.tool()
async def debug_window_detection() -> str:
    """
    Comprehensive debugging information for window detection issues.
    
    Returns:
        JSON string with detailed diagnostics about PowerShell environment,
        process enumeration, and window detection capabilities.
    """
    try:
        wm = get_window_manager()
        
        # Get basic environment info
        env_info = wm.get_environment_info()
        
        debug_result = {
            "status": "success",
            "environment": env_info,
            "window_detection_debug": {}
        }
        
        # If using Windows manager, get detailed debug info
        if hasattr(wm.manager, 'debug_window_detection'):
            logger.info("Running comprehensive window detection debug...")
            debug_info = wm.manager.debug_window_detection()
            debug_result["window_detection_debug"] = debug_info
        else:
            debug_result["window_detection_debug"] = {
                "message": "Debug functionality only available for Windows Window Manager"
            }
        
        # Also include current window list for comparison
        current_windows = wm.list_windows()
        debug_result["current_window_list"] = current_windows
        debug_result["current_window_count"] = len(current_windows)
        
        logger.info(f"Debug complete: found {len(current_windows)} windows")
        
        return json.dumps(debug_result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to run debug window detection: {e}")
        return json.dumps({
            "status": "error", 
            "error": str(e),
            "environment": {"error": "Could not determine environment"}
        })


def main():
    """Run the MCP server."""
    logger.info("Starting Auto-Snap MCP Server")
    
    # Check dependencies on startup
    missing_deps = check_dependencies()
    if missing_deps:
        logger.warning(f"Missing system dependencies: {missing_deps}")
        logger.warning("Some functionality may not work properly")
    
    if not check_tesseract():
        logger.warning("Tesseract OCR not available - OCR functionality disabled")
    
    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()