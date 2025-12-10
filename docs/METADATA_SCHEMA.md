# Схема метаданных для судебных актов с иерархией

## Концепция

Каждое **дело** может иметь множество **актов** на разных инстанциях. Акты связаны между собой иерархией обжалования.

## Сущности БД

### 1. Case (Дело)

Основная сущность - карточка дела.

```python
class Case(Base):
    """Дело в арбитражном суде."""

    # Основные поля
    id: UUID (PK)
    case_number: str  # А83-1729/2024 (уникальный)
    case_type: str    # Исковое, особое производство и т.д.

    # Метаданные из КАД
    kad_url: str      # URL карточки дела
    court_code: str   # А83 (код суда первой инстанции)
    court_name: str   # "Арбитражный суд Республики Крым"
    filing_date: date # Дата подачи

    # Стороны
    plaintiff: str          # Истец
    defendant: str          # Ответчик
    third_parties: JSON     # Третьи лица

    # Предмет спора
    case_category: str      # Категория (налоговые, корпоративные и т.д.)
    subject_matter: str     # Суть спора (краткое описание)
    claim_amount: Decimal   # Сумма иска

    # Связи
    documents: List[Document]  # Все документы по делу

    # Мета
    created_at: datetime
    updated_at: datetime
    last_checked: datetime  # Последняя проверка обновлений
```

### 2. Document (Судебный акт)

Отдельный судебный акт (решение, определение, постановление).

```python
class Document(Base):
    """Судебный акт (решение, определение, постановление)."""

    # Основные поля
    id: UUID (PK)
    case_id: UUID (FK → Case)

    # Идентификация
    document_type: str       # "Решение", "Определение", "Постановление"
    instance_level: int      # 1 - первая, 2 - апелляция, 3 - кассация
    instance_type: str       # "Первая инстанция", "Апелляция", "Кассация"

    # Даты
    decision_date: date      # Дата принятия
    publication_date: date   # Дата изготовления в полном объеме
    announced_date: date     # Дата объявления резолютивной части

    # Суд
    court_code: str          # А21 (для апелляции), СИП (для кассации)
    court_name: str          # "Двадцать первый арбитражный апелляционный суд"

    # Состав суда
    presiding_judge: str     # Председательствующий судья (ФИО)
    judges: JSON             # Список всех судей [{fio, role}]
    secretary: str           # Секретарь судебного заседания

    # Статус акта
    status: str              # "active", "overturned", "modified", "pending"
    effective_date: date     # Дата вступления в законную силу
    is_final: bool           # Вступил ли в законную силу

    # Иерархия обжалования
    parent_document_id: UUID (FK → Document, nullable)  # Обжалуемый акт
    appealed_by: List[Document]  # Акты, обжалующие этот

    # Решение
    decision_type: str       # "Удовлетворить", "Отказать", "Частично удовлетворить"
    outcome: str             # Резолютивная часть (короткая)
    outcome_full: Text       # Полная резолютивная часть

    # Суммы
    awarded_amount: Decimal  # Взысканная сумма
    court_fees: Decimal      # Госпошлина

    # Файлы
    pdf_url: str             # Прямая ссылка на PDF
    pdf_path: str            # Путь в MinIO
    pdf_hash: str            # SHA256 для дедупликации

    # Извлеченные данные
    extracted_entities: JSON # Все извлеченные сущности
    legal_refs: JSON         # Ссылки на нормы права

    # Мета
    created_at: datetime
    updated_at: datetime
```

### 3. Entity (Извлеченная сущность)

NER-сущности из текста документа.

```python
class Entity(Base):
    """Извлеченная сущность из текста."""

    id: UUID (PK)
    document_id: UUID (FK → Document)

    # Тип сущности
    entity_type: str    # "PERSON", "ORG", "LAW", "DATE", "MONEY", "LOCATION"
    entity_value: str   # Текстовое значение

    # Контекст
    context: str        # Окружающий текст
    start_pos: int      # Позиция в тексте
    end_pos: int

    # Нормализация
    normalized: str     # Нормализованное значение

    # Связи
    linked_entity_id: UUID (FK → Entity, nullable)  # Связь с другой сущностью
```

### 4. LegalReference (Ссылка на норму права)

```python
class LegalReference(Base):
    """Ссылка на нормативный акт."""

    id: UUID (PK)
    document_id: UUID (FK → Document)

    # Идентификация НПА
    law_type: str       # "ГК РФ", "НК РФ", "АПК РФ" и т.д.
    article: str        # Статья
    paragraph: str      # Пункт, часть
    full_reference: str # Полная ссылка

    # Контекст применения
    context: str        # Как применялась норма
```

### 5. Party (Участник дела)

```python
class Party(Base):
    """Участник дела (организация или физлицо)."""

    id: UUID (PK)

    # Основные данные
    name: str           # Полное наименование
    short_name: str     # Краткое наименование
    party_type: str     # "legal_entity", "individual", "ip"

    # ИНН/ОГРН
    inn: str
    ogrn: str

    # Адрес
    address: str
    region: str

    # Связи с делами
    cases_as_plaintiff: List[Case]
    cases_as_defendant: List[Case]
```

