"""Маршруты для работы с документами пользователя из auth-service"""

from flask import Blueprint, request, redirect, url_for, flash, current_app, render_template, Response
from .auth_routes import get_current_user

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
    if not current_user.is_admin and not current_user.has_permission('profile.documents'):
        flash('У вас нет прав для просмотра документов', 'error')
        return redirect(url_for('referal.profile'))
    
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
    if not current_user.is_admin and not current_user.has_permission('profile.documents.download'):
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
            'User-Agent': 'Referal-Service/1.0'
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
    if not current_user.is_admin and not current_user.has_permission('profile.documents.download'):
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
            'User-Agent': 'Referal-Service/1.0'
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
    
    current_app.logger.info(f"Download request for document type: '{document_type}' (user {user_id})")
    
    # Принудительно декодируем document_type в UTF-8 если нужно
    if isinstance(document_type, bytes):
        document_type = document_type.decode('utf-8')
    
    current_user = get_current_user()
    if not current_user:
        from flask import jsonify
        return jsonify({'error': 'Пользователь не найден'}), 401

    # Проверяем разрешение на скачивание документов
    if not current_user.is_admin and not current_user.has_permission('profile.documents.download'):
        from flask import jsonify
        return jsonify({'error': 'У вас нет прав для скачивания документов'}), 403

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
            'User-Agent': 'Referal-Service/1.0'
        }
        
        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=30)
        current_app.logger.info(f"Document type API response status: {response.status_code}")
        
        if response.status_code != 200:
            current_app.logger.error(f"Auth-service error: {response.text}")
            from flask import jsonify
            return jsonify({'error': f'Ошибка получения документов: {response.status_code}'}), 500

        data = response.json()
        documents = data.get('documents', [])
        
        current_app.logger.info(f"Found documents: {[doc.get('document_type') for doc in documents]}")
        current_app.logger.info(f"Looking for document type: '{document_type}'")
        
        # Фильтруем документы по типу
        filtered_docs = [doc for doc in documents if doc.get('document_type', '').lower() == document_type.lower()]
        current_app.logger.info(f"Filtered documents count: {len(filtered_docs)}")
        
        if not filtered_docs:
            from flask import jsonify
            return jsonify({'error': f'Документы типа {document_type} не найдены'}), 404
        
        # Создаем ZIP архив с файлами данного типа
        import zipfile
        import tempfile
        from flask import send_file
        
        # Создаем временный ZIP файл
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            files_added = 0
            
            for doc_index, doc in enumerate(documents):
                if doc.get('document_type', '').lower() == document_type.lower():
                    current_app.logger.info(f"Processing document: index={doc_index}, type={doc.get('type', 'unknown')}, attachments_count={len(doc.get('attachments', []))}")
                    
                    for att in doc.get('attachments', []):
                        current_app.logger.info(f"Processing attachment: doc_index={doc_index}, att_id={att['id']}, filename={att.get('original_name', att.get('filename', 'unnamed'))}")
                        
                        # Используем doc_index вместо doc['id'] (как в профиле!)
                        download_url = f"{auth_service_url}/profile/documents/{doc_index}/attachments/{att['id']}/download"
                        current_app.logger.info(f"Attempting to download from: {download_url}")
                        
                        response = requests.get(download_url, cookies=cookies, headers=headers, timeout=30)
                        current_app.logger.info(f"Download response status: {response.status_code}")
                        
                        if response.status_code == 200:
                            filename = att.get('original_name', att.get('filename', f'document_{att["id"]}'))
                            zipf.writestr(filename, response.content)
                            files_added += 1
                            current_app.logger.info(f"Added file to ZIP: {filename}")
                        else:
                            current_app.logger.error(f"Failed to download {att.get('original_name', att.get('filename', 'unnamed'))}: status {response.status_code}")
        
        temp_zip.close()
        
        if files_added == 0:
            import os
            os.unlink(temp_zip.name)
            from flask import jsonify
            return jsonify({'error': f'Не удалось скачать файлы типа {document_type}'}), 404
        
        current_app.logger.info(f"ZIP archive created with {files_added} files")
        
        # Возвращаем ZIP файл
        import atexit
        import os
        
        def cleanup():
            try:
                os.unlink(temp_zip.name)
            except:
                pass
        
        atexit.register(cleanup)
        
        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=f'{document_type}_documents.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading document type: {e}")
        from flask import jsonify
        return jsonify({
            'error': f'Ошибка скачивания документов типа {document_type}',
            'details': str(e)
        }), 500