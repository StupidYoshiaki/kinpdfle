import os
import sys
import subprocess
from pathlib import Path
import argparse # コマンドライン引数処理用
import tempfile # 一時ディレクトリ作成用
import traceback # エラー詳細表示用

# PDF作成に必要なライブラリ (uvで管理されている前提)
import img2pdf
from PIL import Image, ImageFile

# Pillow で大きな画像を扱う際のエラー (DecompressionBombError) を緩和する設定 (任意)
ImageFile.LOAD_TRUNCATED_IMAGES = True # 破損画像を許容する場合（今回は不要かもしれない）
# Image.MAX_IMAGE_PIXELS = None # 画像サイズの制限を無効化（非常に大きな画像用）

# --- 定数 ---
SCRIPT_DIR = Path(__file__).resolve().parent
APPLESCRIPT_NAME = "auto_screenshot.applescript" # AppleScriptファイル名
APPLESCRIPT_PATH = SCRIPT_DIR / APPLESCRIPT_NAME

# --- PDF作成関数 (画像処理機能付き) ---
def create_pdf_from_images_internal(
    image_folder_path_str: str,
    pdf_output_path_str: str,
    resize_max_width: int,
    png_compress_level: int,
    convertToGrayscale: bool
) -> bool:
    image_folder = Path(image_folder_path_str)
    pdf_path = Path(pdf_output_path_str)

    if not image_folder.is_dir():
        print(f"エラー: 画像フォルダ '{image_folder}' が見つかりません。")
        return False

    original_image_paths = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff') # TIFFはimg2pdfのサポート状況による
    print(f"画像フォルダ '{image_folder}' をスキャンしています...")
    for item_path in sorted(image_folder.iterdir()): # ファイル名順で処理
        if item_path.is_file() and item_path.suffix.lower() in valid_extensions:
            original_image_paths.append(item_path)

    if not original_image_paths:
        print(f"エラー: 画像フォルダ '{image_folder}' に処理可能な画像ファイルが見つかりません。")
        return False

    processed_image_paths_for_pdf = [] # PDF化する画像の最終的なパスリスト

    print(f"\n画像処理を開始します (全 {len(original_image_paths)} ファイル):")
    for img_path_obj in original_image_paths:
        processed_file_path_to_use = img_path_obj # デフォルトは元ファイルパス
        try:
            print(f"  処理中: {img_path_obj.name}")
            with Image.open(img_path_obj) as img:
                current_width, current_height = img.size
                processed_img = img.copy() # 元の画像を保持するためにコピーを操作

                # 1. リサイズ (指定された最大幅を超え、かつresize_max_widthが0より大きい場合)
                if resize_max_width > 0 and current_width > resize_max_width:
                    ratio = resize_max_width / float(current_width)
                    new_height = int(float(current_height) * ratio)
                    print(f"    リサイズ: {current_width}x{current_height} -> {resize_max_width}x{new_height}")
                    processed_img = processed_img.resize((resize_max_width, new_height), Image.Resampling.LANCZOS)

                # 2. グレースケール変換 (オプション)
                if convertToGrayscale:
                    print(f"    グレースケールに変換")
                    processed_img = processed_img.convert("L")
                
                # 3. アルファチャンネルの処理 (PNG/PDF互換性のため)
                if processed_img.mode == 'RGBA' or processed_img.mode == 'LA':
                    print(f"    アルファチャンネルを処理中 (モード: {processed_img.mode})")
                    # 新しい背景イメージ(白)を作成し、そこに元のイメージをペースト（アルファをマスクとして使用）
                    if processed_img.mode == 'RGBA':
                        background = Image.new("RGB", processed_img.size, (255, 255, 255))
                        alpha_channel = processed_img.split()[-1] # RGBAのAチャンネル
                        background.paste(processed_img, (0, 0), mask=alpha_channel)
                        processed_img = background
                        print(f"      RGBA -> RGB に変換 (背景: 白)")
                    elif processed_img.mode == 'LA':
                        background = Image.new("L", processed_img.size, 255) # グレースケールの白
                        alpha_channel = processed_img.split()[-1] # LAのAチャンネル
                        background.paste(processed_img, (0, 0), mask=alpha_channel)
                        processed_img = background
                        print(f"      LA -> L に変換 (背景: 白)")
                
                # 処理した画像を一時フォルダ内の元のファイルに上書き保存
                # (tempfileが最後にフォルダごと削除するので、上書きで問題ない)
                target_save_path = img_path_obj 
                
                print(f"    PNGとして最適化保存 (圧縮レベル: {png_compress_level}) -> {target_save_path.name}")
                processed_img.save(target_save_path, "PNG", optimize=True, compress_level=png_compress_level)
                processed_file_path_to_use = target_save_path

        except Exception as e:
            print(f"警告: 画像 '{img_path_obj.name}' の処理中にエラーが発生しました: {e}")
            print(f"      詳細: {traceback.format_exc().splitlines()[-1]}") # エラーの最終行のみ表示
            print(f"      この画像は元の状態でPDFに追加されます（もし可能なら）。")
            # processed_file_path_to_use は変更されず、元の img_path_obj が使われる
        
        processed_image_paths_for_pdf.append(str(processed_file_path_to_use))


    if not processed_image_paths_for_pdf:
        print(f"エラー: PDFに含めることができる画像がありませんでした。")
        return False

    print(f"\n{len(processed_image_paths_for_pdf)} 個の画像（処理済み含む）をPDFに変換します...")
    try:
        pdf_bytes = img2pdf.convert(processed_image_paths_for_pdf)
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
        formatter_class=argparse.RawTextHelpFormatter # ヘルプメッセージの改行を維持
    )
    parser.add_argument(
        "--output-pdf-path",
        required=True,
        help="作成するPDFのフルパス (例: ~/Documents/MyReport.pdf)"
    )
    parser.add_argument(
        "--image-max-width",
        type=int,
        default=0, # デフォルト0はリサイズなし
        help="PDFに含める画像の最大幅 (ピクセル)。0でリサイズなし。 (例: 1920)"
    )
    parser.add_argument(
        "--png-compress-level",
        type=int,
        default=8, # Pillowのデフォルトは通常6あたり。0-9の範囲。
        choices=range(0,10), # 0から9までの整数
        metavar="[0-9]",
        help="PNG画像の圧縮レベル (0=無圧縮, 1=最速, 9=最高圧縮)。 (例: 6)"
    )
    parser.add_argument(
        "--grayscale",
        action="store_true", # 指定されるとTrueになるフラグ
        help="画像をグレースケールに変換します。"
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
    print(f"  画像最大幅: {'リサイズなし' if args.image_max_width <= 0 else str(args.image_max_width) + 'px'}")
    print(f"  PNG圧縮レベル: {args.png_compress_level}")
    print(f"  グレースケール化: {'はい' if args.grayscale else 'いいえ'}")
    print("--------------------------------------------------")

    # 4. 一時的な画像保存フォルダの準備とメイン処理の実行
    temp_image_dir_path_for_message = "" 
    try:
        with tempfile.TemporaryDirectory(prefix="screenshots_workflow_") as temp_dir_name:
            image_subfolder_path = Path(temp_dir_name)
            temp_image_dir_path_for_message = str(image_subfolder_path)
            print(f"一時的な画像保存フォルダを作成しました: {image_subfolder_path}")

            # 5. AppleScriptの実行
            if not run_applescript_process(APPLESCRIPT_PATH, str(image_subfolder_path)):
                sys.exit(1) # AppleScript失敗時はtempfileがクリーンアップ

            # 6. AppleScriptによって画像が実際に保存されたか確認
            image_files_exist = False
            valid_extensions_check = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
            if image_subfolder_path.is_dir():
                for item_path in image_subfolder_path.iterdir():
                    if item_path.is_file() and item_path.suffix.lower() in valid_extensions_check:
                        image_files_exist = True
                        break
            
            if not image_files_exist:
                print(f"エラー: AppleScriptは実行されましたが、一時フォルダ '{image_subfolder_path}' に処理可能な画像ファイルが見つかりません。")
                sys.exit(1) # 異常終了、tempfileがクリーンアップ

            # 7. PDF作成処理の実行 (画像処理オプションを渡す)
            print("スクリーンショット画像のPDF化を開始します...")
            if not create_pdf_from_images_internal(
                str(image_subfolder_path),
                str(output_pdf_path_obj),
                resize_max_width=args.image_max_width,
                png_compress_level=args.png_compress_level,
                convertToGrayscale=args.grayscale
            ):
                print("PDF作成に失敗しました。")
                sys.exit(1) # PDF作成失敗時もtempfileがクリーンアップ
        
        print(f"一時的な画像保存フォルダ '{temp_image_dir_path_for_message}' は処理後に自動的に削除されました。")

    except FileNotFoundError:
        print(f"エラー: 一時フォルダの作成またはアクセスに失敗しました。システムの一時フォルダ設定を確認してください。")
        sys.exit(1)
    except Exception as e: 
        print(f"一時フォルダの処理またはメイン処理の実行中に予期せぬエラーが発生しました: {e}")
        traceback.print_exc()
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
        sys.exit(130) 
    except SystemExit as e:
        # sys.exit() が呼ばれた場合、そのまま終了コードで終了
        # (main() 内でエラー時に sys.exit(1) を呼んでいるため、これをキャッチして再raiseする)
        raise e
    except Exception as e:
        print(f"スクリプト全体で予期せぬエラーが発生し、処理を終了します: {e}")
        traceback.print_exc()
        sys.exit(1)
