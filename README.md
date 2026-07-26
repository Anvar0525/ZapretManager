# Zapret Manager

Мини-приложение для Windows: запуск [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) без чёрного окна терминала.

## Скачать программу

1. Откройте [Releases](https://github.com/Anvar0525/ZapretManager/releases)
2. Скачайте **ZapretManager.exe**
3. Положите его в **любую папку** (например `C:\Zapret` или папку на рабочем столе)  
   Не оставляйте exe «в воздухе» без папки — рядом с ним будет скачиваться zapret
4. Запустите exe и подтвердите UAC (права администратора)
5. Если видите блок **«Zapret ещё не скачан»** — нажмите **«Скачать zapret»**  
   Рядом с exe появится папка `zapret-discord-youtube-...`
6. Нажмите **«Запустить»**

Готово. Отдельно качать Flowseal вручную не нужно — менеджер скачает сам.

## Возможности
- Окно + трей
- Старт / стоп / перезапуск
- Выбор стратегии
- Всегда используется самая новая локальная версия zapret
- Скачивание и обновление zapret с GitHub

## Сборка из исходников (для разработчиков)
Нужен Python 3.11+.

```bat
install_deps.bat
build_exe.bat
```

Готовый файл: `dist\ZapretManager.exe`

## Важно
Это обёртка над [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube), не замена самого zapret.
