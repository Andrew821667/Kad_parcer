# План реализации парсера с иерархией актов

## Этап 1: Парсинг PDF и извлечение метаданных ⏱️ 2-3 дня

### 1.1 Создать PDF парсер

**Файл:** `src/parser/pdf_parser.py`

**Извлечение полей:**
- Тип документа (regex: "РЕШЕНИЕ|ОПРЕДЕЛЕНИЕ|ПОСТАНОВЛЕНИЕ")
- Номер дела (regex: "Дело № (А\d+-\d+/\d+)")
- Даты (announced_date, publication_date)
- Состав суда (председательствующий, судьи, секретарь)
- Резолютивная часть (после "ПОСТАНОВИЛ" или "РЕШИЛ")

**Технологии:**
- `pdfplumber` - извлечение текста
- `regex` - парсинг структурированных полей
- `spacy` - NER для извлечения сущностей

**Пример:**
```python
class CourtDocumentParser:
    def parse_pdf(self, pdf_path: str) -> dict:
        """Извлечь метаданные из PDF."""
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages)

        return {
            "document_type": self._extract_doc_type(text),
            "case_number": self._extract_case_number(text),
            "decision_date": self._extract_decision_date(text),
            "judges": self._extract_judges(text),
            "outcome": self._extract_outcome(text),
            # ...
        }
```

### 1.2 Извлечение резолютивной части

**Ключевые паттерны:**
```python
RESOLUTION_PATTERNS = [
    r"ПОСТАНОВИЛ:?\n(.+?)(?:\n\n|$)",
    r"РЕШИЛ:?\n(.+?)(?:\n\n|$)",
    r"ОПРЕДЕЛИЛ:?\n(.+?)(?:\n\n|$)",
]

DECISION_KEYWORDS = {
    "approved": ["удовлетворить", "взыскать", "признать"],
    "rejected": ["отказать", "оставить без удовлетворения"],
    "partial": ["частично удовлетворить"],
    "upheld": ["оставить без изменения", "оставить в силе"],
    "overturned": ["отменить", "изменить"],
}
```

### 1.3 NER для извлечения сущностей

**Используем spaCy + custom patterns:**
```python
import spacy

nlp = spacy.load("ru_core_news_lg")

# Кастомные правила
patterns = [
    {"label": "LAW", "pattern": [{"TEXT": {"REGEX": "ст\\."}}, {"IS_DIGIT": True}]},
    {"label": "MONEY", "pattern": [{"IS_DIGIT": True}, {"LOWER": "руб"}]},
]

ruler = nlp.add_pipe("entity_ruler")
ruler.add_patterns(patterns)

# Извлечение
doc = nlp(text)
entities = [(ent.text, ent.label_) for ent in doc.ents]
```

---

## Этап 2: Скачивание связанных актов (цепочка) ⏱️ 3-4 дня

### 2.1 Парсинг страницы дела для поиска всех актов

**Проблема:** На странице дела (например, `kad.arbitr.ru/Card/...`) могут быть ссылки на:
- Решение первой инстанции
- Постановление апелляции
- Постановление кассации
- Определения (о принятии, об отложении и т.д.)

**Решение:** Парсить HTML таблицу с актами на странице дела.

**Файл:** `src/scraper/case_page_scraper.py`

```python
class CasePageScraper:
    async def get_all_documents(self, case_url: str) -> List[dict]:
        """Получить все документы по делу со страницы карточки."""
        await self.page.goto(case_url)

        # Найти таблицу с документами
        docs_table = await self.page.query_selector("table.documentsTable")

        documents = []
        for row in await docs_table.query_selector_all("tr"):
            doc_link = await row.query_selector("a[href$='.pdf']")
            if doc_link:
                documents.append({
                    "type": await self._get_doc_type(row),
                    "date": await self._get_doc_date(row),
                    "pdf_url": await doc_link.get_attribute("href"),
                    "instance_level": self._detect_instance(row_text),
                })

        return documents
```

### 2.2 Определение инстанции по типу документа

