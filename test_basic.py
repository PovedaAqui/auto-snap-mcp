"""
Basic tests for Auto-Snap MCP server functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
from PIL import Image
import asyncio

from pdf_utils import PDFConverter
from processing import ImageProcessor, check_tesseract
from capture import check_dependencies


class TestPDFConverter:
    """Test PDFConverter basic functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.pdf_converter = PDFConverter()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_image(self, filename: str, size: tuple = (100, 100)) -> str:
        """Create a test image file."""
        image_path = os.path.join(self.temp_dir, filename)
        img = Image.new('RGB', size, color='red')
        img.save(image_path)
        return image_path
    
    def test_supported_formats(self):
        """Test that supported formats are correctly defined."""
        expected_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        assert self.pdf_converter.supported_formats == expected_formats
    
    def test_images_to_pdf_single_image(self):
        """Test converting single image to PDF."""
        # Create test image
        image_path = self.create_test_image('test.png')
        output_path = os.path.join(self.temp_dir, 'output.pdf')
        
        # Convert to PDF
        result_path = self.pdf_converter.images_to_pdf([image_path], output_path)
        
        # Verify PDF was created
        assert os.path.exists(result_path)
        assert result_path == output_path
    
    def test_images_to_pdf_multiple_images(self):
        """Test converting multiple images to PDF."""
        # Create test images
        image1 = self.create_test_image('test1.png')
        image2 = self.create_test_image('test2.jpg')
        output_path = os.path.join(self.temp_dir, 'multi.pdf')
        
        # Convert to PDF
        result_path = self.pdf_converter.images_to_pdf([image1, image2], output_path)
        
        # Verify PDF was created
        assert os.path.exists(result_path)
    
    def test_images_to_pdf_invalid_files(self):
        """Test handling of invalid image files."""
        invalid_path = os.path.join(self.temp_dir, 'nonexistent.png')
        output_path = os.path.join(self.temp_dir, 'output.pdf')
        
        # Should raise ValueError for no valid images
        with pytest.raises(ValueError, match="No valid images found"):
            self.pdf_converter.images_to_pdf([invalid_path], output_path)


class TestImageProcessor:
    """Test ImageProcessor basic functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.processor = ImageProcessor()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_image(self, filename: str, size: tuple = (100, 100)) -> str:
        """Create a test image file."""
        image_path = os.path.join(self.temp_dir, filename)
        img = Image.new('RGB', size, color='blue')
        img.save(image_path)
        return image_path
    
    def test_supported_formats(self):
        """Test that supported formats are correctly defined."""
        expected_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
        assert self.processor.supported_formats == expected_formats
    
    def test_enhance_image(self):
        """Test image enhancement functionality."""
        # Create test image
        image_path = self.create_test_image('test.png')
        
        # Enhance image
        enhanced_path = self.processor.enhance_image(image_path)
        
        # Verify enhanced image exists
        assert os.path.exists(enhanced_path)
        
        # Verify it's different from original
        assert enhanced_path != image_path


class TestDependencies:
    """Test dependency checking functions."""
    
    def test_check_tesseract(self):
        """Test tesseract dependency check."""
        # Should return boolean
        result = check_tesseract()
        assert isinstance(result, bool)
    
    def test_check_dependencies(self):
        """Test system dependencies check."""
        # Should return list of missing dependencies
        result = check_dependencies()
        assert isinstance(result, list)


class TestMCPServer:
    """Test MCP server initialization."""
    
    def test_server_imports(self):
        """Test that server module can be imported."""
        # This tests basic module structure
        import server
        assert hasattr(server, 'mcp')
        assert hasattr(server, 'window_capture')
        assert hasattr(server, 'image_processor')
        assert hasattr(server, 'pdf_converter')
    
    @pytest.mark.asyncio
    async def test_list_windows_tool(self):
        """Test list_windows MCP tool."""
        import server
        
        # Test that the function is registered as an MCP tool
        result = await server.list_windows()
        assert isinstance(result, str)
        
        # Should return valid JSON
        import json
        data = json.loads(result)
        assert 'status' in data