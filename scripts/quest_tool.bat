@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set MODE=%1
set TARGET_PATH=%2

if "%MODE%"=="import" goto IMPORT
if "%MODE%"=="config" goto CONFIG
if "%MODE%"=="test" goto TEST
echo.
echo [エラー] 不正なモードです。"import", "config", または "test" を指定してください。
pause
exit /b 1

:IMPORT
echo.
echo ========================================
echo   VRChat Picture Import Tool
echo ========================================
echo.
echo [1] ADBサーバー起動中...
adb start-server
if errorlevel 1 (
    echo [エラー] ADBコマンドが見つかりません。ADB をインストールしてください。
    pause
    exit /b 1
)

echo.
echo [2] デバイス確認中...
adb devices
echo.

:: TARGET_PATH が指定されていない場合のデフォルト値
if not defined TARGET_PATH (
    set "TARGET_PATH=S:\VRChat-Picture\Pics"
)

echo [3] VRChatスクリーンショットをコピー中...
echo    ソース: /storage/emulated/0/Pictures/VRChat
echo    ターゲット: !TARGET_PATH!
echo.

:: ターゲットディレクトリ作成
if not exist "!TARGET_PATH!" (
    mkdir "!TARGET_PATH!"
    if errorlevel 1 (
        echo [エラー] ターゲットフォルダの作成に失敗しました。
        echo パスを確認してください: !TARGET_PATH!
        pause
        exit /b 1
    )
)

adb pull "/storage/emulated/0/Pictures/VRChat" "!TARGET_PATH!"
if errorlevel 1 (
    echo.
    echo [警告] ADB転送に失敗した可能性があります。
    echo - Questが正しく接続されているか確認してください
    echo - USBデバッグモードが有効になっているか確認してください
    pause
    exit /b 1
) else (
    echo.
    echo [成功] ファイル転送が完了しました。
)

echo.
echo [4] ファイルをリネーム中 (_Quest 追加)...
setlocal enabledelayedexpansion
if exist "!TARGET_PATH!\VRChat" (
    for /r "!TARGET_PATH!\VRChat" %%A in (*) do (
        set "filename=%%~nA"
        set "extension=%%~xA"
        :: 拡張子の前に _Quest を追加（例: photo.png → photo_Quest.png）
        set "newname=!filename!_Quest!extension!"
        if not "!filename!"=="!filename:_Quest=!" (
            echo   スキップ: %%A （既に _Quest が含まれています）
        ) else (
            ren "%%A" "!newname!"
            if not errorlevel 1 (
                echo   リネーム: !filename!!extension! → !newname!
            )
        )
    )
    endlocal
)

echo.
echo [完了] ファイル転送とリネームが完了しました。
echo ターゲットフォルダ: !TARGET_PATH!
pause
exit /b 0

:CONFIG
echo.
echo ========================================
echo   接続状況確認
echo ========================================
echo.
adb devices -l
echo.
pause
exit /b 0

:TEST
echo.
echo ========================================
echo   テストモード
echo ========================================
echo.
echo [テスト] ADB バージョン確認
adb version
echo.
echo [テスト] デバイス リスト
adb devices
echo.
echo [テスト] 設定ファイル内容 (config.json)
echo ----------------------------------------
if exist "config.json" (
    type "config.json"
) else (
    echo config.json ファイルが見つかりません。
)
echo ----------------------------------------
echo.
echo [テスト] ターゲットパスの確認
echo.
echo [GUI設定] config.json から読み込んだ値:
if exist "config.json" (
    powershell -NoProfile -Command "Get-Content 'config.json' | ConvertFrom-Json | Select-Object target_path, rename_suffix, adb_auto_start | Format-Table -AutoSize" 2>nul
    if errorlevel 1 (
        echo （PowerShellで解析できませんでした）
    )
) else (
    echo （config.jsonが見つかりません）
)
echo.
echo [実行時引数] コマンドラインから渡された値:
if defined TARGET_PATH (
    echo ターゲットパス（第2引数）: !TARGET_PATH!
) else (
    echo ターゲットパス（第2引数）: 指定されていません
)
echo.
echo ========================================
echo テストモードが終了しました。いずれかのキーを押してこの画面を閉じます。
pause
exit /b 0
