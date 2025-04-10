# Auto Retargeter

## 制作者
天羽綺良々 <br>

## ツールについて
このツールは、Unreal Engine5におけるIKリターゲットのセットアップをツールが自動で実行するツールです。チェーンの作成、リターゲッターのセットアップまで対応しています。（ルートの位置は手動で補正が必要です。）<br>

## 動作環境
- Unreal Engine 5.3.2
- Windows 11 Home

## 使い方
Unreal Engineを起動し、リターゲットを行いたいモデルのスケルたるメッシュを選択しながら、コマンドラインで、<br><br>

~~~ 
py （ここにこのツールのフォルダーパス）/AutoRetargeter.py
~~~

を入力して実行することで、自動でリターゲットしてくれます。（実行処理は数秒かかります。）
例えば私の環境の場合は、
~~~
py E:/Project/Programming/Python/AutoRetargeter/AutoRetargeter.py
~~~
と入力することで実行できます。

## 仕様
- 左右を示すボーン命名規則が複数種類ある場合は、正しく動作しません。<br>
    ex.）"Arm.L" や "RightArm" などが同一のモデルに混在している場合

