import os
import tempfile
from typing import List
from pdf2image import convert_from_path
from PIL import Image
from fastapi import HTTPException, UploadFile
import aiofiles


class PDFProcessor:
    """Utility for processing PDF files and converting them to images"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.image_quality = 300  # DPI for image conversion
    
    async def save_uploaded_file(self, upload_file: UploadFile) -> str:
        """
        Save uploaded file to temporary directory
        
        Args:
            upload_file: FastAPI UploadFile object
        
        Returns:
            Path to saved file
        """
        try:
            # Create a temporary file
            temp_file_path = os.path.join(
                self.temp_dir, 
                f"temp_{upload_file.filename}"
            )
            
            # Save the uploaded file
            async with aiofiles.open(temp_file_path, "wb") as temp_file:
                content = await upload_file.read()
                await temp_file.write(content)
            
            return temp_file_path
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File save failed: {e}")
    
    def pdf_to_images(self, pdf_path: str) -> List[str]:
        """
        Convert PDF to images
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of image file paths
        """
        try:
            # Convert PDF to images
            images = convert_from_path(
                pdf_path,
                dpi=self.image_quality,
                fmt='jpeg'
            )
            
            image_paths = []
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            
            for i, image in enumerate(images):
                image_path = os.path.join(
                    self.temp_dir,
                    f"{base_name}_page_{i+1}.jpg"
                )
                
                # Save image with high quality
                image.save(image_path, "JPEG", quality=95, optimize=True)
                image_paths.append(image_path)
            
            return image_paths
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {e}")
    
    async def process_pdf_upload(self, upload_file: UploadFile) -> List[str]:
        """
        Process uploaded PDF file and convert to images
        
        Args:
            upload_file: Uploaded PDF file
        
        Returns:
            List of image file paths
        """
        # Validate file type
        if not upload_file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="File must be a PDF"
            )
        
        try:
            # Save uploaded file
            pdf_path = await self.save_uploaded_file(upload_file)
            
            # Convert to images
            image_paths = self.pdf_to_images(pdf_path)
            
            # Clean up the PDF file
            self.cleanup_file(pdf_path)
            
            return image_paths
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF processing failed: {e}")
    
    def cleanup_files(self, file_paths: List[str]):
        """
        Clean up temporary files
        
        Args:
            file_paths: List of file paths to delete
        """
        for file_path in file_paths:
            self.cleanup_file(file_path)
    
    def cleanup_file(self, file_path: str):
        """
        Clean up a single temporary file
        
        Args:
            file_path: Path to file to delete
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Warning: Failed to cleanup file {file_path}: {e}")


# Global PDF processor instance
pdf_processor = PDFProcessor() 