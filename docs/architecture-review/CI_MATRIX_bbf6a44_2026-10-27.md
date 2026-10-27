Agent: Claude

# Матрица CI на новом SHA кандидата

Claude, 2026-10-27 ~13:20 UTC. Ветка `claude/project-thread-uewgy0`. Не независимый аудит.

## Изменение

- Было: `d191d2f658c4016d38f70e02997af9b52861d96e`.
- Стало: **`bbf6a4410a6f5f5fc1d028ff9abd176211455eaf`**.
- Разрешение: владелец, 2026-10-27 13:13 UTC.
- `git diff --stat d191d2f bbf6a44`: `.github/workflows/ci.yml | 2 +-`, одна строка: `queue["version"] = 2` → `999` в сценарии `bad_version`.
- Остальное дерево проверено: `git diff d191d2f bbf6a44 -- . ':!.github'` пуст.
- Локально на `bbf6a44`: `python -m unittest discover -s tests` = 254 OK. Код не менялся, поэтому результат тот же, что на `d191d2f`.

Все запуски ниже — `workflow_dispatch` ci.yml на `head_sha = bbf6a4410a6f5f5fc1d028ff9abd176211455eaf`. Запускались последовательно, каждый следующий после завершения предыдущего. Шаг отказа взят из API jobs, причина — из лога job.

| # | Сценарий | Ввод | Run | Ожидание | Итог | Шаг отказа | Причина в логе |
|---|---|---|---|---|---|---|---|
| 1 | seed | `seed_done_probe=true` | 40510236605 | success | success | — | — |
| 2 | clean restore | `restore_run_id=40510236605` | 40510308788 | success | success | — | — |
| 3 | tamper_bytes | restore 40510308788 + fault | 40510392684 | failure | failure | Validate and install prior queue snapshot | `TASK_QUEUE.json SHA-256 does not match source snapshot manifest` (`queue_snapshot.py:93`) |
| 4 | corrupt_json | то же | 40510441088 | failure | failure | то же | `Cannot read task queue: Expecting value…` (`task_queue.py:237`) |
| 5 | **bad_version** | то же | 40510490879 | failure | failure | то же | `Unsupported task queue format`: проверка версии (`task_queue.py:255`, `_validate_queue`) |
| 6 | bad_history | то же | 40510538254 | failure | failure | то же | `unsupported event type 'UNKNOWN_EVENT'` (`_validate_history`) |
| 7 | drop_queue | то же | 40510597405 | failure | failure | то же | `Queue snapshot file is missing` (`queue_snapshot.py:63`) |
| 8 | drop_manifest | то же | 40510643375 | failure | failure | то же | `Queue snapshot manifest file is missing` (`queue_snapshot.py:65`) |
| 9 | fault без restore | `restore_fault=bad_version` | 40510691795 | failure | failure | Reject a restore fault without a restore | шаг-охранник |
| 10 | устаревший источник | `restore_run_id=40510236605` (seed, а последний успешный — 40510308788) | 40510740316 | failure | failure | Verify prior run succeeded | `Source run 40510236605 is not the latest snapshot …; latest is 40510308788` |
| 11 | restore latest после всех отказов | `restore_run_id=latest` | 40510786891 | success | success | — | — |

## Вывод

- Все 11 исходов совпали с ожиданием. Каждый отказ произошёл на своём шаге и по своей причине.
- `bad_version` теперь отклоняется проверкой версии, а не чем-то посторонним.
- Отказы не испортили состояние: запуск 11 восстановился из последнего успешного снимка.
- Уровень доказательства: RUNTIME в тестовом workflow `ci.yml` на точном SHA. Это **не** независимый аудит и **не** production-цикл. Плановый workflow (#40) в кандидат не входит.

Не сделано по ограничению владельца: перенос теста `e88765b` из #60. Он меняет файл тестов, поэтому нужно отдельное согласование.

Скрипт прогона: `matrix.sh` в scratchpad сессии (в репозиторий не добавлялся).
