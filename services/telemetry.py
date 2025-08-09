"""
OpenTelemetry integration
Metrics, tracing, and observability
"""

import logging
from typing import Optional, Dict, Any
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from services.config import get_settings

logger = logging.getLogger(__name__)

class TelemetryManager:
    """Manages OpenTelemetry setup and instrumentation"""
    
    def __init__(self):
        self.settings = get_settings()
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        self._initialized = False
    
    def setup(self):
        """Setup OpenTelemetry tracing and metrics"""
        if self._initialized:
            return
        
        try:
            if not self.settings.enable_telemetry:
                logger.info("Telemetry disabled")
                return
            
            # Create resource
            resource = Resource.create({
                "service.name": "mcp-google-calendar-server",
                "service.version": "1.0.0",
                "service.instance.id": f"calendar-server-{id(self)}",
            })
            
            # Setup tracing
            self._setup_tracing(resource)
            
            # Setup metrics
            self._setup_metrics(resource)
            
            # Setup automatic instrumentation
            self._setup_instrumentation()
            
            self._initialized = True
            logger.info("OpenTelemetry setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup telemetry: {e}")
            # Don't fail the application if telemetry setup fails
    
    def _setup_tracing(self, resource: Resource):
        """Setup distributed tracing"""
        if not self.settings.otel_exporter_endpoint:
            logger.warning("OTEL exporter endpoint not configured, tracing disabled")
            return
        
        try:
            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)
            
            # Create OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.settings.otel_exporter_endpoint,
                insecure=True  # Use secure=False for HTTPS
            )
            
            # Create span processor
            span_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(span_processor)
            
            # Get tracer
            self.tracer = trace.get_tracer(__name__)
            
            logger.info(f"Tracing configured with endpoint: {self.settings.otel_exporter_endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to setup tracing: {e}")
    
    def _setup_metrics(self, resource: Resource):
        """Setup metrics collection"""
        if not self.settings.otel_exporter_endpoint:
            return
        
        try:
            # Create metric exporter
            metric_exporter = OTLPMetricExporter(
                endpoint=self.settings.otel_exporter_endpoint,
                insecure=True
            )
            
            # Create metric reader
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=10000  # 10 seconds
            )
            
            # Create meter provider
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )
            metrics.set_meter_provider(meter_provider)
            
            # Get meter
            self.meter = metrics.get_meter(__name__)
            
            logger.info("Metrics configured")
            
        except Exception as e:
            logger.error(f"Failed to setup metrics: {e}")
    
    def _setup_instrumentation(self):
        """Setup automatic instrumentation"""
        try:
            # Instrument FastAPI
            FastAPIInstrumentor.instrument()
            
            # Instrument requests
            RequestsInstrumentor.instrument()
            
            logger.info("Automatic instrumentation configured")
            
        except Exception as e:
            logger.error(f"Failed to setup instrumentation: {e}")
    
    def get_tracer(self) -> Optional[trace.Tracer]:
        """Get tracer for manual instrumentation"""
        return self.tracer
    
    def get_meter(self) -> Optional[metrics.Meter]:
        """Get meter for custom metrics"""
        return self.meter
    
    def create_counter(self, name: str, description: str = "", unit: str = ""):
        """Create a counter metric"""
        if self.meter:
            return self.meter.create_counter(
                name=name,
                description=description,
                unit=unit
            )
        return None
    
    def create_histogram(self, name: str, description: str = "", unit: str = ""):
        """Create a histogram metric"""
        if self.meter:
            return self.meter.create_histogram(
                name=name,
                description=description,
                unit=unit
            )
        return None
    
    def create_gauge(self, name: str, description: str = "", unit: str = ""):
        """Create a gauge metric"""
        if self.meter:
            return self.meter.create_observable_gauge(
                name=name,
                description=description,
                unit=unit
            )
        return None

# Global telemetry manager
_telemetry_manager: Optional[TelemetryManager] = None

def setup_telemetry():
    """Setup global telemetry"""
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager()
    _telemetry_manager.setup()

def get_telemetry_manager() -> Optional[TelemetryManager]:
    """Get global telemetry manager"""
    return _telemetry_manager

def get_tracer() -> Optional[trace.Tracer]:
    """Get global tracer"""
    if _telemetry_manager:
        return _telemetry_manager.get_tracer()
    return None

def get_meter() -> Optional[metrics.Meter]:
    """Get global meter"""
    if _telemetry_manager:
        return _telemetry_manager.get_meter()
    return None

# Common metrics
class Metrics:
    """Common application metrics"""
    
    def __init__(self):
        self.telemetry = get_telemetry_manager()
        if self.telemetry:
            self.request_counter = self.telemetry.create_counter(
                "mcp_requests_total",
                "Total number of MCP requests"
            )
            
            self.request_duration = self.telemetry.create_histogram(
                "mcp_request_duration_seconds",
                "Duration of MCP requests in seconds"
            )
            
            self.calendar_operations = self.telemetry.create_counter(
                "calendar_operations_total",
                "Total number of calendar operations"
            )
            
            self.calendar_operation_duration = self.telemetry.create_histogram(
                "calendar_operation_duration_seconds",
                "Duration of calendar operations in seconds"
            )
            
            self.errors = self.telemetry.create_counter(
                "errors_total",
                "Total number of errors"
            )
    
    def increment_requests(self, tool_name: str = ""):
        """Increment request counter"""
        if self.request_counter:
            self.request_counter.add(1, {"tool": tool_name})
    
    def record_request_duration(self, duration: float, tool_name: str = ""):
        """Record request duration"""
        if self.request_duration:
            self.request_duration.record(duration, {"tool": tool_name})
    
    def increment_calendar_operations(self, operation: str):
        """Increment calendar operation counter"""
        if self.calendar_operations:
            self.calendar_operations.add(1, {"operation": operation})
    
    def record_calendar_operation_duration(self, duration: float, operation: str):
        """Record calendar operation duration"""
        if self.calendar_operation_duration:
            self.calendar_operation_duration.record(duration, {"operation": operation})
    
    def increment_errors(self, error_type: str = "", component: str = ""):
        """Increment error counter"""
        if self.errors:
            self.errors.add(1, {"type": error_type, "component": component})

# Global metrics instance
_metrics: Optional[Metrics] = None

def get_metrics() -> Optional[Metrics]:
    """Get global metrics instance"""
    global _metrics
    if _metrics is None and get_telemetry_manager():
        _metrics = Metrics()
    return _metrics