# kinpdfle
kindleの電子書籍をPDFにするスクリプト

## 必須
- [リンク](https://engineer-ganbaru.com/kindle-auto-screenshot/) の「スクリプトエディタの許可設定」を実施する
- Kindleの保存したい電子書籍の最初のページ画面を開いておく
- `requires-python = ">=3.13"`
- スクショしている間はじっとする

## 推奨
- スクリーンショットを撮影しても左下にプレビューが表示されないようにする
    1. `Shift + Command + 5` でスクリーンショットのコントロールバーを開く
    2. 「オプション」から「フローティングサムネールを表示」のチェックを外す


## 例
```python
uv run main.py --output-pdf-path test/example.pdf
```

## 参考
- https://qiita.com/yu_uk/items/5c430a1c3aa61d48d115
