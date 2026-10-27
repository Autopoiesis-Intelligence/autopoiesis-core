Agent: Claude

# G3: план реализации привязки DONE к коммиту

Claude, 2026-10-27. **План, не реализация.** Код не менялся. База: кандидат `bbf6a4410a6f5f5fc1d028ff9abd176211455eaf`.

## 0. Находка при подготовке плана

Путей к DONE сейчас три, а не один:
1. `orchestrator.run_cycle` — координатор;
2. `run_tasks.py`, тип задачи `update_task_status` со `status: DONE` (`run_tasks.py:147–163`): DONE по дайджесту живого каталога. Используется в `tests/test_task_lifecycle.py:251, 325` и `tests/test_queue_snapshot_validation.py:129`;
3. шаг seed в `.github/workflows/ci.yml` (около строки 270): синтетическая проба DONE через `revision`.

Если G3 закроет только путь 1, гарантия «DONE означает проверенный коммит» останется ложной. Поэтому план закрывает все три. Путь 3 — **изменение workflow**, на него нужно отдельное «да» владельца.

## 1. Изменения по файлам

| Файл | Изменение | Зачем |
|---|---|---|
| `autopoesis/task_queue.py` | `QUEUE_VERSION = 3`. Поля `commit_sha` и `tree_sha` (40 или 64 hex) в `VERIFICATION_RECORDED` и в DONE. `advance_task(..., commit_sha, tree_sha)` принимает DONE только при совпадении с последним привязанным PASS (задача, попытка, аренда, commit, tree). DONE пишет `revision_semantics = "tested_commit_tree"`. Параметр `revision` для DONE убирается. Ключ очереди `legacy_history_length`: DONE со старой семантикой допустим только по индексу меньше него. `migrate_queue`: v1 → v2 → v3, при v2 → v3 события не меняются, ставится `legacy_history_length = len(history)`, резервная копия `.v2.bak` | п.3, 4, 6 контракта G4 §4 |
| `autopoesis/orchestrator.py` | Новая `_snapshot(root) -> (commit_sha, tree_sha, path)`: `git rev-parse --verify HEAD^{commit}`, `git rev-parse <commit>^{tree}`, `git archive <commit>` с извлечением во временный каталог через `tarfile` с `filter="data"`. Обработчик получает путь снимка, а не `repository_root`. Перед DONE повторная сверка `git rev-parse <commit>^{tree} == tree_sha`. Проверка «живое дерево = протестированное» удаляется: она больше ничего не гарантирует. Не git-каталог или ошибка git — `RECOVERY_REQUIRED`, без записи | п.1, 2, 5 |
| `run_tasks.py` | `update_task_status` со `status: DONE` отклоняется: «DONE ставит только координатор». Остальные статусы как раньше | закрывает путь 2 |
| `.github/workflows/ci.yml` (**нужно «да»**) | Шаг seed: проба DONE пишет `commit_sha = github.sha` и `tree_sha = git rev-parse HEAD^{tree}` вместо `revision` | закрывает путь 3 |
| `tests/test_commit_binding.py` (новый) | Отрицательные тесты, §2 | |
| `tests/test_orchestrator.py` | Фикстура репозитория становится git-репозиторием во временном каталоге (`git init`, commit). Тесты на `revision` переводятся на commit/tree | |
| `tests/test_task_lifecycle.py`, `tests/test_queue_snapshot_validation.py` | Сценарии с `update_task_status → DONE` переходят на прямой вызов `advance_task` с commit/tree или ожидают отказа | |
| `tests/test_queue_migration.py` | v2 → v3 и v1 → v3; повышения семантики нет | |
| `tests/test_queue_history_validation.py` | Подтесты `done_evidence` переходят на commit/tree | |
| `tests/fixtures/queue_v2_done_from_bbf6a44.json` (новый) | Очередь v2, записанная кодом `bbf6a44` | реальный формат для миграции |
| `tests/*` с `"version": 2` в фикстурах | 2 → 3 | |

Не меняется: `executor.py` (дайджест каталога остаётся дополнительным полем `source_digest`), `queue_snapshot.py`, права, ruleset, плановый workflow.

## 2. Отрицательные тесты (сначала красные на `bbf6a44`)

| # | Сценарий | Ожидание |
|---|---|---|
| 1 | PASS для коммита A, DONE для коммита B | `advance_task` отказывает; при повторе истории — `EvolutionError` |
| 2 | PASS и DONE с одинаковым commit, но разным tree | отказ в `advance_task` и при повторе |
| 3 | `tree_sha` не является деревом `commit_sha` в git | `run_cycle` → `RECOVERY_REQUIRED`, DONE не записан |
| 4 | Рабочий каталог изменили после теста | DONE ссылается на проверенный коммит; результат не зависит от каталога |
| 5 | Рабочий каталог «грязный» до запуска | обработчик видит снимок коммита: файл, которого нет в коммите, в снимке отсутствует |
| 6 | Обработчик пишет в свой снимок | `tree_sha` в записи не меняется; DONE ссылается на исходный коммит |
| 7 | После миграции v2 → v3 добавлен новый DONE со старой семантикой | отказ при повторе: индекс ≥ `legacy_history_length` |
| 8 | Миграция v2 → v3 | старые DONE сохраняют `tested_source_snapshot_sha256`, ни один не становится `tested_commit_tree` |
| 9 | Повтор после истечения аренды: PASS от попытки 1, DONE в попытке 2 | отказ (попытка и аренда не совпадают) |
| 10 | `update_task_status → DONE` через `run_tasks.py` | отказ |
| 11 | `repository_root` не git-репозиторий | `RECOVERY_REQUIRED`, без записи |
| 12 | Повторная миграция v3 | без изменений, байт в байт |

## 3. Порядок работы после согласования

1. Тесты из §2 на `bbf6a44`: убедиться, что они красные по нужной причине.
2. Реализация `task_queue.py`, затем `orchestrator.py`, затем `run_tasks.py`.
3. Миграция и фикстура v2.
4. Правка `ci.yml` (только после «да»).
5. Новый SHA, локальные тесты, полная dispatch-матрица (11 сценариев, как для `bbf6a44`) и PR-независимые проверки.
6. Отчёт: SHA, файлы с обоснованием, тесты, run id, что доказано и что нет, совместимость.

## 4. Совместимость

- Очереди v1 и v2 читаются только после `migrate_queue_file`. Их DONE остаются со старой семантикой и записываются как исторические, а не как доказанные по коммиту.
- Артефакты прошлых запусков CI (v2) при restore на новом коде отклоняются проверкой версии. Так и задумано (fail-closed), это не регрессия.
- Внешних потребителей формата очереди нет: production-цикл не запускался.

## 5. Что останется непроверенным после G3

- Исполнение в отдельной job без прав (часть G3 для CI): в этом плане обработчик изолирован снимком, но не правами процесса. Отдельная job — правка workflow и тема плана G5.
- Всё по этапу 2 (G4 §3).
- Независимый аудит.

## 6. Решения, которые нужны до начала

1. Согласие GPT с планом (особенно §0 и отказ от DONE через `run_tasks.py`).
2. «Да» владельца на правку шага seed в `ci.yml` (путь 3). Без неё G3 можно сделать только частично, и это будет явно написано в отчёте.
3. Тест `e88765b` из #60 не переносится, пока не будет отдельного согласования. Гарантию, которую он проверяет («аренда, истёкшая посреди выполнения, не доходит до DONE»), в кандидате уже проверяет `test_stale_worker_cannot_record_or_complete_after_reassignment`. Сравнение двух тестов будет в отчёте G3.
