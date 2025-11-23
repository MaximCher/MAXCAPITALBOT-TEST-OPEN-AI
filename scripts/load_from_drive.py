"""
MAXCAPITAL Bot - Enhanced Google Drive Loader
Загружает все документы из папок Google Drive рекурсивно
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, close_db, get_session
from src.google_drive_loader import GoogleDriveLoader
from src.vector_store import VectorStore
from src.logger import setup_logging
import structlog

logger = structlog.get_logger()


async def load_all_folders():
    """Загрузка всех документов из папок Google Drive"""
    
    setup_logging()
    
    logger.info("starting_google_drive_sync")
    
    try:
        await init_db()
        
        async for session in get_session():
            loader = GoogleDriveLoader()
            vector_store = VectorStore(session)
            
            # Проверяем текущее количество документов
            current_count = await vector_store.count_documents()
            print(f"\n📊 Текущих документов в базе: {current_count}\n")
            
            # Аутентификация
            print("🔐 Подключение к Google Drive...")
            loader.authenticate()
            
            # Получаем список всех файлов из главной папки и подпапок
            print("📂 Сканирование папок...\n")
            
            main_folder_id = loader.folder_id
            
            # Функция для рекурсивного получения файлов
            def get_all_files_recursive(folder_id, folder_name=""):
                """Рекурсивно получает все файлы из папки и подпапок"""
                all_files = []
                
                try:
                    # Получаем содержимое папки
                    query = f"'{folder_id}' in parents and trashed=false"
                    
                    results = loader.service.files().list(
                        q=query,
                        fields="files(id, name, mimeType, size)",
                        pageSize=1000
                    ).execute()
                    
                    items = results.get('files', [])
                    
                    for item in items:
                        # Если это папка - рекурсивно обрабатываем
                        if item['mimeType'] == 'application/vnd.google-apps.folder':
                            subfolder_name = f"{folder_name}/{item['name']}" if folder_name else item['name']
                            print(f"  📁 Папка: {subfolder_name}")
                            
                            subfiles = get_all_files_recursive(item['id'], subfolder_name)
                            all_files.extend(subfiles)
                        
                        # Если это поддерживаемый файл
                        elif item['mimeType'] in [
                            'application/pdf',
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            'text/plain'
                        ]:
                            item['folder'] = folder_name
                            all_files.append(item)
                            
                except Exception as e:
                    logger.error("folder_scan_error", folder=folder_name, error=str(e))
                
                return all_files
            
            # Получаем все файлы
            all_files = get_all_files_recursive(main_folder_id, "MAXCAPITAL")
            
            print(f"\n✅ Найдено файлов для обработки: {len(all_files)}\n")
            
            if not all_files:
                print("⚠️  Файлы не найдены. Проверьте:")
                print("   1. ID папки правильный")
                print("   2. Service Account имеет доступ к папке")
                print("   3. В папке есть PDF, DOCX или TXT файлы\n")
                return
            
            # Обрабатываем каждый файл
            success_count = 0
            skip_count = 0
            error_count = 0
            
            for i, file_info in enumerate(all_files, 1):
                file_id = file_info['id']
                file_name = file_info['name']
                mime_type = file_info['mimeType']
                file_size = file_info.get('size', 0)
                folder = file_info.get('folder', '')
                
                full_path = f"{folder}/{file_name}" if folder else file_name
                
                print(f"[{i}/{len(all_files)}] {full_path}")
                
                try:
                    # Скачиваем файл
                    file_content = loader.download_file(file_id, file_name)
                    
                    if not file_content:
                        print(f"  ⚠️  Не удалось скачать")
                        skip_count += 1
                        continue
                    
                    # Извлекаем текст
                    text = loader.extract_text(file_content, mime_type)
                    
                    if not text or len(text.strip()) < 50:
                        print(f"  ⚠️  Мало текста ({len(text)} символов)")
                        skip_count += 1
                        continue
                    
                    # Добавляем в векторную базу
                    await vector_store.add_document(
                        filename=full_path,
                        content=text,
                        file_type=Path(file_name).suffix.lstrip('.'),
                        file_size=int(file_size) if file_size else len(file_content),
                        drive_file_id=file_id
                    )
                    
                    print(f"  ✅ Добавлен ({len(text)} символов, {len(text.split())} слов)")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ❌ Ошибка: {str(e)}")
                    error_count += 1
                    logger.error("file_processing_error", file=file_name, error=str(e))
            
            # Итоговая статистика
            new_count = await vector_store.count_documents()
            
            print(f"\n{'='*60}")
            print(f"📊 ИТОГИ ЗАГРУЗКИ")
            print(f"{'='*60}")
            print(f"✅ Успешно загружено: {success_count}")
            print(f"⚠️  Пропущено: {skip_count}")
            print(f"❌ Ошибок: {error_count}")
            print(f"📚 Всего документов в базе: {new_count}")
            print(f"{'='*60}\n")
            
            logger.info(
                "google_drive_sync_completed",
                success=success_count,
                skipped=skip_count,
                errors=error_count,
                total_documents=new_count
            )
    
    except Exception as e:
        logger.error("sync_error", error=str(e), exc_info=True)
        print(f"\n❌ Критическая ошибка: {str(e)}\n")
        return 1
    
    finally:
        await close_db()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(load_all_folders())
    sys.exit(exit_code)

