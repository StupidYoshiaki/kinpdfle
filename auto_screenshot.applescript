-- グローバル変数の宣言
global originalScreenshotLocation
global appName
global waitSeconds

-- スクリプトのメイン実行ブロック
on run argv
    -- 初期設定
    set appName to "Kindle" -- 対象アプリケーション名
    set waitSeconds to 0.5 -- スクリーンショットのタイミング調整用

    set targetSaveFolder to missing value
    set originalScreenshotLocation to "" -- 初期化

    try
        -- 1. 保存先フォルダを取得 (引数またはダイアログ)
        if (count of argv) > 0 then
            set targetPathString to item 1 of argv
            try
                set targetSaveFolder to (POSIX file targetPathString) as alias
            on error
                display alert "エラー" message "引数で指定されたパスが無効です: " & targetPathString buttons {"OK"} default button "OK"
                error number -128
            end try
        else
            set targetSaveFolder to choose folder with prompt "スクリーンショットの保存先フォルダを選択してください:"
        end if

        -- 2. 現在のスクリーンショット保存先をバックアップし、新しい保存先を設定
        set originalScreenshotLocation to getCurrentScreencaptureSetting("location")

        -- 新しい保存先を設定
        do shell script "defaults write com.apple.screencapture location " & quoted form of (POSIX path of targetSaveFolder)
        do shell script "killall SystemUIServer" -- 設定をシステムに反映

        -- 3. メイン処理の実行
        runMainScreenshotLogic()

        -- 4. 処理終了後、元の設定に戻す (正常終了時)
        restoreScreencaptureSettings()
        display alert "完了" message "処理が正常に終了しました。" buttons {"OK"} default button "OK"

    on error errMsg number errNum
        -- 5. エラー発生時も元の設定に戻す
        restoreScreencaptureSettings()
        display alert "エラー" message "エラーが発生しました: " & errMsg & " (エラー番号: " & errNum & ")" buttons {"OK"} default button "OK"
        -- error errMsg number errNum -- 必要に応じてエラーを再スローしてスクリプトを停止
    end try
end run

-- スクリーンショットのメインロジック
on runMainScreenshotLogic()
    -- OSバージョン確認
    set OSVer to do shell script "sw_vers -productVersion | cut -d '.' -f 1-2"
    set nOSVer to OSVer as number
    if nOSVer < 10.14 then
        display alert "このスクリプトはMojave以降のOSでしか使えません。"
        error number -128
    end if

    -- 範囲指定の確認 (保存先に関する説明を更新)
    display dialog "範囲指定は済んでいますか？" & return & "" & return & "範囲指定: 点線エリアを調整してください。" & return & "保存先: スクリプト起動時に指定/選択したフォルダに保存されます。" & return & "最後に右下のパネルをxで閉じるか「取り込む」を押します。" buttons {"はい", "設定する", "終了"} default button "はい" with title "選択範囲設定確認 Step0"
    set confirmPattern to button returned of result
    if confirmPattern = "終了" then error number -128
    if confirmPattern = "設定する" then openScreenshotTool()

    -- スクリーンショット回数の指定
    display dialog "スクショする回数（ページ数）を入力してください。" default answer "5" with title "自動スクショ Step1"
    set screenShotCount to (text returned of result) as integer

    -- ページ方向の指定
    display dialog "右開き？左開き？" buttons {"左", "右"} default button "右" with title "自動スクショ Step2"
    set pageDirection to button returned of result

    -- スクリーンショット取得とページ送りのループ
    repeat with i from 1 to screenShotCount
        takeScreenshot()
        turnPage(pageDirection)
    end repeat
end runMainScreenshotLogic

-- 現在のスクリーンショット関連設定を取得するハンドラ
on getCurrentScreencaptureSetting(settingKey)
    try
        return do shell script "defaults read com.apple.screencapture " & settingKey
    on error
        return "" -- 設定が存在しない場合は空文字 (デフォルト状態を示す)
    end try
end getCurrentScreencaptureSetting

-- スクリーンショット関連設定を元に戻すハンドラ
on restoreScreencaptureSettings()
    global originalScreenshotLocation
    try
        if originalScreenshotLocation is not "" then
            do shell script "defaults write com.apple.screencapture location " & quoted form of originalScreenshotLocation
        else
            -- 元の設定が空（デフォルト=Desktopなど）だった場合、キー自体を削除してデフォルトに戻す
            do shell script "defaults delete com.apple.screencapture location"
        end if
        do shell script "killall SystemUIServer" -- 設定をシステムに反映
    on error errMsg number errNum
        -- 元に戻す際にエラーが発生しても、ここでは致命的エラーとしない (ログ出力等を検討)
        log "スクリーンショット設定の復元中にエラー: " & errMsg
    end try
end restoreScreencaptureSettings

-- スクリーンショットを取得するハンドラ
on takeScreenshot()
    global appName, waitSeconds
    try
        tell application appName to activate
        delay waitSeconds -- アプリがアクティブになるまでの待ち時間
        tell application "System Events"
            key code 23 using {command down, shift down} -- Shift+Command+5 (スクリーンショットUI起動)
            delay waitSeconds
            key code 76 -- Enterキー (スクリーンショットUIの「取り込む」ボタン)
        end tell
    on error errMsg number errNum
        display alert "スクリーンショット取得中にエラー: " & errMsg
        error errNum
    end try
end takeScreenshot

-- ページをめくるハンドラ
on turnPage(direction)
    global appName, waitSeconds
    try
        tell application appName to activate
        delay waitSeconds
        tell application "System Events"
            if direction = "右" then
                keystroke (ASCII character 29) -- 右矢印キー
            else
                keystroke (ASCII character 28) -- 左矢印キー
            end if
            delay waitSeconds
        end tell
    on error errMsg number errNum
        display alert "ページ送り中にエラー: " & errMsg
        error errNum
    end try
end turnPage

-- スクリーンショットツールを起動するハンドラ (範囲設定用)
on openScreenshotTool()
    global appName
    try
        tell application appName to activate -- 事前にアプリをアクティブにしておく
        delay 0.2
        tell application "System Events"
            key code 23 using {command down, shift down} -- Shift+Command+5 (スクリーンショットUI起動)
        end tell
    on error errMsg number errNum
        display alert "スクリーンショットツールの起動中にエラー: " & errMsg
        error errNum
    end try
end openScreenshotTool
