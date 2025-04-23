def is_valid_image_url(url):
    """
    Verifica si la URL corresponde a una imagen y no a un video.
    
    Args:
        url: URL del recurso a verificar
        
    Returns:
        Boolean: True si es una imagen válida, False si no
    """
    if not url:
        return False
    
    # Extensiones de imagen comunes
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg']
    # Extensiones de video comunes para excluir
    video_extensions = ['.mp4', '.webm', '.avi', '.mov', '.wmv', '.flv', '.mkv']
    
    url_lower = url.lower()
    
    # Verificar si termina con extensión de imagen
    is_image = any(url_lower.endswith(ext) for ext in image_extensions)
    
    # Verificar si termina con extensión de video
    is_video = any(url_lower.endswith(ext) for ext in video_extensions)
    
    # También podemos buscar patrones en la URL que sugieran video
    contains_video_pattern = 'video' in url_lower or 'player' in url_lower
    
    # Si la URL tiene una extensión de imagen y no parece ser un video
    return is_image and not (is_video or contains_video_pattern)