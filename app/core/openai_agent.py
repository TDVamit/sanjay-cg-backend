import asyncio
import base64
from typing import List, Optional
from pydantic import BaseModel
from fastapi import HTTPException

from app.core.config import settings


class ATSScoreResponse(BaseModel):
    """Response model for ATS scoring"""
    Category: List[str]
    Score: List[int]
    Comments: List[str]


class OpenAIAgent:
    """OpenAI agent for processing images and text"""
    
    def __init__(self):
        self.client = None
        self.model = settings.openai_model
        self._initialized = False
        self._initialization_error = None
    
    def _initialize_client(self):
        """Initialize OpenAI client lazily with better error handling"""
        if self._initialized:
            return
            
        try:
            # Check if API key is configured
            if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key":
                raise ValueError("OpenAI API key not configured")
            
            from openai import AsyncOpenAI
            
            # Initialize with minimal parameters to avoid compatibility issues
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,  # Set explicit timeout
            )
            self._initialized = True
            self._initialization_error = None
            print("✅ OpenAI client initialized successfully")
            
        except Exception as e:
            self._initialization_error = str(e)
            print(f"⚠️ OpenAI client initialization failed: {e}")
            # Don't raise here, let the calling method handle it
    
    async def send_images(self, image_paths: List[str], prompt: str, response_model: BaseModel = None):
        """
        Send images to OpenAI for analysis
        
        Args:
            image_paths: List of image file paths
            prompt: Text prompt for the analysis
            response_model: Pydantic model for structured response
        
        Returns:
            Parsed response from OpenAI
        """
        # Initialize client if not already done
        self._initialize_client()
        
        if not self.client or self._initialization_error:
            error_msg = self._initialization_error or "OpenAI client not available"
            raise HTTPException(
                status_code=503,
                detail=f"OpenAI service unavailable: {error_msg}"
            )
        
        try:
            # Encode images concurrently
            encoding_tasks = [self._encode_image(image_path) for image_path in image_paths]
            encoded_images = await asyncio.gather(*encoding_tasks)
            
            # Build content array
            content = [{"type": "text", "text": f"{prompt}"}]
            for encoded_image in encoded_images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}",
                        "detail": "high",
                    },
                })
            
            # Make the API call with proper error handling
            try:
                response_data = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=16384,
                    response_format=response_model if response_model else {"type": "json_object"},
                )
                
                response_data = response_data.to_dict()
                return response_data["choices"][0]["message"]["content"]
                
            except Exception as api_error:
                # If structured parsing fails, try regular completion
                print(f"⚠️ Structured completion failed, trying regular completion: {api_error}")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=16384,
                )
                
                return response.choices[0].message.content
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OpenAI API error: {e}")
    
    async def analyze_resume_ats(self, image_paths: List[str]) -> ATSScoreResponse:
        """
        Analyze resume images for ATS scoring
        
        Args:
            image_paths: List of resume image file paths
        
        Returns:
            ATS score analysis
        """
        prompt = '''You are a helpful assistant that returns ATS score of the resume given in this specific JSON format:
{
    "Category": [], 
    "Score": [], 
    "Comments": []
}

Where:
- Category: List of categories in which resume is scored (e.g., "Format", "Keywords", "Experience", "Education", "Skills", "Contact Info")
- Score: Score for each category out of 10
- Comments: List of comments for each category explaining the score

Analyze the resume comprehensively for ATS compatibility, considering:
1. Format and structure
2. Keyword optimization
3. Experience relevance
4. Education presentation
5. Skills section
6. Contact information clarity
7. Overall readability for ATS systems

Provide constructive feedback in each comment.'''
        
        try:
            print(f"🤖 Starting ATS analysis with model: {self.model}")
            result = await self.send_images(image_paths, prompt)
            
            if not result:
                raise ValueError("Empty response from OpenAI")
            
            print(f"📊 OpenAI response received: {result[:200]}...")
            
            # Parse the JSON response
            import json
            try:
                parsed_result = json.loads(result)
                print(f"✅ JSON parsed successfully: {list(parsed_result.keys())}")
                return ATSScoreResponse(**parsed_result)
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON parsing failed: {json_error}")
                print(f"Raw response: {result}")
                raise ValueError(f"Invalid JSON response from OpenAI: {json_error}")
            except Exception as validation_error:
                print(f"❌ Pydantic validation failed: {validation_error}")
                print(f"Parsed data: {parsed_result}")
                raise ValueError(f"Response validation failed: {validation_error}")
                
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            print(f"❌ ATS analysis failed: {error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=f"ATS analysis failed: {error_msg}"
            )
    
    async def _encode_image(self, image_path: str) -> str:
        """
        Encode image to base64 string
        
        Args:
            image_path: Path to image file
        
        Returns:
            Base64 encoded image string
        """
        try:
            import aiofiles
            async with aiofiles.open(image_path, "rb") as image_file:
                image_data = await image_file.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image encoding failed: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available"""
        try:
            # Quick availability check without full initialization
            return (
                settings.openai_api_key and 
                settings.openai_api_key != "your-openai-api-key"
            )
        except Exception:
            return False
    
    async def close(self):
        """Properly close the OpenAI client"""
        if self.client and hasattr(self.client, 'close'):
            try:
                await self.client.close()
                print("✅ OpenAI client closed properly")
            except Exception as e:
                print(f"⚠️ Error closing OpenAI client: {e}")

    async def chat_completion(self, prompt: str) -> str:
        """
        Simple chat completion with OpenAI
        
        Args:
            prompt: Text prompt for the chat completion
        
        Returns:
            OpenAI's text response
        """
        # Initialize client if not already done
        self._initialize_client()
        
        if not self.client or self._initialization_error:
            error_msg = self._initialization_error or "OpenAI client not available"
            raise HTTPException(
                status_code=503,
                detail=f"OpenAI service unavailable: {error_msg}"
            )
        
        try:
            
            response = await self.client.chat.completions.create(
                model='gpt-4.1-mini',
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            print(f"✅ Chat completion successful: {len(result)} characters")
            
            return result
            
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            print(f"❌ Chat completion failed: {error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=f"Chat completion failed: {error_msg}"
            )


# Global OpenAI agent instance
openai_agent = OpenAIAgent() 