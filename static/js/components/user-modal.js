/**
 * Обработчик модального окна информации о пользователе
 */
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для открытия модальных окон пользователей
    const userLinks = document.querySelectorAll('.user-login-link');
    
            userLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const userId = this.getAttribute('data-user-id');
            
            if (userId) {
                const modal = document.getElementById(`UserInfoModal_${userId}`);
                if (modal) {
                    modal.style.display = 'block';
                    console.log('Открываю модальное окно:', `UserInfoModal_${userId}`);
                    
                    // Загружаем документы пользователя
                    loadUserDocuments(userId);
                } else {
                    console.log('Не найдено модальное окно:', `UserInfoModal_${userId}`);
                }
            } else {
                console.log('Не найден user-id');
            }
        });
    });    // Обработчики для закрытия модальных окон пользователей
    const userModals = document.querySelectorAll('[id^="UserInfoModal_"]');
    
    userModals.forEach(modal => {
        const closeBtn = modal.querySelector('.close');
        
        // Закрытие по клику на крестик
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                modal.style.display = 'none';
            });
        }
        
        // Закрытие по клику вне модального окна
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    });
    
    // Закрытие по нажатию Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            userModals.forEach(modal => {
                if (modal.style.display === 'block') {
                    modal.style.display = 'none';
                }
            });
        }
    });

    /**
     * Загрузка документов пользователя
     */
    function loadUserDocuments(userId) {
        const container = document.getElementById(`userDocuments_${userId}`);
        if (!container) return;

        // Показываем индикатор загрузки
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> Загрузка документов...</div>';

        // Загружаем документы через API
        fetch(`/api/users/${userId}/documents`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                displayUserDocuments(container, data.documents);
            })
            .catch(error => {
                console.error('Ошибка загрузки документов:', error);
                container.innerHTML = '<div class="error-message"><i class="fas fa-exclamation-triangle"></i> Ошибка загрузки документов</div>';
            });
    }

    /**
     * Отображение документов пользователя
     */
    function displayUserDocuments(container, documents) {
        if (!documents || documents.length === 0) {
            container.innerHTML = '<div class="no-documents-message"><i class="fas fa-inbox"></i> Документы не найдены</div>';
            return;
        }

        let html = '<div class="user-documents-grid">';
        
        documents.forEach(doc => {
            html += `
                <div class="user-document-card">
                    <div class="document-header">
                        <div class="document-icon">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <div class="document-info">
                            <div class="document-title">${doc.document_type || 'Документ'}</div>
                            <div class="document-date">
                                Загружен: ${new Date(doc.created_at).toLocaleDateString('ru-RU')}
                            </div>
                        </div>
                    </div>
                    ${doc.attachments && doc.attachments.length > 0 ? `
                        <div class="document-attachments">
                            <div class="attachments-title">Вложения:</div>
                            <div class="attachments-list">
                                ${doc.attachments.map(att => `
                                    <div class="attachment-item">
                                        <div class="attachment-info">
                                            <i class="fas fa-paperclip"></i>
                                            <span class="attachment-name">${att.original_filename}</span>
                                            <span class="attachment-size">${formatFileSize(att.file_size)}</span>
                                        </div>
                                        <button class="download-attachment-btn" 
                                                data-doc-id="${doc.id}" 
                                                data-att-id="${att.id}"
                                                title="Скачать файл">
                                            <i class="fas fa-download"></i>
                                        </button>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : '<div class="no-attachments">Вложений нет</div>'}
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;

        // Добавляем обработчики для кнопок скачивания
        container.querySelectorAll('.download-attachment-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const docId = this.getAttribute('data-doc-id');
                const attId = this.getAttribute('data-att-id');
                downloadAttachment(docId, attId);
            });
        });
    }

    /**
     * Скачивание вложения документа
     */
    function downloadAttachment(docId, attId) {
        const url = `/documents/${docId}/attachments/${attId}/download`;
        
        // Создаем невидимую ссылку для скачивания
        const link = document.createElement('a');
        link.href = url;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /**
     * Форматирование размера файла
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Б';
        const k = 1024;
        const sizes = ['Б', 'КБ', 'МБ', 'ГБ'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});

/**
 * Скачивание документов конкретного типа (новая функция)
 */
function downloadDocumentType(userId, documentType) {
    console.log(`Скачивание документов типа "${documentType}" для пользователя:`, userId);
    
    // Показываем индикатор загрузки
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btn.disabled = true;
    
    // Получаем имя пользователя для названия файла
    let userName = 'user_' + userId;
    try {
        const userModal = document.querySelector(`#UserInfoModal_${userId}`);
        if (userModal) {
            const nameElement = userModal.querySelector('h1');
            if (nameElement && nameElement.textContent) {
                const fullName = nameElement.textContent.trim();
                const nameParts = fullName.split(' ');
                if (nameParts.length >= 2) {
                    const lastName = nameParts[0];
                    const firstInitial = nameParts[1] ? nameParts[1][0] + '.' : '';
                    const middleInitial = nameParts[2] ? nameParts[2][0] + '.' : '';
                    userName = `${lastName}_${firstInitial}${middleInitial}`.replace(/[^a-zA-Zа-яА-Я0-9._]/g, '_');
                }
            }
        }
    } catch (e) {
        console.warn('Не удалось получить имя пользователя:', e);
    }
    
    // Скачиваем документы конкретного типа
    fetch(`/referal/api/users/${userId}/documents/download-type/${encodeURIComponent(documentType)}`, {
        method: 'GET',
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('У вас нет прав для скачивания документов');
            } else if (response.status === 404) {
                throw new Error(`Документы типа "${documentType}" не найдены`);
            } else {
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
        }
        return response.blob();
    })
    .then(blob => {
        // Определяем расширение файла
        let fileExtension = '.zip';
        const contentType = blob.type;
        if (contentType.includes('pdf')) fileExtension = '.pdf';
        else if (contentType.includes('image')) fileExtension = '.jpg';
        else if (contentType.includes('text')) fileExtension = '.txt';
        
        // Создаем URL для blob и скачиваем файл
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${userName}_${documentType}${fileExtension}`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Освобождаем URL
        window.URL.revokeObjectURL(url);
        
        showNotification(`Документы "${documentType}" успешно скачаны!`, 'success');
    })
    .catch(error => {
        console.error('Ошибка скачивания документов:', error);
        showNotification(`Ошибка скачивания: ${error.message}`, 'error');
    })
    .finally(() => {
        // Восстанавливаем кнопку
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

/**
 * Скачивание документов пользователя (глобальная функция для вызова из HTML)
 */
function downloadUserDocuments(userId) {
    console.log('Скачивание документов для пользователя:', userId);
    
    // Показываем индикатор загрузки
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
    btn.disabled = true;
    
    // Сначала проверим, есть ли документы
    fetch(`/referal/api/users/${userId}/documents`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.documents && data.documents.length > 0) {
                // Есть документы - даем выбор: показать список или скачать все
                showDocumentOptions(userId, data.documents);
            } else {
                alert('У пользователя нет документов для скачивания');
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки документов:', error);
            alert(`Ошибка при загрузке документов: ${error.message}`);
        })
        .finally(() => {
            // Восстанавливаем кнопку
            btn.innerHTML = originalText;
            btn.disabled = false;
        });
}

/**
 * Показать опции для работы с документами
 */
function showDocumentOptions(userId, documents) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.7); z-index: 10000; 
        display: flex; align-items: center; justify-content: center;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: var(--card-background); padding: 30px; border-radius: 12px; 
        max-width: 500px; text-align: center; color: var(--text-primary);
        border: 1px solid var(--border-color);
    `;
    
    let totalAttachments = 0;
    documents.forEach(doc => {
        totalAttachments += (doc.attachments || []).length;
    });
    
    content.innerHTML = `
        <h3 style="margin-bottom: 20px; color: var(--primary-color);">
            <i class="fas fa-folder-open"></i> Документы пользователя
        </h3>
        <p style="margin-bottom: 20px; color: var(--text-secondary);">
            Найдено <strong>${documents.length}</strong> документов с <strong>${totalAttachments}</strong> файлами
        </p>
        <div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;">
            <button onclick="downloadAllDocuments(${userId}); this.closest('.temp-modal').remove();" 
                    style="background: var(--primary-color); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; display: flex; align-items: center; gap: 8px; transition: all 0.2s ease;">
                <i class="fas fa-download"></i> Скачать все (ZIP)
            </button>
            <button onclick="showDetailedDocuments(${userId}); this.closest('.temp-modal').remove();" 
                    style="background: var(--secondary-color, #6c757d); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; display: flex; align-items: center; gap: 8px; transition: all 0.2s ease;">
                <i class="fas fa-list"></i> Просмотреть список
            </button>
        </div>
        <button onclick="this.closest('.temp-modal').remove()" 
                style="background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 15px;">
            Отмена
        </button>
    `;
    
    modal.className = 'temp-modal';
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Сохраняем данные документов для последующего использования
    window.currentUserDocuments = { userId, documents };
    
    // Закрытие по клику вне модала
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

/**
 * Скачать все документы пользователя как ZIP архив
 */
function downloadAllDocuments(userId) {
    console.log('Скачивание всех документов пользователя:', userId);
    
    // Пытаемся получить имя пользователя из модального окна
    let userName = 'user_' + userId;
    try {
        // Ищем элемент с ФИО пользователя в модальном окне
        const userModal = document.querySelector(`#UserInfoModal_${userId}`);
        if (userModal) {
            const nameElement = userModal.querySelector('h1');
            if (nameElement && nameElement.textContent) {
                const fullName = nameElement.textContent.trim();
                // Преобразуем "Иванов Иван Иванович" в "Иванов И.И."
                const nameParts = fullName.split(' ');
                if (nameParts.length >= 2) {
                    const lastName = nameParts[0];
                    const firstInitial = nameParts[1] ? nameParts[1][0] + '.' : '';
                    const middleInitial = nameParts[2] ? nameParts[2][0] + '.' : '';
                    userName = `${lastName}_${firstInitial}${middleInitial}`.replace(/[^a-zA-Zа-яА-Я0-9._]/g, '_');
                }
            }
        }
    } catch (e) {
        console.warn('Не удалось получить имя пользователя, используем ID:', e);
    }
    
    // Показываем уведомление о начале загрузки
    showNotification('Подготовка архива к скачиванию...', 'info');
    
    // Скачиваем ZIP архив через fetch для правильной передачи куки
    fetch(`/referal/api/users/${userId}/documents/download-all`, {
        method: 'GET',
        credentials: 'same-origin' // Включаем куки
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('У вас нет прав для скачивания документов');
            } else if (response.status === 404) {
                throw new Error('Документы не найдены');
            } else {
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
        }
        return response.blob();
    })
    .then(blob => {
        // Создаем URL для blob и скачиваем файл
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${userName}_documents.zip`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Освобождаем URL
        window.URL.revokeObjectURL(url);
        
        showNotification('Архив успешно скачан!', 'success');
    })
    .catch(error => {
        console.error('Ошибка скачивания архива:', error);
        showNotification(`Ошибка скачивания: ${error.message}`, 'error');
    });
}

/**
 * Показать детальный список документов
 */
function showDetailedDocuments(userId) {
    console.log('Показываем детальный список документов для пользователя:', userId);
    
    if (!window.currentUserDocuments) {
        console.error('Данные документов не найдены');
        alert('Ошибка: данные документов не найдены');
        return;
    }
    
    const { documents } = window.currentUserDocuments;
    showDocumentsModal(documents, userId);
}

/**
 * Показать модальное окно с документами для скачивания
 */
function showDocumentsModal(documents, userId) {
    console.log('Показываем модальное окно с документами:', documents);
    
    if (!documents || documents.length === 0) {
        alert('У пользователя нет документов для просмотра');
        return;
    }

    let html = '<div class="documents-download-modal" style="max-width: 600px;">';
    html += '<h3 style="margin-bottom: 20px; color: var(--primary-color); text-align: center;"><i class="fas fa-folder-open"></i> Документы пользователя</h3>';
    
    documents.forEach(doc => {
        html += `<div class="document-item" style="background: var(--background-color); border: 1px solid var(--border-color); border-radius: 8px; padding: 15px; margin-bottom: 15px;">
            <h4 style="color: var(--text-primary); margin: 0 0 10px 0; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-file-alt"></i> ${doc.document_type || 'Документ'}
            </h4>
            <p style="color: var(--text-secondary); font-size: 12px; margin: 0 0 10px 0;">
                Загружен: ${new Date(doc.created_at).toLocaleDateString('ru-RU')}
            </p>`;
        
        if (doc.attachments && doc.attachments.length > 0) {
            html += '<div class="attachments-list" style="display: flex; flex-direction: column; gap: 8px;">';
            doc.attachments.forEach(att => {
                html += `
                    <div class="attachment-download" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--card-background); border: 1px solid var(--border-color); border-radius: 4px;">
                        <div>
                            <span style="color: var(--text-primary); font-weight: 500;">${att.original_filename}</span>
                            <span style="color: var(--text-secondary); font-size: 11px; margin-left: 8px;">(${formatFileSize(att.file_size)})</span>
                        </div>
                        <button onclick="downloadSingleAttachment(${doc.id}, ${att.id})" 
                                style="background: var(--primary-color); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; display: flex; align-items: center; gap: 4px;">
                            <i class="fas fa-download"></i> Скачать
                        </button>
                    </div>`;
            });
            html += '</div>';
        } else {
            html += '<p style="color: var(--text-muted); font-style: italic; text-align: center; padding: 10px;">Вложений нет</p>';
        }
        html += '</div>';
    });
    
    html += '</div>';
    
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.7); z-index: 10000; 
        display: flex; align-items: center; justify-content: center;
        overflow-y: auto; padding: 20px;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: var(--card-background); padding: 25px; border-radius: 12px; 
        max-width: 90vw; max-height: 90vh; overflow-y: auto; 
        color: var(--text-primary); border: 1px solid var(--border-color);
    `;
    
    content.innerHTML = html + `
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="this.closest('.temp-modal').remove()" 
                    style="background: var(--border-color); color: var(--text-primary); border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">
                Закрыть
            </button>
        </div>
    `;
    
    modal.className = 'temp-modal';
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Закрытие по клику вне модала
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

/**
 * Скачивание одного вложения
 */
function downloadSingleAttachment(docId, attId) {
    const url = `/referal/documents/${docId}/attachments/${attId}/download`;
    const link = document.createElement('a');
    link.href = url;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Сохранение банковских данных (заглушка)
 */
function saveBankData(userId) {
    console.log('Сохранение банковских данных для пользователя:', userId);
    alert('Функция сохранения банковских данных будет реализована позже');
}

/**
 * Показать уведомление
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 10001;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
        color: white; padding: 15px 20px; border-radius: 6px;
        font-weight: 500; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        max-width: 350px; animation: slideIn 0.3s ease;
    `;
    
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Автоматически удаляем через 5 секунд
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
    
    // Клик для закрытия
    notification.addEventListener('click', () => {
        notification.remove();
    });
}
