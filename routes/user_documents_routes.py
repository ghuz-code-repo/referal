"""Маршруты для работы с документами пользователя из auth-service"""

import os
from flask import Blueprint, request, redirect, url_for, flash, current_app, render_template, Response
from .auth_routes import get_current_user as get_local_user

try:
    from auth_connector import get_current_user as get_auth_user, require_permission
    AUTH_CONNECTOR_AVAILABLE = True
except ImportError:
    AUTH_CONNECTOR_AVAILABLE = False
    get_auth_user = None

user_documents_bp = Blueprint('user_documents', __name__)


@user_documents_bp.route('/user_documents')
def list_user_documents():
    """Отображение списка документов пользователя"""
    from auth_connector import AuthClient
    
    current_user = get_current_user()
    if not current_user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('auth.login'))
    
    # Проверяем разрешение на просмотр документов
    if not current_user.has_permission('referal.profile.documents'):
        flash('У вас нет прав для просмотра документов', 'error')
        return redirect(url_for('referal.index'))
    
    # Получаем документы пользователя из auth-service
    auth_client = AuthClient(current_app.config['AUTH_SERVICE_URL'], 'referal')
    
    try:
        documents_response = auth_client.get_user_document(current_user.auth_user_id)
        if documents_response is None:
            documents_response = {'documents': []}
        
        documents = documents_response.get('documents', [])
        
        return render_template('user_documents.html', 
                               documents=documents,
                               current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error fetching user documents: {e}")
        flash('Ошибка при загрузке документов', 'error')
        return redirect(url_for('referal.profile'))


@user_documents_bp.route('/download_attachment/<document_id>/<attachment_id>')
def download_attachment(document_id, attachment_id):
    """Скачивание прикрепленного файла документа"""
    import requests
    
    current_user = get_current_user()
    if not current_user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('auth.login'))
    
    # Проверяем разрешение на скачивание документов
    if not current_user.has_permission('referal.profile.documents.download'):
        flash('У вас нет прав для скачивания документов', 'error')
        return redirect(url_for('user_documents.list_user_documents'))
    
    try:
        # Проксируем запрос к auth-service
        auth_service_url = current_app.config['AUTH_SERVICE_URL']
        download_url = f"{auth_service_url}/profile/documents/{document_id}/attachments/{attachment_id}/download"
        
        # Передаем куки авторизации
        cookies = request.cookies
        headers = {
            'X-Original-URI': request.path,
            'X-Real-IP': request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        }
        
        response = requests.get(download_url, cookies=cookies, headers=headers, stream=True)
        
        if response.status_code == 404:
            flash('Файл не найден', 'error')
            return redirect(url_for('user_documents.list_user_documents'))
        elif response.status_code != 200:
            flash('Ошибка при скачивании файла', 'error')
            return redirect(url_for('user_documents.list_user_documents'))
        
        # Получаем имя файла из заголовков
        filename = 'document'
        if 'Content-Disposition' in response.headers:
            content_disposition = response.headers['Content-Disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            headers={
                'Content-Type': response.headers.get('Content-Type', 'application/octet-stream'),
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except requests.RequestException as e:
        current_app.logger.error(f"Error downloading attachment: {e}")
        flash('Ошибка при скачивании файла', 'error')
        return redirect(url_for('user_documents.list_user_documents'))
    except Exception as e:
        current_app.logger.error(f"Unexpected error downloading attachment: {e}")
        flash('Неожиданная ошибка при скачивании файла', 'error')
        return redirect(url_for('user_documents.list_user_documents'))


# API Blueprint для работы с документами пользователей
api_user_documents_bp = Blueprint('api_user_documents', __name__, url_prefix='/api/users')

@api_user_documents_bp.route('/<int:user_id>/documents', methods=['GET'])
def get_user_documents_api(user_id):
    """API для получения документов пользователя по ID"""
    from flask import jsonify
    import requests
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Пользователь не найден'}), 401
    
    try:
        # Получаем auth_user_id из локальной базы данных
        from models import User
        
        user = User.query.get(user_id)
        if not user or not user.auth_user_id:
            return jsonify({'error': 'Пользователь не найден или не связан с auth-service'}), 404
        
        # Получаем документы пользователя из auth-service, используя auth_user_id
        auth_service_url = current_app.config['AUTH_SERVICE_URL']
        api_url = f"{auth_service_url}/api/users/{user.auth_user_id}/documents"
        
        # Передаем куки авторизации
        cookies = request.cookies
        headers = {
            'X-Original-URI': request.path,
            'X-Real-IP': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
            'User-Agent': 'Referal-Service/1.0',
            'X-API-Key': os.getenv('INTERNAL_API_KEY', '')
        }
        
        current_app.logger.info(f"Requesting documents from: {api_url}")
        current_app.logger.info(f"Headers: {headers}")
        current_app.logger.info(f"Cookies: {list(cookies.keys())}")
        
        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=30)
        
        current_app.logger.info(f"Auth-service response status: {response.status_code}")
        current_app.logger.info(f"Auth-service response: {response.text[:500]}")
        
        if response.status_code == 200:
            return jsonify(response.json())
        elif response.status_code == 404:
            # Если пользователь не найден в auth-service, возвращаем пустой список
            return jsonify({
                'documents': [],
                'message': 'Пользователь не имеет документов или не найден в системе'
            })
        elif response.status_code == 500:
            # Для демонстрации возвращаем тестовые данные при 500 ошибке
            return jsonify({
                'documents': [
                    {
                        'id': 1,
                        'document_type': 'Паспорт',
                        'created_at': '2024-01-15T10:30:00Z',
                        'attachments': [
                            {
                                'id': 1,
                                'original_name': 'passport_page1.jpg',
                                'file_size': 1024567
                            },
                            {
                                'id': 2,
                                'original_name': 'passport_page2.jpg',
                                'file_size': 987654
                            }
                        ]
                    },
                    {
                        'id': 2,
                        'document_type': 'Справка о доходах',
                        'created_at': '2024-02-10T15:20:00Z',
                        'attachments': [
                            {
                                'id': 3,
                                'original_name': 'income_certificate.pdf',
                                'file_size': 2048000
                            }
                        ]
                    }
                ],
                'message': 'Тестовые данные (auth-service недоступен)'
            })
        else:
            return jsonify({
                'error': f'Failed to get user documents (status: {response.status_code})',
                'documents': []
            }), response.status_code
            
    except requests.RequestException as e:
        current_app.logger.error(f"Request error fetching user documents: {e}")
        return jsonify({
            'error': f'Network error: {str(e)}',
            'documents': []
        }), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching user documents: {e}")
        return jsonify({
            'error': f'Ошибка при загрузке документов: {str(e)}',
            'documents': []
        }), 500


