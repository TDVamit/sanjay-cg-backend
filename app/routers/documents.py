from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import os
import tempfile
from pydantic import BaseModel

from app.core.openai_agent import openai_agent, ATSScoreResponse
from app.core.pdf_processor import pdf_processor
from app.core.security import get_current_user, get_current_user_basic
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["Document Processing"])


class ChatRequest(BaseModel):
    """Request model for chat completion"""
    prompt: str


class ChatResponse(BaseModel):
    """Response model for chat completion"""
    response: str
    model_used: str
    
    class Config:
        protected_namespaces = ()


@router.post("/chat", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Simple chat completion with OpenAI (Bearer Token Auth)
    
    Send a text prompt to OpenAI and get a response.
    Requires JWT Bearer token authentication.
    
    - **prompt**: Your text prompt/question for the AI
    
    Returns the AI's response.
    """
    try:
        
        # Check if OpenAI is available
        if not openai_agent.is_available():
            raise HTTPException(
                status_code=503,
                detail="OpenAI service is not configured. Please set OPENAI_API_KEY environment variable."
            )
        
        # Get response from OpenAI
        response = await openai_agent.chat_completion(request.prompt)
        
        return ChatResponse(
            response=response,
            model_used=openai_agent.model
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Chat completion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat completion failed: {str(e)}"
        )


@router.post("/chat-basic", response_model=ChatResponse)
async def chat_completion_basic_auth(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_basic)
):
    """
    Simple chat completion with OpenAI (Basic Auth)
    
    Send a text prompt to OpenAI and get a response.
    Uses Basic Authentication (username/password).
    
    - **prompt**: Your text prompt/question for the AI
    
    In Swagger UI, click "Authorize" and use "BasicAuth" with your username and password.
    
    Returns the AI's response.
    """
    try:
        print(f"💬 Chat request (Basic Auth) from user: {current_user.username}")
        print(f"📝 Prompt length: {len(request.prompt)} characters")
        
        # Check if OpenAI is available
        if not openai_agent.is_available():
            raise HTTPException(
                status_code=503,
                detail="OpenAI service is not configured. Please set OPENAI_API_KEY environment variable."
            )
        
        # Get response from OpenAI
        response = await openai_agent.chat_completion(request.prompt)
        
        return ChatResponse(
            response=response,
            model_used=openai_agent.model
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Chat completion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat completion failed: {str(e)}"
        )


@router.post("/analyze-resume", response_model=ATSScoreResponse)
async def analyze_resume_pdf(
    file: UploadFile = File(..., description="Resume PDF file to analyze"),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze a resume PDF for ATS (Applicant Tracking System) compatibility
    
    This endpoint:
    1. Accepts a PDF file upload
    2. Converts PDF pages to high-quality images
    3. Sends images to OpenAI for analysis
    4. Returns structured ATS scoring
    
    **Authentication required**: Include JWT token in Authorization header
    
    **File Requirements**:
    - Format: PDF only
    - Content: Resume/CV document
    - Size: Reasonable file size (will be converted to images)
    
    **Returns**:
    - Category: List of scored categories (Format, Keywords, Experience, etc.)
    - Score: Numerical scores (0-10) for each category
    - Comments: Detailed feedback for each category
    """
    
    # Check if OpenAI service is available
    if not openai_agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="OpenAI service is not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    image_paths = []
    
    try:
        # Process the uploaded PDF
        print(f"📄 Processing PDF upload from user: {current_user.username}")
        image_paths = await pdf_processor.process_pdf_upload(file)
        
        if not image_paths:
            raise HTTPException(
                status_code=400,
                detail="Failed to convert PDF to images. PDF may be corrupted or empty."
            )
        
        print(f"🖼️ Converted PDF to {len(image_paths)} images")
        
        # Analyze with OpenAI
        print("🤖 Analyzing resume with OpenAI...")
        ats_score = await openai_agent.analyze_resume_ats(image_paths)
        
        print(f"✅ Analysis complete for user: {current_user.username}")
        return ats_score
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Resume analysis failed: {str(e)}"
        )
    finally:
        # Clean up temporary image files
        if image_paths:
            pdf_processor.cleanup_files(image_paths)
            print(f"🗑️ Cleaned up {len(image_paths)} temporary files")


@router.post("/pdf-to-images")
async def convert_pdf_to_images(
    file: UploadFile = File(..., description="PDF file to convert"),
    current_user: User = Depends(get_current_user)
):
    """
    Convert a PDF file to images (for testing purposes)
    
    **Authentication required**: Include JWT token in Authorization header
    
    Returns information about the converted images without processing them through OpenAI.
    """
    
    image_paths = []
    
    try:
        print(f"📄 Converting PDF to images for user: {current_user.username}")
        image_paths = await pdf_processor.process_pdf_upload(file)
        
        if not image_paths:
            raise HTTPException(
                status_code=400,
                detail="Failed to convert PDF to images"
            )
        
        # Return information about the converted images
        result = {
            "message": f"Successfully converted PDF to {len(image_paths)} images",
            "page_count": len(image_paths),
            "image_info": [
                {
                    "page": i + 1,
                    "filename": image_path.split('/')[-1],
                    "size_mb": round(os.path.getsize(image_path) / (1024 * 1024), 2)
                }
                for i, image_path in enumerate(image_paths)
            ]
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF conversion failed: {str(e)}"
        )
    finally:
        # Clean up temporary files
        if image_paths:
            pdf_processor.cleanup_files(image_paths)


@router.get("/health")
async def document_service_health():
    """
    Health check for document processing service
    
    Checks if all required dependencies are available.
    """
    services = {}
    
    try:
        import pdf2image
        services["pdf2image"] = "available"
    except ImportError:
        services["pdf2image"] = "missing"
    
    try:
        import PIL
        services["PIL"] = "available"
    except ImportError:
        services["PIL"] = "missing"
        
    try:
        import openai
        services["openai"] = "available"
    except ImportError:
        services["openai"] = "missing"
    
    # Check OpenAI configuration
    openai_configured = openai_agent.is_available()
    services["openai_configured"] = "yes" if openai_configured else "no"
    
    # Determine overall status
    required_services = ["pdf2image", "PIL", "openai"]
    all_available = all(services.get(service) == "available" for service in required_services)
    
    status = "healthy" if all_available else "degraded"
    if not openai_configured:
        status = "degraded"
    
    return {
        "status": status,
        "services": services,
        "message": "Document processing service status",
        "notes": {
            "pdf_processing": "available" if services.get("pdf2image") == "available" else "unavailable",
            "ai_analysis": "available" if openai_configured else "unavailable - configure OPENAI_API_KEY"
        }
    } 