# Zapret Manager

Мини-приложение для Windows: запуск `zapret-discord-youtube` без чёрного окна терминала.

## Возможности
- Окно + трей
- Старт / стоп / перезапуск
- Выбор стратегии и версии
- Скачивание/обновление zapret с GitHub Flowseal

## Для пользователей (без Python)
1. Скачайте `ZapretManager.exe` из [Releases](https://github.com/Anvar0525/ZapretManager/releases) (когда появится)  
   или соберите сами (см. ниже)
2. Запустите exe → подтвердите UAC
3. Если zapret ещё нет → **«Скачать zapret»**
4. **«Запустить»**

Подробнее: `КАК_ПОЛЬЗОВАТЬСЯ.txt`

## Сборка exe
Нужен Python 3.11+.

```bat
install_deps.bat
build_exe.bat
```

Готовый файл: `dist\ZapretManager.exe`

## Разработка
```bat
install_deps.bat
Zapret Manager.vbs
```

## Важно
Это обёртка над [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube), не замена самого zapret.
