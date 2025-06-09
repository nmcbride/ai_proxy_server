"""
Pydantic models for OpenAI API request/response schemas
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model"""

    role: Literal["system", "user", "assistant", "tool", "function"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


class ChatCompletionRequest(BaseModel):
    """Chat completion request model"""

    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(default=1, ge=1, le=128)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, Any]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    top_k: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    """Chat completion response model"""

    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None
    system_fingerprint: Optional[str] = None


class CompletionRequest(BaseModel):
    """Text completion request model"""

    model: str
    prompt: Union[str, List[str]]
    suffix: Optional[str] = None
    max_tokens: Optional[int] = Field(default=16, ge=1)
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(default=1, ge=1, le=128)
    stream: Optional[bool] = False
    logprobs: Optional[int] = Field(default=None, ge=0, le=5)
    echo: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    best_of: Optional[int] = Field(default=1, ge=1, le=20)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


class CompletionResponse(BaseModel):
    """Text completion response model"""

    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None


class EmbeddingRequest(BaseModel):
    """Embedding request model"""

    model: str
    input: Union[str, List[str], List[int], List[List[int]]]
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None
    user: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Embedding response model"""

    object: str
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, Any]


class ModelInfo(BaseModel):
    """Model information"""

    id: str
    object: str
    created: int
    owned_by: str
    permission: Optional[List[Dict[str, Any]]] = None
    root: Optional[str] = None
    parent: Optional[str] = None


class ModelListResponse(BaseModel):
    """Model list response"""

    object: str
    data: List[ModelInfo]


class ErrorDetail(BaseModel):
    """Error detail model"""

    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model"""

    error: ErrorDetail


class ModerationRequest(BaseModel):
    """Moderation request model"""

    input: Union[str, List[str]]
    model: Optional[str] = "text-moderation-latest"


class ModerationResponse(BaseModel):
    """Moderation response model"""

    id: str
    model: str
    results: List[Dict[str, Any]]


class ImageGenerationRequest(BaseModel):
    """Image generation request model"""

    model: Optional[str] = "dall-e-2"
    prompt: str
    n: Optional[int] = Field(default=1, ge=1, le=10)
    quality: Optional[str] = "standard"
    response_format: Optional[str] = "url"
    size: Optional[str] = "1024x1024"
    style: Optional[str] = "vivid"
    user: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    """Image generation response model"""

    created: int
    data: List[Dict[str, Any]]


class AudioSpeechRequest(BaseModel):
    """Audio speech request model"""

    model: str
    input: str
    voice: str
    response_format: Optional[str] = "mp3"
    speed: Optional[float] = Field(default=1.0, ge=0.25, le=4.0)


class AudioTranscriptionRequest(BaseModel):
    """Audio transcription request model"""

    file: Any  # File upload
    model: str
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Optional[str] = "json"
    temperature: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)
    timestamp_granularities: Optional[List[str]] = None


class AudioTranscriptionResponse(BaseModel):
    """Audio transcription response model"""

    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[List[Dict[str, Any]]] = None
    segments: Optional[List[Dict[str, Any]]] = None


class AudioTranslationRequest(BaseModel):
    """Audio translation request model"""

    file: Any  # File upload
    model: str
    prompt: Optional[str] = None
    response_format: Optional[str] = "json"
    temperature: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)


class AudioTranslationResponse(BaseModel):
    """Audio translation response model"""

    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
