import base64

def decode_header_full_name(request):
    """
    Декодирует base64-закодированное полное имя из заголовков запроса
    
    Args:
        request: Объект запроса Flask с заголовками
        
    Returns:
        str: Декодированное полное имя или оригинальное значение, если не закодировано
    """
    # Получаем закодированное имя и флаг кодировки
    encoded_full_name = request.headers.get('X-User-Full-Name', '')
    encoding = request.headers.get('X-User-Full-Name-Encoding', '')
    
    print(f"Received full name header: {encoded_full_name}, encoding: {encoding}")
    
    if encoding == 'base64' and encoded_full_name:
        try:
            # Декодируем base64
            decoded_bytes = base64.b64decode(encoded_full_name)
            decoded_name = decoded_bytes.decode('utf-8')
            print(f"Decoded name: '{decoded_name}'")
            return decoded_name
        except Exception as e:
            print(f"Error decoding full name: {e}")
            return encoded_full_name  # Возвращаем как есть, если декодирование не удалось
    else:
        return encoded_full_name  # Не закодировано или нет указания кодировки
