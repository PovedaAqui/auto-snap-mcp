"""
Image processing utilities for screenshot enhancement and OCR.
"""

import os
from typing import List, Optional, Dict
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import hashlib
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image processing and OCR operations."""
    
    def __init__(self):
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
    
    def enhance_image(self, image_path: str, output_path: Optional[str] = None) -> str:
        """
        Enhance image quality for better OCR results.
        
        Args:
            image_path: Path to input image
            output_path: Path for enhanced image (optional)
        
        Returns:
            Path to enhanced image
        """
        try:
            with Image.open(image_path) as img:
                # Convert to grayscale for better OCR
                if img.mode != 'L':
                    img = img.convert('L')
                
                # Enhance contrast
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
                
                # Enhance sharpness
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(2.0)
                
                # Apply slight blur to reduce noise
                img = img.filter(ImageFilter.MedianFilter(size=3))
                
                if output_path is None:
                    name, ext = os.path.splitext(image_path)
                    output_path = f"{name}_enhanced{ext}"
                
                img.save(output_path)
                logger.info(f"Image enhanced: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"Failed to enhance image {image_path}: {e}")
            raise
    
    def extract_text(self, image_path: str, language: str = 'eng') -> str:
        """
        Extract text from image using OCR.
        
        Args:
            image_path: Path to image file
            language: OCR language (default: 'eng')
        
        Returns:
            Extracted text
        """
        try:
            # Enhance image first for better OCR
            enhanced_path = self.enhance_image(image_path)
            
            # Extract text using pytesseract
            text = pytesseract.image_to_string(
                Image.open(enhanced_path),
                lang=language,
                config='--psm 6'  # Assume uniform block of text
            )
            
            # Clean up temporary enhanced image
            if enhanced_path != image_path:
                try:
                    os.remove(enhanced_path)
                except OSError:
                    pass
            
            logger.info(f"Text extracted from {image_path}: {len(text)} characters")
            return text.strip()
            
        except Exception as e:
            logger.error(f"Failed to extract text from {image_path}: {e}")
            raise
    
    def get_image_hash(self, image_path: str) -> str:
        """
        Calculate hash of image for duplicate detection.
        
        Args:
            image_path: Path to image file
        
        Returns:
            MD5 hash of image
        """
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {image_path}: {e}")
            return ""
    
    def find_duplicates(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Find duplicate images in a list of image paths.
        
        Args:
            image_paths: List of image file paths
        
        Returns:
            Dictionary mapping hash to list of duplicate file paths
        """
        hash_to_files = {}
        
        for image_path in image_paths:
            if not os.path.exists(image_path):
                continue
                
            image_hash = self.get_image_hash(image_path)
            if image_hash:
                if image_hash not in hash_to_files:
                    hash_to_files[image_hash] = []
                hash_to_files[image_hash].append(image_path)
        
        # Return only groups with duplicates
        duplicates = {h: files for h, files in hash_to_files.items() if len(files) > 1}
        
        if duplicates:
            logger.info(f"Found {len(duplicates)} groups of duplicate images")
        
        return duplicates
    
    def resize_image(self, image_path: str, max_width: int = 1920, 
                    max_height: int = 1080, output_path: Optional[str] = None) -> str:
        """
        Resize image while maintaining aspect ratio.
        
        Args:
            image_path: Path to input image
            max_width: Maximum width
            max_height: Maximum height
            output_path: Output path (optional)
        
        Returns:
            Path to resized image
        """
        try:
            with Image.open(image_path) as img:
                # Calculate new size maintaining aspect ratio
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                if output_path is None:
                    name, ext = os.path.splitext(image_path)
                    output_path = f"{name}_resized{ext}"
                
                img.save(output_path, optimize=True, quality=90)
                logger.info(f"Image resized: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"Failed to resize image {image_path}: {e}")
            raise
    
    def process_batch(self, image_dir: str, operations: List[str] = None) -> Dict[str, List[str]]:
        """
        Process a batch of images in a directory.
        
        Args:
            image_dir: Directory containing images
            operations: List of operations ('enhance', 'ocr', 'resize', 'deduplicate')
        
        Returns:
            Dictionary with results of operations
        """
        if operations is None:
            operations = ['enhance']
        
        image_paths = []
        for ext in self.supported_formats:
            image_paths.extend(Path(image_dir).glob(f"*{ext}"))
            image_paths.extend(Path(image_dir).glob(f"*{ext.upper()}"))
        
        image_paths = [str(p) for p in image_paths]
        
        results = {
            'processed_files': [],
            'enhanced_files': [],
            'ocr_results': [],
            'resized_files': [],
            'duplicates': {}
        }
        
        try:
            # Find duplicates first
            if 'deduplicate' in operations:
                results['duplicates'] = self.find_duplicates(image_paths)
            
            for image_path in image_paths:
                results['processed_files'].append(image_path)
                
                try:
                    # Enhance image
                    if 'enhance' in operations:
                        enhanced_path = self.enhance_image(image_path)
                        results['enhanced_files'].append(enhanced_path)
                    
                    # Extract text
                    if 'ocr' in operations:
                        text = self.extract_text(image_path)
                        results['ocr_results'].append({
                            'file': image_path,
                            'text': text
                        })
                    
                    # Resize image
                    if 'resize' in operations:
                        resized_path = self.resize_image(image_path)
                        results['resized_files'].append(resized_path)
                        
                except Exception as e:
                    logger.error(f"Failed to process {image_path}: {e}")
                    continue
            
            logger.info(f"Batch processed {len(results['processed_files'])} images")
            return results
            
        except Exception as e:
            logger.error(f"Failed to process batch in {image_dir}: {e}")
            raise


def check_tesseract() -> bool:
    """
    Check if Tesseract OCR is installed and accessible.
    
    Returns:
        True if Tesseract is available, False otherwise
    """
    try:
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Tesseract check timed out")
        
        # Set timeout for tesseract check
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        
        try:
            pytesseract.get_tesseract_version()
            return True
        finally:
            signal.alarm(0)  # Cancel the alarm
            
    except (TimeoutError, Exception) as e:
        logger.error(f"Tesseract not available: {e}")
        return False