"""
PDF conversion utilities for converting images to PDF documents.
"""

import os
from typing import List, Optional
from pathlib import Path
import img2pdf
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class PDFConverter:
    """Handles conversion of images to PDF documents."""
    
    def __init__(self):
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
    
    def images_to_pdf(self, image_paths: List[str], output_path: str, 
                     sort_files: bool = True, title: Optional[str] = None) -> str:
        """
        Convert a list of images to a single PDF document.
        
        Args:
            image_paths: List of image file paths
            output_path: Output PDF file path
            sort_files: Whether to sort files by name
            title: PDF document title (optional)
        
        Returns:
            Path to created PDF file
        """
        try:
            # Filter existing files with supported formats
            valid_images = []
            for path in image_paths:
                if os.path.exists(path):
                    ext = Path(path).suffix.lower()
                    if ext in self.supported_formats:
                        valid_images.append(path)
                    else:
                        logger.warning(f"Unsupported format: {path}")
                else:
                    logger.warning(f"File not found: {path}")
            
            if not valid_images:
                raise ValueError("No valid images found")
            
            # Sort files if requested
            if sort_files:
                valid_images.sort()
            
            logger.info(f"Converting {len(valid_images)} images to PDF")
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Convert images to PDF
            with open(output_path, "wb") as f:
                # Create layout for each image
                layout_fun = img2pdf.get_layout_fun(
                    img2pdf.get_fixed_dpi_layout_fun(150)  # 150 DPI
                )
                
                f.write(img2pdf.convert(
                    valid_images,
                    layout_fun=layout_fun,
                    title=title or "Auto-Snap Captured Document"
                ))
            
            logger.info(f"PDF created: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to convert images to PDF: {e}")
            raise
    
    def directory_to_pdf(self, image_dir: str, output_path: str, 
                        pattern: str = "*", title: Optional[str] = None) -> str:
        """
        Convert all images in a directory to PDF.
        
        Args:
            image_dir: Directory containing images
            output_path: Output PDF file path
            pattern: File pattern to match (default: *)
            title: PDF document title (optional)
        
        Returns:
            Path to created PDF file
        """
        try:
            image_paths = []
            
            # Find all image files in directory
            for ext in self.supported_formats:
                image_paths.extend(Path(image_dir).glob(f"{pattern}{ext}"))
                image_paths.extend(Path(image_dir).glob(f"{pattern}{ext.upper()}"))
            
            image_paths = [str(p) for p in sorted(image_paths)]
            
            if not image_paths:
                raise ValueError(f"No image files found in {image_dir}")
            
            logger.info(f"Found {len(image_paths)} images in {image_dir}")
            
            return self.images_to_pdf(image_paths, output_path, sort_files=True, title=title)
            
        except Exception as e:
            logger.error(f"Failed to convert directory {image_dir} to PDF: {e}")
            raise
    
    def optimize_pdf(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """
        Optimize PDF file size (placeholder for future implementation).
        Currently just returns the original path.
        
        Args:
            pdf_path: Input PDF file path
            output_path: Output PDF file path (optional)
        
        Returns:
            Path to optimized PDF file
        """
        # For now, just return the original file
        # In the future, we could use PyPDF2 or similar for optimization
        if output_path and pdf_path != output_path:
            import shutil
            shutil.copy2(pdf_path, output_path)
            return output_path
        
        return pdf_path
    
    def get_pdf_info(self, pdf_path: str) -> dict:
        """
        Get basic information about a PDF file.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Dictionary with PDF information
        """
        try:
            file_size = os.path.getsize(pdf_path)
            
            info = {
                'path': pdf_path,
                'size_bytes': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'exists': os.path.exists(pdf_path)
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get PDF info for {pdf_path}: {e}")
            return {'path': pdf_path, 'error': str(e)}
    
    def validate_images_for_pdf(self, image_paths: List[str]) -> dict:
        """
        Validate images before PDF conversion.
        
        Args:
            image_paths: List of image file paths
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid_images': [],
            'invalid_images': [],
            'missing_files': [],
            'unsupported_formats': [],
            'total_size_mb': 0
        }
        
        for path in image_paths:
            if not os.path.exists(path):
                results['missing_files'].append(path)
                continue
            
            ext = Path(path).suffix.lower()
            if ext not in self.supported_formats:
                results['unsupported_formats'].append(path)
                continue
            
            try:
                # Try to open image to validate
                with Image.open(path) as img:
                    img.verify()
                
                file_size = os.path.getsize(path)
                results['total_size_mb'] += file_size / (1024 * 1024)
                results['valid_images'].append(path)
                
            except Exception as e:
                logger.warning(f"Invalid image {path}: {e}")
                results['invalid_images'].append(path)
        
        results['total_size_mb'] = round(results['total_size_mb'], 2)
        
        logger.info(f"Validation: {len(results['valid_images'])} valid, "
                   f"{len(results['invalid_images'])} invalid, "
                   f"{len(results['missing_files'])} missing, "
                   f"{len(results['unsupported_formats'])} unsupported")
        
        return results