### 6. CasePartyRole (Роль в деле)

Связующая таблица для many-to-many с ролями.

```python
class CasePartyRole(Base):
    """Роль участника в конкретном деле."""

    id: UUID (PK)
    case_id: UUID (FK → Case)
    party_id: UUID (FK → Party)

    role: str          # "plaintiff", "defendant", "third_party"
    role_details: str  # Дополнительно (например, "заявитель", "заинтересованное лицо")
```

## Ключевые индексы

```sql
-- Быстрый поиск по номеру дела
CREATE INDEX idx_case_number ON cases(case_number);

-- Поиск актов по делу
CREATE INDEX idx_document_case ON documents(case_id);

-- Иерархия обжалования
CREATE INDEX idx_document_parent ON documents(parent_document_id);

-- Поиск по статусу
CREATE INDEX idx_document_status ON documents(status, is_final);

-- Дедупликация по хэшу
CREATE UNIQUE INDEX idx_document_hash ON documents(pdf_hash);

-- Поиск по датам
CREATE INDEX idx_document_dates ON documents(decision_date, publication_date);

-- Поиск участников
CREATE INDEX idx_party_inn ON parties(inn);
CREATE INDEX idx_party_name ON parties(name);
```

## Пример иерархии актов

```
Case: А83-1729/2024
  │
  ├─ Document 1 (id=uuid1)
  │    Type: Решение
  │    Instance: 1 (Первая инстанция)
  │    Date: 15.03.2024
  │    Status: overturned (отменено апелляцией)
  │    parent_document_id: NULL
  │    appealed_by: [Document 2]
  │
  ├─ Document 2 (id=uuid2)
  │    Type: Постановление
  │    Instance: 2 (Апелляция)
  │    Date: 01.10.2025
  │    Status: active
  │    parent_document_id: uuid1  ← обжалует Document 1
  │    appealed_by: []
  │    Decision: "Оставить решение суда без изменения"
  │
  └─ Document 3 (id=uuid3)
       Type: Определение
       Instance: 1 (Первая инстанция)
       Date: 12.03.2024
       Status: active
       parent_document_id: NULL
       Decision: "О принятии искового заявления"
```

## Queries для типовых задач

### 1. Получить актуальный статус дела

```python
def get_final_decision(case_id: UUID) -> Document:
    """Получить финальное решение по делу (вступившее в силу)."""
    return (
        session.query(Document)
        .filter(
            Document.case_id == case_id,
            Document.is_final == True,
            Document.status == "active"
        )
        .order_by(Document.instance_level.desc())
        .first()
    )
```

### 2. Построить цепочку обжалования

```python
def get_appeal_chain(document_id: UUID) -> List[Document]:
    """Получить всю цепочку: первая инстанция → апелляция → кассация."""
    chain = []
    current = session.query(Document).get(document_id)

    # Спуск к первой инстанции
    while current.parent_document_id:
        chain.insert(0, current)
        current = session.query(Document).get(current.parent_document_id)

    chain.insert(0, current)

    # Подъем к вышестоящим
    # ... (рекурсивно через appealed_by)

    return chain
```

### 3. Найти дубликаты PDF

```python
def check_duplicate(pdf_hash: str) -> Optional[Document]:
    """Проверить, не скачан ли уже этот PDF."""
    return (
        session.query(Document)
        .filter(Document.pdf_hash == pdf_hash)
        .first()
    )
```

### 4. Получить дела для обновления статуса

```python
def get_cases_to_update(days: int = 7) -> List[Case]:
    """Получить дела, не проверявшиеся N дней."""
    threshold = datetime.now() - timedelta(days=days)
    return (
        session.query(Case)
        .filter(Case.last_checked < threshold)
        .all()
    )
```

## Поля для ML/поиска

### Embeddings для семантического поиска

```python
class Document(Base):
    # ... existing fields

    # Векторные представления для поиска
    decision_embedding: Vector(1536)  # Embedding резолютивной части
    full_text_embedding: Vector(1536) # Embedding полного текста

    # Индекс для vector search (pgvector)
    __table_args__ = (
        Index('idx_decision_emb', 'decision_embedding',
              postgresql_using='ivfflat',
              postgresql_with={'lists': 100}),
    )
```

### Теги и категории

```python
class Document(Base):
    # ... existing fields

    # ML-категоризация
    auto_categories: JSON     # Автоматически определенные категории
    legal_topics: JSON        # Правовые темы (налоги, договоры и т.д.)
    outcome_prediction: float # Вероятность удовлетворения иска

    # Full-text search
    search_vector: TSVECTOR   # PostgreSQL full-text search
```

## Следующие шаги

1. **Создать миграции Alembic** с этой схемой
2. **Реализовать PDF парсер** для извлечения полей
3. **Реализовать логику скачивания связанных актов**
4. **Добавить дедупликацию по hash**
5. **Реализовать обновление статусов**