```python
def detect_instance_level(doc_type: str, court_name: str) -> int:
    """Определить уровень инстанции."""
    if "апелляц" in court_name.lower():
        return 2
    elif "кассац" in court_name.lower() or "окружной" in court_name.lower():
        return 3
    elif doc_type in ["Решение", "Определение"]:
        return 1
    return 1  # по умолчанию
```

### 2.3 Построение иерархии

**Логика:**
1. Скачать все акты по делу
2. Отсортировать по дате (старые → новые)
3. Определить parent_id по упоминанию в тексте
   - Апелляция содержит: "Обжалуется решение от ДД.ММ.ГГГГ"
   - Кассация содержит: "Обжалуется постановление апелляции от ДД.ММ.ГГГГ"

```python
def link_documents_hierarchy(documents: List[Document]) -> None:
    """Установить связи parent_document_id."""
    # Сортировка по дате и инстанции
    sorted_docs = sorted(documents, key=lambda d: (d.decision_date, d.instance_level))

    for doc in sorted_docs:
        if doc.instance_level > 1:
            # Искать в тексте упоминание обжалуемого акта
            parent = find_appealed_document(doc, sorted_docs)
            if parent:
                doc.parent_document_id = parent.id
                doc.save()
```

---

## Этап 3: Дедупликация и обновление статусов ⏱️ 2 дня

### 3.1 Дедупликация по SHA256

```python
import hashlib

def calculate_pdf_hash(pdf_path: str) -> str:
    """Вычислить SHA256 hash PDF файла."""
    sha256_hash = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# Проверка перед сохранением
pdf_hash = calculate_pdf_hash(pdf_path)
existing = session.query(Document).filter_by(pdf_hash=pdf_hash).first()
if existing:
    logger.info(f"Duplicate found: {existing.id}")
    return existing
```

### 3.2 Обновление статусов при обжаловании

```python
def update_parent_status(document: Document) -> None:
    """Обновить статус обжалуемого акта."""
    if not document.parent_document_id:
        return

    parent = session.query(Document).get(document.parent_document_id)

    # Если апелляция отменила решение
    if "отменить" in document.outcome.lower():
        parent.status = "overturned"
        parent.is_final = False

    # Если оставила в силе
    elif "оставить" in document.outcome.lower() and "без изменения" in document.outcome.lower():
        parent.status = "active"
        parent.is_final = True

    parent.save()
```

### 3.3 Мониторинг обновлений

```python
async def check_case_updates(case: Case) -> List[Document]:
    """Проверить появились ли новые акты по делу."""
    # Получить все акты со страницы дела
    current_docs = await scraper.get_all_documents(case.kad_url)

    # Найти новые (не в БД)
    existing_hashes = {doc.pdf_hash for doc in case.documents}

    new_docs = []
    for doc_info in current_docs:
        pdf_hash = calculate_pdf_hash(doc_info["pdf_url"])
        if pdf_hash not in existing_hashes:
            new_docs.append(doc_info)

    return new_docs
```

---

## Этап 4: Парсинг апелляционных судов ⏱️ 5-7 дней

### 4.1 Список апелляционных судов

**21 апелляционный суд РФ:**
- 01-й (Владимир)
- 02-й (Киров)
- ...
- 21-й (Севастополь)

### 4.2 Workflow для каждого суда

```
1. Открыть kad.arbitr.ru
2. Выбрать апелляционный суд (код А21, А28 и т.д.)
3. Указать период (2020-2025)
4. Для каждой страницы результатов:
   4.1. Спарсить дела
   4.2. Для каждого дела:
        - Открыть страницу дела
        - Получить все акты (первая инстанция + апелляция)
        - Скачать PDF каждого акта
        - Проверить дедупликацию
        - Извлечь метаданные
        - Установить связи parent_document_id
        - Сохранить в БД
```

### 4.3 Приоритизация

**Стратегия "сверху вниз":**
1. Парсим апелляционные суды (инстанция 2)
2. Для каждого акта апелляции ищем решение первой инстанции
3. Если решения нет в БД - скачиваем и парсим
4. Потом парсим кассационные суды (инстанция 3)
5. Для каждой кассации ищем апелляцию и первую инстанцию

