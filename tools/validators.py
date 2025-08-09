"""
Input validation and schema enforcement
JSON schema validation for tool arguments
"""

from pydantic import ValidationError
from typing import Dict, Any, Type, Union
import logging
from .schemas import (
    CreateEventSchema,
    UpdateEventSchema, 
    DeleteEventSchema,
    FreeBusyQuerySchema,
    ToolResponse
)

logger = logging.getLogger(__name__)

class ValidationException(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message: str, errors: list = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)

class ToolValidator:
    """Validates tool arguments against Pydantic schemas"""
    
    SCHEMA_MAP: Dict[str, Type] = {
        "create_event": CreateEventSchema,
        "update_event": UpdateEventSchema,
        "delete_event": DeleteEventSchema,
        "freebusy_query": FreeBusyQuerySchema
    }
    
    @classmethod
    def validate_tool_args(cls, tool_name: str, arguments: Dict[str, Any]) -> Union[CreateEventSchema, UpdateEventSchema, DeleteEventSchema, FreeBusyQuerySchema]:
        """
        Validate tool arguments against the appropriate schema
        
        Args:
            tool_name: Name of the tool to validate
            arguments: Arguments to validate
            
        Returns:
            Validated schema instance
            
        Raises:
            ValidationException: If validation fails
        """
        schema_class = cls.SCHEMA_MAP.get(tool_name)
        if not schema_class:
            raise ValidationException(f"Unknown tool: {tool_name}")
        
        try:
            validated_args = schema_class(**arguments)
            logger.debug(f"Successfully validated arguments for tool: {tool_name}")
            return validated_args
            
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append({
                    "field": field,
                    "message": error["msg"],
                    "type": error["type"]
                })
            
            error_message = f"Validation failed for tool '{tool_name}'"
            logger.error(f"{error_message}: {error_details}")
            
            raise ValidationException(error_message, error_details)
    
    @classmethod 
    def get_tool_schema(cls, tool_name: str) -> Dict[str, Any]:
        """
        Get JSON schema for a tool
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            JSON schema dictionary
        """
        schema_class = cls.SCHEMA_MAP.get(tool_name)
        if not schema_class:
            raise ValidationException(f"Unknown tool: {tool_name}")
        
        return schema_class.schema()
    
    @classmethod
    def get_all_schemas(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get all tool schemas
        
        Returns:
            Dictionary mapping tool names to their schemas
        """
        schemas = {}
        for tool_name, schema_class in cls.SCHEMA_MAP.items():
            schemas[tool_name] = schema_class.schema()
        return schemas
    
    @classmethod
    def create_error_response(cls, message: str, error: str = None) -> ToolResponse:
        """
        Create a standardized error response
        
        Args:
            message: Error message
            error: Detailed error information
            
        Returns:
            ToolResponse with error details
        """
        return ToolResponse(
            success=False,
            message=message,
            error=error
        )
    
    @classmethod
    def create_success_response(cls, message: str, data: Dict[str, Any] = None) -> ToolResponse:
        """
        Create a standardized success response
        
        Args:
            message: Success message
            data: Response data
            
        Returns:
            ToolResponse with success details
        """
        return ToolResponse(
            success=True,
            message=message,
            data=data
        )