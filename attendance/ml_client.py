"""ML Service client for face recognition API calls."""
import requests
import json
from io import BytesIO
from django.conf import settings
from typing import List, Tuple, Union

ML_SERVICE_URL = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8000')
ML_REGISTER_ENDPOINT = f'{ML_SERVICE_URL}/register-embedding'
ML_ATTENDANCE_ENDPOINT = f'{ML_SERVICE_URL}/process-attendance'
ML_CONTINUOUS_DETECTION_ENDPOINT = f'{ML_SERVICE_URL}/continuous-detection'


class MLServiceError(Exception):
    """Custom exception for ML service errors"""
    pass


def _prepare_image_upload(image_file) -> Union[BytesIO, tuple]:
    """Ensure file-like image payloads are rewound and sent as multipart JPEG."""
    if hasattr(image_file, 'seek'):
        image_file.seek(0)
    if isinstance(image_file, BytesIO):
        return ('frame.jpg', image_file, 'image/jpeg')
    return image_file


def register_face_embedding(image_file) -> Tuple[List[float], float]:
    """Call ML service to extract face embedding."""
    try:
        files = {'image': image_file}
        response = requests.post(
            ML_REGISTER_ENDPOINT,
            files=files,
            timeout=30
        )
        
        if response.status_code != 200:
            error_detail = response.json().get('detail', 'Unknown error')
            raise MLServiceError(f"ML Service Error: {error_detail}")
        
        data = response.json()
        embedding = data.get('embedding')
        quality_score = data.get('quality_score', data.get('confidence', 0.0))
        
        if not embedding:
            raise MLServiceError("No embedding returned from ML service")
        
        return embedding, quality_score
    
    except requests.exceptions.RequestException as e:
        raise MLServiceError(f"Failed to connect to ML service: {str(e)}")


def process_attendance(
    image_file,
    stored_embeddings: List[List[float]],
    student_ids: List[str],
    session_id: str = ""
) -> dict:
    """
    Call ML service to match a captured face against stored embeddings.
    
    Args:
        image_file: Django UploadedFile object
        stored_embeddings: List of embedding vectors from database
        student_ids: List of corresponding student IDs
        session_id: Optional session ID for reference
    
    Returns:
        dict with keys: student_id, confidence, distance_to_nearest, status
    
    Raises:
        MLServiceError: If ML service fails to process attendance
    """
    try:
        files = {'image': _prepare_image_upload(image_file)}
        data = {
            'session_id': session_id,
            'stored_vectors': json.dumps(stored_embeddings),
            'labels': json.dumps(student_ids)
        }
        
        response = requests.post(
            ML_ATTENDANCE_ENDPOINT,
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code != 200:
            error_detail = response.json().get('detail', 'Unknown error')
            raise MLServiceError(f"ML Service Error: {error_detail}")
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        raise MLServiceError(f"Failed to connect to ML service: {str(e)}")


def check_ml_service_health() -> bool:
    """
    Check if ML service is available.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        response = requests.get(
            f'{ML_SERVICE_URL}/health',
            timeout=5
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def process_continuous_detection(
    image_file,
    stored_embeddings: List[List[float]],
    student_ids: List[str],
    session_id: str = ""
) -> dict:
    """Call ML service for real-time face detection and matching."""
    try:
        files = {'image': _prepare_image_upload(image_file)}
        data = {
            'session_id': session_id,
            'stored_vectors': json.dumps(stored_embeddings),
            'labels': json.dumps(student_ids)
        }
        
        response = requests.post(
            ML_CONTINUOUS_DETECTION_ENDPOINT,
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code != 200:
            error_detail = response.json().get('detail', 'Unknown error')
            raise MLServiceError(f"ML Service Error: {error_detail}")
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        raise MLServiceError(f"Failed to connect to ML service: {str(e)}")