**Преимущества:**
- Актуальные дела (дошедшие до апелляции) попадают в БД быстрее
- Естественная фильтрация значимых дел
- Постепенное заполнение иерархии

---

## Этап 5: Интеграция с БД и MinIO ⏱️ 2-3 дня

### 5.1 Alembic миграции

```bash
# Создать миграцию
alembic revision --autogenerate -m "Add court documents schema with hierarchy"

# Применить
alembic upgrade head
```

### 5.2 Сохранение PDF в MinIO

```python
class DocumentStorage:
    def __init__(self, minio_client):
        self.minio = minio_client
        self.bucket = "court-documents"

    def save_pdf(self, pdf_path: str, case_number: str, doc_id: UUID) -> str:
        """Сохранить PDF в MinIO и вернуть путь."""
        object_name = f"{case_number}/{doc_id}.pdf"

        self.minio.fput_object(
            self.bucket,
            object_name,
            pdf_path,
        )

        return object_name
```

### 5.3 Celery задачи для фоновой обработки

```python
@celery.task
def parse_and_save_document(pdf_url: str, case_id: UUID):
    """Скачать, распарсить и сохранить документ."""
    # 1. Скачать PDF
    pdf_path = download_pdf(pdf_url)

    # 2. Проверить дедупликацию
    pdf_hash = calculate_pdf_hash(pdf_path)
    if Document.query.filter_by(pdf_hash=pdf_hash).first():
        return

    # 3. Парсинг
    parser = CourtDocumentParser()
    metadata = parser.parse_pdf(pdf_path)

    # 4. Сохранить в MinIO
    storage = DocumentStorage()
    minio_path = storage.save_pdf(pdf_path, metadata["case_number"], uuid4())

    # 5. Сохранить в БД
    document = Document(
        case_id=case_id,
        pdf_hash=pdf_hash,
        pdf_path=minio_path,
        **metadata
    )
    session.add(document)
    session.commit()

    # 6. Обновить статус parent
    update_parent_status(document)
```

---

## Этап 6: ML и поиск ⏱️ 5-7 дней

### 6.1 Генерация embeddings

```python
from openai import OpenAI

client = OpenAI()

def generate_embedding(text: str) -> List[float]:
    """Создать embedding для семантического поиска."""
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

# Сохранение в БД
document.decision_embedding = generate_embedding(document.outcome_full)
```

### 6.2 Семантический поиск (pgvector)

```sql
-- Найти похожие решения
SELECT * FROM documents
ORDER BY decision_embedding <-> '[embedding вектор]'
LIMIT 10;
```

### 6.3 Full-text search

```python
from sqlalchemy import func

# PostgreSQL tsvector
Document.search_vector = func.to_tsvector('russian', Document.outcome_full)

# Поиск
results = session.query(Document).filter(
    Document.search_vector.match('взыскание убытков', postgresql_regconfig='russian')
).all()
```

---

## Приоритезация задач

### Неделя 1-2: MVP
- ✅ Парсинг 3 страниц (готово)
- ✅ Скачивание PDF (готово)
- ⏳ PDF парсер (метаданные)
- ⏳ БД схема + миграции
- ⏳ Скачивание всех актов по делу

### Неделя 3-4: Масштабирование
- Парсинг 40 страниц (январь 2024)
- Иерархия актов + обновление статусов
- Дедупликация
- Celery задачи для фоновой обработки

### Неделя 5-6: Апелляционные суды
- Парсинг 21 апелляционного суда
- Спуск до первой инстанции
- Мониторинг обновлений

### Неделя 7+: ML и поиск
- Embeddings для семантического поиска
- NER для извлечения сущностей
- Full-text search
- API для поиска

---

## Метрики успеха

**Количество:**
- 1000+ дел (январь 2024)
- 10,000+ дел (2024 год)
- 100,000+ дел (2020-2025, 21 апелляционный суд)

**Качество:**
- 95%+ точность извлечения номера дела
- 90%+ точность извлечения резолютивной части
- 100% дедупликация (нет дублей PDF)

**Связность:**
- 80%+ актов с установленным parent_document_id
- 100% актов с корректным instance_level