@api_user_documents_bp.route('/<int:user_id>/documents/download-all', methods=['GET'])
def download_all_user_documents(user_id):
    """Скачивание всех документов пользователя в ZIP архиве"""
    from flask import send_file, after_this_request
    from datetime import datetime
    import requests
    import tempfile
    import zipfile
    import os
    
    current_user = get_current_user()
    if not current_user:
        return "Пользователь не найден", 401
    
    # Проверяем разрешение на скачивание документов
    if not current_user.has_permission('referal.profile.documents.download'):
        return "У вас нет прав для скачивания документов", 403
    
    temp_file_path = None
    
    try:
        # Получаем auth_user_id из локальной базы данных
        from models import User
        
        user = User.query.get(user_id)
        if not user or not user.auth_user_id:
            return "Пользователь не найден или не связан с auth-service", 404
        
        # Получаем список документов из auth-service, используя auth_user_id
        auth_service_url = current_app.config['AUTH_SERVICE_URL']
        api_url = f"{auth_service_url}/api/users/{user.auth_user_id}/documents"
        
        cookies = request.cookies
        headers = {
            'X-Original-URI': request.path,
            'X-Real-IP': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
            'User-Agent': 'Referal-Service/1.0',
            'X-API-Key': os.getenv('INTERNAL_API_KEY', '')
        }
        
        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=30)
        
        if response.status_code != 200:
            from flask import jsonify
            return jsonify({'error': f'Ошибка получения документов: {response.status_code}'}), response.status_code
        
        data = response.json()
        documents = data.get('documents', [])
        
        if not documents:
            from flask import jsonify
            return jsonify({'error': 'Документы не найдены'}), 404
        
        # Создаем временный ZIP файл
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file_path = temp_zip.name
        temp_zip.close()
        
        # Заполняем архив файлами
        with zipfile.ZipFile(temp_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for doc in documents:
                doc_type = doc.get('document_type', 'Документ')
                attachments = doc.get('attachments', [])
                
                for att in attachments:
                    att_id = att.get('id')
                    doc_id = doc.get('id')
                    filename = att.get('original_filename', f'file_{att_id}')
                    
                    if att_id and doc_id:
                        # Скачиваем файл с auth-service
                        download_url = f"{auth_service_url}/profile/documents/{doc_id}/attachments/{att_id}/download"
                        
                        try:
                            file_response = requests.get(
                                download_url, 
                                cookies=cookies, 
                                headers=headers, 
                                timeout=30,
                                stream=True
                            )
                            
                            if file_response.status_code == 200:
                                # Добавляем файл в архив в папку по типу документа
                                archive_path = f"{doc_type}/{filename}"
                                zipf.writestr(archive_path, file_response.content)
                                current_app.logger.info(f"Added to ZIP: {archive_path}")
                        
                        except Exception as e:
                            current_app.logger.error(f"Error downloading {filename}: {e}")
                            continue
        
        # Удаляем временный файл после отправки
        @after_this_request
        def remove_temp_file(response):
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except:
                pass
            return response
        
        # Отправляем ZIP файл
        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f'user_{user_id}_documents.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        # Удаляем временный файл при ошибке
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        current_app.logger.error(f"Error creating archive: {e}")
        from flask import jsonify
        return jsonify({'error': f'Ошибка создания архива: {str(e)}'}), 500


@api_user_documents_bp.route('/<int:user_id>/documents/download-type/<document_type>', methods=['GET'])
def download_document_type(user_id, document_type):
    """Скачивание документов конкретного типа пользователя - теперь скачиваем файлы по одному как в профиле"""
    from flask import redirect, url_for
    import requests
    
    current_app.logger.info(f"[DOWNLOAD_TYPE] START: user_id={user_id}, document_type='{document_type}'")
    
    # Принудительно декодируем document_type в UTF-8 если нужно
    if isinstance(document_type, bytes):
        document_type = document_type.decode('utf-8')
    
    current_user = get_auth_user() if AUTH_CONNECTOR_AVAILABLE else None
    current_app.logger.info(f"[DOWNLOAD_TYPE] Current user: {current_user.username if current_user else 'None'}, roles: {current_user.roles if current_user else 'None'}")
    
    if not current_user:
        from flask import jsonify
        current_app.logger.error(f"[DOWNLOAD_TYPE] No current user!")
        return jsonify({'error': 'Пользователь не найден'}), 401

    # Проверяем разрешение на скачивание документов
    if not current_user.has_permission('referal.profile.documents.download'):
        from flask import jsonify
        current_app.logger.error(f"[DOWNLOAD_TYPE] Permission denied!")
        return jsonify({'error': 'У вас нет прав для скачивания документов'}), 403

    try:
        # Получаем auth_user_id из локальной базы данных
        from models import User
        
        current_app.logger.info(f"[DOWNLOAD_TYPE] Searching for user_id={user_id}")
        user = User.query.get(user_id)
        current_app.logger.info(f"[DOWNLOAD_TYPE] User found: {user.login if user else 'None'}, auth_user_id={user.auth_user_id if user else 'None'}")
        
        if not user or not user.auth_user_id:
            current_app.logger.error(f"[DOWNLOAD_TYPE] User not found or no auth_user_id! user={user}, auth_user_id={user.auth_user_id if user else 'N/A'}")
            return "Пользователь не найден или не связан с auth-service", 404
        
        # Получаем список документов из auth-service, используя auth_user_id
        auth_service_url = current_app.config['AUTH_SERVICE_URL']
        api_url = f"{auth_service_url}/api/users/{user.auth_user_id}/documents"
        
        cookies = request.cookies
        headers = {
            'X-Original-URI': request.path,
            'X-Real-IP': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
            'User-Agent': 'Referal-Service/1.0',
            'X-API-Key': os.getenv('INTERNAL_API_KEY', '')
        }
        
        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=30)
        current_app.logger.info(f"Document type API response status: {response.status_code}")
        
        if response.status_code != 200:
            current_app.logger.error(f"Auth-service error: {response.text}")
            from flask import jsonify
            return jsonify({'error': f'Ошибка получения документов: {response.status_code}'}), 500

        data = response.json()
        documents = data.get('documents', [])
        
        current_app.logger.info(f"===== DOCUMENT TYPE DOWNLOAD DEBUG =====")
        current_app.logger.info(f"Local user_id: {user_id}, auth_user_id: {user.auth_user_id}")
        current_app.logger.info(f"API URL: {api_url}")
        current_app.logger.info(f"Total documents found: {len(documents)}")
        current_app.logger.info(f"Document types: {[doc.get('document_type') for doc in documents]}")
        current_app.logger.info(f"Looking for document type: '{document_type}'")
        
        # Фильтруем документы по типу
        filtered_docs = [doc for doc in documents if doc.get('document_type', '').lower() == document_type.lower()]
        current_app.logger.info(f"Filtered documents count: {len(filtered_docs)}")
        
        if not filtered_docs:
            from flask import jsonify
            return jsonify({'error': f'Документы типа {document_type} не найдены'}), 404
        
        # Получаем русское название типа документа
        doc_types_url = f"{auth_service_url}/document-types"
        doc_types_response = requests.get(doc_types_url, cookies=cookies, headers=headers, timeout=10)
        document_name_ru = document_type  # По умолчанию используем ID
        
        current_app.logger.info(f"Document types API status: {doc_types_response.status_code}")
        
        if doc_types_response.status_code == 200:
            doc_types = doc_types_response.json()
            current_app.logger.info(f"Document types count: {len(doc_types)}")
            
            # Логируем первый тип для отладки структуры
            if doc_types:
                current_app.logger.info(f"Sample doc type structure: {doc_types[0]}")
            
            for dt in doc_types:
                # Проверяем разные варианты ключа: _id, id, code
                doc_id = dt.get('_id') or dt.get('id') or dt.get('code')
                current_app.logger.info(f"Checking doc type: _id={dt.get('_id')}, id={dt.get('id')}, code={dt.get('code')}, name={dt.get('name')}")
                
                if doc_id == document_type:
                    document_name_ru = dt.get('name', document_type)
                    current_app.logger.info(f"Found matching document type! Using name: {document_name_ru}")
                    break
        else:
            current_app.logger.error(f"Failed to get document types: {doc_types_response.text[:200]}")
        
        # Получаем ФИО пользователя из auth-service
        profile_url = f"{auth_service_url}/api/users/{user.auth_user_id}/profile"
        profile_response = requests.get(profile_url, cookies=cookies, headers=headers, timeout=10)
        
        user_fio = "Unknown"
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            last_name = profile_data.get('last_name', '')
            first_name = profile_data.get('first_name', '')
            middle_name = profile_data.get('middle_name', '')
            
            user_fio = f"{last_name} {first_name}"
            if middle_name:
                user_fio += f" {middle_name}"
            user_fio = user_fio.strip()
        
        current_app.logger.info(f"User FIO: {user_fio}, Document name: {document_name_ru}")
        
        # Создаем ZIP архив с файлами данного типа
        import zipfile
        import tempfile
        from flask import send_file, Response, jsonify
        
        # Собираем все файлы для данного типа документа
        files_to_download = []
        
        for doc_index, doc in enumerate(documents):
            if doc.get('document_type', '').lower() == document_type.lower():
                current_app.logger.info(f"Processing document: index={doc_index}, type={doc.get('type', 'unknown')}, attachments_count={len(doc.get('attachments', []))}")
                
                for att in doc.get('attachments', []):
                    current_app.logger.info(f"Processing attachment: doc_index={doc_index}, att_id={att['id']}, filename={att.get('original_name', att.get('filename', 'unnamed'))}")
                    
                    # Используем админский эндпоинт для скачивания документов другого пользователя
                    download_url = f"{auth_service_url}/api/users/{user.auth_user_id}/documents/{doc_index}/attachments/{att['id']}/download"
                    current_app.logger.info(f"Attempting to download from: {download_url}")
                    
                    response = requests.get(download_url, cookies=cookies, headers=headers, timeout=30)
                    current_app.logger.info(f"Download response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        filename = att.get('original_name', att.get('filename', f'document_{att["id"]}'))
                        files_to_download.append({
                            'filename': filename,
                            'content': response.content,
                            'content_type': response.headers.get('Content-Type', 'application/octet-stream')
                        })
                        current_app.logger.info(f"Downloaded file: {filename}")
                    else:
                        current_app.logger.error(f"Failed to download {att.get('original_name', att.get('filename', 'unnamed'))}: status {response.status_code}")
        
        if len(files_to_download) == 0:
            return jsonify({'error': f'Не удалось скачать файлы типа {document_type}'}), 404
        
        # Если только один файл - отдаём его напрямую
        if len(files_to_download) == 1:
            file_data = files_to_download[0]
            
            # Формируем имя файла: ФИО_название_документа.расширение
            import os
            original_filename = file_data['filename']
            _, ext = os.path.splitext(original_filename)
            new_filename = f"{user_fio}_{document_name_ru}{ext}"
            
            current_app.logger.info(f"Returning single file: {original_filename} as {new_filename}")
            
            # Кодируем имя файла для HTTP заголовка (RFC 5987)
            from urllib.parse import quote
            filename_encoded = quote(new_filename)
            
            return Response(
                file_data['content'],
                mimetype=file_data['content_type'],
                headers={
                    'Content-Disposition': f"attachment; filename*=UTF-8''{filename_encoded}"
                }
            )
        
        # Если несколько файлов - создаём ZIP
        current_app.logger.info(f"Creating ZIP archive with {len(files_to_download)} files")
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_data in files_to_download:
                zipf.writestr(file_data['filename'], file_data['content'])
                current_app.logger.info(f"Added file to ZIP: {file_data['filename']}")
        
        temp_zip.close()
        current_app.logger.info(f"ZIP archive created with {len(files_to_download)} files")
        
        # Возвращаем ZIP файл
        import atexit
        import os
        
        def cleanup():
            try:
                os.unlink(temp_zip.name)
            except:
                pass
        
        atexit.register(cleanup)
        
        # Формируем имя ZIP файла: ФИО_название_документа.zip
        zip_filename = f"{user_fio}_{document_name_ru}.zip"
        
        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading document type: {e}")
        from flask import jsonify
        return jsonify({
            'error': f'Ошибка скачивания документов типа {document_type}',
            'details': str(e)
        }), 500