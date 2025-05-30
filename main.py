import os
import subprocess
import datetime
import sys
import shutil
from pathlib import Path
import argparse # コマンドライン引数処理用
import tempfile # 一時ディレクトリ作成用

# PDF作成に必要なライブラリ (uvで管理されている前提)
import img2pdf
from PIL import Image

# --- 定数 ---
SCRIPT_DIR = Path(__file__).resolve().parent
APPLESCRIPT_NAME = "auto_screenshot.applescript" # AppleScriptファイル名
APPLESCRIPT_PATH = SCRIPT_DIR / APPLESCRIPT_NAME

# --- PDF作成関数 (変更なし) ---
def create_pdf_from_images_internal(image_folder_path_str: str, pdf_output_path_str: str) -> bool:
    image_folder = Path(image_folder_path_str)
    pdf_path = Path(pdf_output_path_str)

    if not image_folder.is_dir():
        print(f"エラー: 画像フォルダ '{image_folder}' が見つかりません。")
        return False

    image_files = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')

    print(f"画像フォルダ '{image_folder}' をスキャンしています...")
    for item_path in sorted(image_folder.iterdir()):
        if item_path.is_file() and item_path.suffix.lower() in valid_extensions:
            image_files.append(str(item_path))
            print(f"  検出: {item_path.name}")

    if not image_files:
        print(f"エラー: 画像フォルダ '{image_folder}' に処理可能な画像ファイルが見つかりません。")
        return False # この関数が呼ばれる前にメイン処理でチェック済みのはずだが念のため

    print(f"{len(image_files)} 個の画像ファイルをPDFに変換します...")
    try:
        pdf_bytes = img2pdf.convert(image_files)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"PDFが正常に作成されました: {pdf_path}")
        return True
    except Exception as e:
        print(f"PDF作成中にエラーが発生しました: {e}")
        return False

# --- AppleScript実行関数 (変更なし) ---
def run_applescript_process(target_applescript_path: Path, image_output_folder_path: str) -> bool:
    if not target_applescript_path.is_file():
        print(f"エラー: 指定されたAppleScriptが見つかりません: {target_applescript_path}")
        return False

    print(f"AppleScript '{target_applescript_path.name}' を実行します...")
    print(f"AppleScriptへの引数 (一時的な画像保存先): {image_output_folder_path}")
    
    try:
        process = subprocess.Popen(['osascript', str(target_applescript_path), image_output_folder_path])
        process.wait()

        if process.returncode == 0:
            print("AppleScriptの実行が正常に完了しました。")
            return True
        else:
            print(f"エラー: AppleScriptの実行に失敗しました (終了コード: {process.returncode})。")
            return False
    except FileNotFoundError:
        print("エラー: 'osascript' コマンドが見つかりません。Xcode Command Line Toolsがインストールされているか確認してください。")
        return False
    except Exception as e:
        print(f"AppleScript実行中に予期せぬエラーが発生しました: {e}")
        return False

