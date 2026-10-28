---
name: ssrf
description: Проверка SSRF с контрольным endpoint на attack box
argument-hint: "URL параметр"
arguments: url param
---
Проверь SSRF.

Цель: $0
Параметр: $1

Порядок:
1. Подними watcher/listener на attack box (HTTP или nc) и зафиксируй его адрес.
2. Отправь запрос с контрольным URL на этот адрес.
3. Подтверди получение запроса (step ID + лог).
4. Проверь обход фильтров (encoding, DNS rebinding, redirect, cloud metadata только если в scope).
5. Доведи до чтения внутреннего ресурса или metadata, если это в scope и подтверждено.