# --- メイン処理 ---
def main():
    # 1. コマンドライン引数の設定と解析
    parser = argparse.ArgumentParser(
        description="スクリーンショットを一時フォルダに保存し、指定されたパスにPDFを作成します。\nAppleScriptファイル 'auto_screenshot.applescript' がこのスクリプトと同じディレクトリにある必要があります。\n中間画像ファイルはPDF作成後に自動的に削除されます。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--output-pdf-path",
        required=True,
        help="作成するPDFのフルパス (例: ~/Documents/MyReport.pdf)"
    )
    args = parser.parse_args()

    print("自動スクリーンショット & PDF作成スクリプト (Python版)")
    print("--------------------------------------------------")

    # 2. AppleScriptファイルの存在確認
    if not APPLESCRIPT_PATH.is_file():
        print(f"エラー: 必要なAppleScriptファイルが見つかりません: {APPLESCRIPT_PATH}")
        sys.exit(1)

    # 3. 引数からPDF出力パス情報を構築
    try:
        output_pdf_path_obj = Path(args.output_pdf_path).expanduser().resolve()
        output_pdf_dir = output_pdf_path_obj.parent
        
        # PDFファイル名に拡張子がない場合は .pdf を付与 (ユーザーが拡張子なしで指定した場合のケア)
        if not output_pdf_path_obj.suffix.lower() == ".pdf":
            output_pdf_path_obj = output_pdf_path_obj.with_suffix(".pdf")
            print(f"情報: PDF出力パスに拡張子 .pdf を追加しました: {output_pdf_path_obj}")

    except Exception as e:
        print(f"エラー: 指定されたPDF出力パスの処理中に問題が発生しました: {e}")
        sys.exit(1)

    # PDF出力先ディレクトリの作成 (存在しない場合)
    try:
        output_pdf_dir.mkdir(parents=True, exist_ok=True)
        print(f"PDF出力先ディレクトリを確認（または作成）しました: {output_pdf_dir}")
    except Exception as e:
        print(f"エラー: PDF出力先ディレクトリ '{output_pdf_dir}' の作成に失敗しました: {e}")
        sys.exit(1)

    print(f"設定情報:")
    print(f"  最終PDF出力ファイル: {output_pdf_path_obj}")
    print("--------------------------------------------------")

    # 4. 一時的な画像保存フォルダの準備とメイン処理の実行
    temp_image_dir_path_for_message = "" # 削除後のメッセージ表示用にパス文字列を保持
    try:
        with tempfile.TemporaryDirectory(prefix="screenshots_workflow_") as temp_dir_name:
            image_subfolder_path = Path(temp_dir_name)
            temp_image_dir_path_for_message = str(image_subfolder_path) # withブロックを抜ける前にパスを保存
            print(f"一時的な画像保存フォルダを作成しました: {image_subfolder_path}")

            # 5. AppleScriptの実行
            if not run_applescript_process(APPLESCRIPT_PATH, str(image_subfolder_path)):
                # AppleScriptが失敗した場合、tempfileが自動でクリーンアップするので追加の削除処理は不要
                sys.exit(1)

            # 6. AppleScriptによって画像が実際に保存されたか確認
            image_files_exist = False
            valid_extensions_check = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
            if image_subfolder_path.is_dir(): # 念のためフォルダ存在確認
                for item_path in image_subfolder_path.iterdir():
                    if item_path.is_file() and item_path.suffix.lower() in valid_extensions_check:
                        image_files_exist = True
                        break
            
            if not image_files_exist:
                print(f"エラー: AppleScriptは実行されましたが、一時フォルダ '{image_subfolder_path}' に処理可能な画像ファイルが見つかりません。")
                # tempfileが自動でクリーンアップ
                sys.exit(1) # 異常終了

            # 7. PDF作成処理の実行
            print("スクリーンショット画像のPDF化を開始します...")
            if not create_pdf_from_images_internal(str(image_subfolder_path), str(output_pdf_path_obj)):
                print("PDF作成に失敗しました。")
                # tempfileが自動でクリーンアップ
                sys.exit(1)
        
        # with tempfile.TemporaryDirectory() ブロックを正常に抜けた場合、一時フォルダは自動的に削除されている
        print(f"一時的な画像保存フォルダ '{temp_image_dir_path_for_message}' は処理後に自動的に削除されました。")

    except FileNotFoundError: # tempfile.TemporaryDirectory が稀に発生させる場合がある
        print(f"エラー: 一時フォルダの作成またはアクセスに失敗しました。システムの一時フォルダ設定を確認してください。")
        sys.exit(1)
    except Exception as e: 
        print(f"一時フォルダの処理またはメイン処理の実行中に予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        # この場合も、もし with ブロックに入っていれば tempfile はクリーンアップを試みる
        sys.exit(1)

    print("--------------------------------------------------")
    print("全ての処理が正常に完了しました！")
    print(f"作成されたPDFファイル: {output_pdf_path_obj}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nユーザーにより処理が中断されました。")
        # 一時フォルダは tempfile の管理下なら適切に処理されるはず
        sys.exit(130) 
    except SystemExit as e: # sys.exit() をキャッチしてそのまま終了
        raise
    except Exception as e: # 予期せぬトップレベルのエラー
        print(f"スクリプト全体で予期せぬエラーが発生し、処理を終了します: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
