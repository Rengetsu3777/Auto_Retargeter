#import unreal
import os
import sys
import re
from importlib import reload
thisPath = os.path.dirname(os.path.abspath(__file__))
sys.path.append(thisPath + "/../../../Library/Pyside")
workspaceRootPath = thisPath + "/../../../../"

import logging 
import unreal

"""================================================="""
LOG_PATH = os.path.dirname(os.path.abspath(__file__)) + "/log/AutoRetargetting.log"


#配列の中は、優先探索パス（親になりそうなチェーン）、必須キーワードが順に入っている。
#辞書の構造は、
#    チェーン名: [このチェーンの先頭の親ボーンとして存在するボーン, [このリストの中の文字列に少なくとも1つは一致], [このリストの中の文字列に少なくとも1つは一致],...]
IK_MANNEQUIN_CHAIN_LIST = {
    "Root": ["Root", ["root","pelvis", "hip"]],
    "Spine": ["Root", ["spine", "chest"]],
    "Head": ["Spine", ["neck", "head"]],
    "HandGunIK": ["Root", ["handgunik"]],
    "FootRootIK": ["Root", ["footrootik"]],
    "HandRootIK": ["Root", ["handrootik"]],
}

#1つ上のリストと同じ構造で、このリストは左右に存在するボーンに対するチェーンマップ
IK_MANNEQUIN_CHAIN_MIRROR_LIST = {
    "Arm": ["Spine", ["arm"]],
    "Pinky": ["Arm", ["pinky"]],
    "Ring": ["Arm", ["ring"]],
    "Thumb": ["Arm", ["thumb"]],
    "Middle": ["Arm", ["middle"]],
    "Index": ["Arm", ["index"]],
    "Leg": ["Arm", ["leg", "thigh", "calf", "foot", "ball"]],
    "LowerArmTwist01": ["Root", ["lower"], ["arm"], ["twist"]],
    "LowerArmTwist02": ["Root", ["lower"], ["arm"], ["twist02"]],
    "UpperArmTwist01": ["Root", ["upper"], ["arm"], ["twist01"]],
    "UpperArmTwist02": ["Root", ["upper"], ["arm"], ["twist02"]],
    "ThighTwist01": ["Root", ["thigh"], ["twist01"]],
    "ThighTwist02": ["Root", ["thigh"], ["twist02"]],
    "CalfTwist01": ["Root", ["calf"], ["twist01"]],
    "CalfTwist02": ["Root", ["calf"], ["twist02"]],
    "IndexMetacarpal": ["Root", ["index"], ["metacarpal"]],
    "MiddleMetacarpal": ["Root", ["middle"], ["metacarpal"]],
    "PinkyMetacarpal": ["Root", ["pinky"], ["metacarpal"]],
    "RingMetacarpal": ["Root", ["ring"], ["metacarpal"]],
    "Clavicle": ["Root", ["clavicle", "shoulder"]],
    "FootIK": ["Root", ["foot"], ["ik"]],
    "HandIK": ["Root", ["hand"], ["ik"]],
}

#上の2つのリストの合体したリスト。
IK_MANNEQUIN_CHAIN_ALL_LIST = dict(**IK_MANNEQUIN_CHAIN_LIST, **IK_MANNEQUIN_CHAIN_MIRROR_LIST)


# コーディング上の左右のサインの定義：
# 「(記号) + r」-> 記号の後、直後が末尾で、rが付く。 ex.) _r -r
# 「r + (記号)」-> 先頭がrで、直後に記号が付く。  ex.) r_ r-
# 「（記号） + r + （記号）」 -> 途中にrがあり、その両端に同じ記号 ex.) -r- _r_
# 「（記号なし） + right」 -> 先頭に「right」が来る。 ex.) RightArm.lower()
# 格納する命名規則は、2つのリストで一致してなければならない。
SIGNS_FOR_RIGHT = ["_r", "-r", "r_", "r-", "_r_", "-r-", "right"]

SIGNS_FOR_LEFT = ["_l", "-l", "l_", "l-", "_l_", "-l-", "left"]


#MIRROR_CHAIN_LIST_REPRESENT = {"Arm", IK_MANNEQUIN_CHAIN_MIRROR_LIST["Arm"]} #左右のあるチェーンリストの代表として抽出して左右のサイン情報の解析などを行うための対象。

bone_hierarchy = []
chain_map = [] # Unreal Engine でのリターゲットでのチェーンマップに対応. 
left_sign = ""
right_sign = ""
sign_position = 0 # -rや_r, r-, r_など、「r」がどの位置に来るかのサイン。
#0: 無効, 1: 左, 2: 中, 3: 右
recrusive_function_queue = [] #想定はfind_bone関数で、幅優先探索で再帰呼び出しする時に、子ノードをappendして、前からポップして出たボーンノードで再帰呼び出しをする。


source_ik_rig = unreal.EditorAssetLibrary.load_asset('/Game/Characters/Mannequins/Rigs/IK_Mannequin.IK_Mannequin')
source_mesh = unreal.EditorAssetLibrary.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple') #source_mesh = UE5のManeqquin
if not source_ik_rig or not source_mesh:
    unreal.log("Warning: Fail to find source ik rig and mesh. Exit the process (AutoIKRetargetting)")
    logging.info("Warning: Fail to find source ik rig and mesh. Exit the process (AutoIKRetargetting)")


chain_tail_maps = {
    "Spine": 0,
    "LeftArm": 0,
    "LeftPinky": 0,
    "LeftRing": 0,
    "LeftThumb": 0,
    "LeftMiddle": 0,
    "LeftIndex": 0,
    "RightArm": 0,
    "RightPinky": 0,
    "RightRing": 0,
    "RightThumb": 0,
    "RightMiddle": 0,
    "RightIndex": 0,
    "RightLeg": 0,
    "LeftLeg": 0,
    "LeftLowerArmTwist01": 0,
    "LeftLowerArmTwist02": 0,
    "LeftUpperArmTwist01": 0,
    "LeftUpperArmTwist02": 0,
    "RightLowerArmTwist02": 0,
    "RightLowerArmTwist01": 0,
    "RightUpperArmTwist01": 0,
    "RightUpperArmTwist02": 0,
    "LeftThighTwist01": 0,
    "LeftThighTwist02": 0,
    "LeftCalfTwist01": 0,
    "LeftCalfTwist02": 0,
    "RightCalfTwist01": 0,
    "RightCalfTwist02": 0,
    "RightThighTwist01": 0,
    "RightThighTwist02": 0,
    "LeftIndexMetacarpal": 0,
    "LeftMiddleMetacarpal": 0,
    "LeftPinkyMetacarpal": 0,
    "LeftRingMetacarpal": 0,
    "RightPinkyMetacarpal": 0,
    "RightRingMetacarpal": 0,
    "RightMiddleMetacarpal": 0,
    "RightIndexMetacarpal": 0,
    "LeftClavicle": 0,
    "RightClavicle": 0,
    "LeftFootIK": 0,
    "RightFootIK": 0,
    "LeftHandIK": 0,
    "RightHandIK": 0,
    "HandGunIK": 0,
    "FootRootIK": 0,
    "HandRootIK": 0,
    "Root": 0,
    "Head": 0
}

#ボーン走査関数を再帰関数として呼び出す時、幅優先探索か、深さ優先探索か、再帰しないかを以下のフラグで選択。
NO_RECRUSIVE_SEARCH = 0
DEPTH_FIRST_SEARCH_FLAG = 1
WIDTH_FIRST_SEARCH_FLAG = 2

"""================================================="""


# 実行：py E:\Project\Unreal Engine\GameCreation5_3\MyScript\Tools\Python\AutoRetargetting\AutoRetargeter.py


def main():
    
    #ログ初期化
    initialize_log_settting()
    
    meshs = load_selected_assets_by_class("SkeletalMesh")
    
    for mesh in meshs:
        #ヒエラルキー作成＆ボーン階層取得のためのスケルタルメッシュモディファイア―作成
        initialize_bone_hierarchy()
        skeleton_modifier = initialize_skeleton_modifier(mesh)
        create_bone_hierarchy(skeleton_modifier, -1, "root", 0) #スケルトンの情報から、木構造のボーンリストを作成する。

        
        #スケルトン取得
        skeleton = mesh.skeleton

        #リターゲット用アセット生成
        ik_rig, ik_rig_controller = create_ik_asset(skeleton) #IK rigアセットの用意
        rtg, rtg_controller = create_retarget_asset(skeleton) #IK Rigとメッシュを使ってキャラ2体をリターゲットするアセット。

        map_chains()
                
        initialize_ik_asset(ik_rig, ik_rig_controller, mesh)
        setup_ik_asset(ik_rig_controller)
        setup_retarget_asset(rtg_controller, source_ik_rig, ik_rig, source_mesh, mesh)

        show_node()
    unreal.log("END!")
    logging.shutdown()



class Node():
    """ボーン1つの情報を格納するクラス。
    
    親と子のボーンの参照先を持っている。
    
    Attributes:
        parent: 親ボーンの名前
        bone_name: このノードのボーン名
        bone_id: ボーンの配列アドレス
        depth: 子のボーンのボーンツリー上での深さ
        children: 子ノードの名前のリスト
        children_id: 子ノードの配列アドレスのリスト
    """
    
    def __init__(self):
        """ボーンに対応するノードクラスを生成した時の初期化処理
        """
        
        self.parent:object = "" #Name
        self.bone_name:object = "" #Name
        self.bone_id:int = 0
        self.depth:int = 0
        self.children:list[object] = [] #Array(Name)
        self.children_id:list[int] = []

    def create_and_append_node(self, parent_bone_id:int, bone_name:object, depth:int):
        """ボーン情報を格納する関数

        Args:
            parent_bone_id (int): 親ボーンのボーン参照インデックス
            bone_name (name): ボーン名
            depth (int): ノードの
        """
        
        self.parent_bone_id = parent_bone_id
        self.bone_name = bone_name
        self.bone_id = len(bone_hierarchy) # ノードid = ボーン階層リストでのインデックス番号
        self.depth = depth

        bone_hierarchy.append(self)


def contain_left_right_sign_in_bone(bone_name:str, sign:str) -> bool:
    """ボーン名に命名規則として定義されている左右のサインが指定の箇所(sign_positionで定義)にあるかどうかを返す。

    Args:
        bone_name (str): ボーンの名前
        sign (str): 左右を示すサイン。sign_left, sign_rightが基本的に入る。（事前に値がセットしている状態で呼び出してください。）

    Returns:
        bool: ボーン中にサインが存在するか
    """
    
    logging.info("bone name: ", bone_name, ", sign_position: ", sign_position)
    
    if sign_position == 1:#サインが左端にある場合
        if bone_name.lower().startswith(sign):
            return True
        else:
            return False
        
    elif sign_position == 2:#サインが中にある場合
        if sign in bone_name.lower():
            return True
        else:
            return False
        
    elif sign_position == 3:#サインが右端にある場合
        if bone_name.lower().endswith(sign):
            return True
        else:
            return False
    else:
        #警告表示
        logging.warning("Function contain_left_right_sign_in_bone: invalid value 'sign_position'!")
        return False


def set_left_right_sign(sign_index:int):
    """グローバル変数の「left_sign」「right_sign」に値をセット、加えてsignの位置をsign_positionにセット。
    
    SIGNS_FOR_LEFTなどのリストから一致する左右を示す命名規則を探索して見つけたもののインデックス番号を入れるのを基本としている。

    Args:
        sign_index (int): SIGNS_FOR_LEFT, SIGNS_FOR_RIGHTのインデックス番号
    """
    
    global left_sign
    global right_sign
    global sign_position
    
    if sign_index == -1:
        logging.error("Cannot find left-right signs.")
        exit()
    else:
        if not left_sign:
            left_sign = SIGNS_FOR_LEFT[sign_index]
            char_l_position = left_sign.find('l')
            logging.info("left_sign: " + left_sign + ", char_l_position: " + str(char_l_position))
            if char_l_position == 0:#「l」の位置が左端なら
                sign_position = 1
            elif char_l_position == len(left_sign)-1:#「l」の位置が右端なら
                sign_position = 3
            else:#「l」の位置がそれ以外の位置では
                sign_position = 2
            #Tip: もし不具合あれば、右のところにも同様に作る。
        
        if not right_sign:
            right_sign = SIGNS_FOR_RIGHT[sign_index]


#不要
def get_current_script_path():
    """このスクリプトのあるシステムパスを返す。

    Returns:
        _type_: _description_
    """
    
    return os.path.dirname(os.path.abspath(__file__))


def initialize_log_settting():
    """ログの設定の初期化
    """
    
    logging.basicConfig(
        filename=LOG_PATH,
        filemode='w', 
        level=logging.INFO, 
        format='%(message)s', 
        force=True
    )


def initialize_bone_hierarchy():
    """ボーン情報を格納するリストの初期化
    """
    
    global bone_hierarchy
    bone_hierarchy = []


def get_chain_name_in_list_and_sign(chain_name:str) -> list[str, int]:
    """チェーン名から左右どちらのものであるかの判別と左右の接頭辞のないチェーン名を取得する。

    Args:
        chain_name (str): チェーンの名前

    Returns:
        list[str, int]: それぞれ、左右の接頭辞のないチェーン名と左右どちらのものであるかの番号
    """
    
    if 'Left' in chain_name:
        left_right_sign = -1
        chain_name_in_list = chain_name.replace("Left", "")
    elif 'Right' in chain_name:
        left_right_sign = 1
        chain_name_in_list = chain_name.replace("Right", "")
    else: #左右のサインがないチェーンの場合
        left_right_sign = 0
        chain_name_in_list = chain_name
    
    return chain_name_in_list, left_right_sign


def find_bone(chain_name:str, bone_node:Node, recrusive_search_method:int) -> int:
    """指定されたチェーン名に対応するボーンをボーンリストから探索して、ボーン名を返す。

    チェーンの条件に一致するボーンを探す。見つからなかったら、さらに下のボーンに潜る。それでも見つからなかったら、-1を返す。この関数で左右の識別子があるものとないものの両方について対応可能。chain_nameも左右付きの名前に対応している。

    Args:
        chain_name (str): 対応するボーンを探索する時のチェーン名
        bone_node (Node): ボーン1つの情報を格納したボーンのノードクラス。
        recrusive_search_method (int): 再帰関数として呼び出す時のボーン走査アルゴリズム

    Returns:
        int: 発見したボーンの、ボーンリスト内での参照インデックス。
    """

      
    #比較用に小文字に統一
    bone_name_lower = str(bone_node.bone_name).lower()
    

    chain_name_in_list, chain_left_right_sign = get_chain_name_in_list_and_sign(chain_name) #チェーンリストでの探索できるように名前を編集したchain_name_in_listと、左右のどちらのチェーンかを-1, 0, 1として判定したものを返す。。
    # ex.)
    # chain_name: LeftArm
    # chain_name_in_list: Arm (定数のリストに入ってる名前. Left, Rightを抜く)
    # chain_left_right_sign: -1 or 0 or 1
    

    for keywords in IK_MANNEQUIN_CHAIN_ALL_LIST[chain_name_in_list][1:]:#絶対条件のキーワードのループ(ここでは一旦、CHAIN_LISTの中にあるキーワードのみで、Left, Rightは検知しない。) 左右あり、なし混合リストを使用。
        
        bContain_keyword_single = False
        recrusive_flag = False
        #絶対に含むべきキーワードの中で1つは含まれているかのフラグ
        #例えばchain = "Root": ["Root", ["pelvis", "root", "hip"], [hoge]]なら、pelvis, root, hipのうち1つでもbone_node.bone_nameに含まれていれば、bContain_keyword_singleはTrue。加えてhogeの方でもボーン名に含まれていたら、発見したということでTrueを返す。
        
        for keyword_single in keywords:#チェーンに一致ボーン名なら、この中で1つは絶対に一致すべきキーワードがある。
            if keyword_single in bone_name_lower:
                
                bContain_keyword_single = True
                break
                
        if not bContain_keyword_single:#条件不一致の場合、子に遡る
            #再帰呼び出しフラグ=True
            
            recrusive_flag = True
            break
        
        
    #左右を示すキーワードのボーン名での存在確認 (再帰が確定してない場合のみ確認)
    if not recrusive_flag:
        
        if chain_left_right_sign == -1:
            #左の場合
            if contain_left_right_sign_in_bone(bone_name_lower, left_sign):
                return bone_node.bone_id
            else:
                #再帰で探索.
                recrusive_flag = True
            
        elif chain_left_right_sign == 0:
            #左右なしの場合
            return bone_node.bone_id
        
        else:
            #右の場合
            if contain_left_right_sign_in_bone(bone_name_lower, right_sign):
                return bone_node.bone_id
            else:
                #再帰で探索.
                recrusive_flag = True
                

    #ここまで来るのは、再帰呼び出しをする時 =========
    if recrusive_flag:
        
        #再帰しない場合
        if recrusive_search_method == NO_RECRUSIVE_SEARCH:
            return -1
        
        #深さ優先探索の場合
        elif recrusive_search_method == DEPTH_FIRST_SEARCH_FLAG:
            for child_id in bone_node.children_id:
                bone_id = find_bone(chain_name, bone_hierarchy[child_id], DEPTH_FIRST_SEARCH_FLAG) 
                if bone_id != -1:#-1でなければ（＝boneを見つけた場合は）、その枝で探索終了し、idを返す。
                    return bone_id
                
            # <-ここにくるのは、全ての子ボーンでfind_boneして-1の場合
            
        #幅優先探索の場合
        elif recrusive_search_method == WIDTH_FIRST_SEARCH_FLAG:
            for child_id in bone_node.children_id:
                recrusive_function_queue.append(child_id)
            
            if len(recrusive_function_queue) == 0:#キューに貯めた子ノードリストが無くなるまで探索してもなかった時、-1を返す。
                return -1
            
            bone_id = find_bone(chain_name, bone_hierarchy[recrusive_function_queue.pop(0)], WIDTH_FIRST_SEARCH_FLAG)
            if bone_id != -1:#発見した時
                return bone_id
        
        
        #子ノードがない末端の場合は、見つからなかったフラグid=-1を返す
        return -1
    
    return bone_node.bone_id #自分がその該当ノードなので、自分のノードidを返す。


def get_bone_id_from_name(target_bone_name:str) -> int:
    """Node型のボーンノードで名前と同じものを見つけて、idを返す。
    
    ボーンノードのidは、bone_hierarchy[bone_id]によってボーンノードを取得できる、いわばポインターの役割を持ち、ノード自体を返さないことにより、最小限の情報量を返すことにしている。

    Args:
        target_bone_name (str): 見つけたいボーンidのボーンの名前

    Returns:
        int: ボーンのid
    """
    
    for bone_node in bone_hierarchy:
        if str(bone_node.bone_name) == target_bone_name:
            return bone_node.bone_id


def find_chain_tail(chain_name:str, bone_id:int) -> int:
    """チェーンマッピングでの末尾のボーンを取得する。
    
    チェーンのボーンに一致するボーンを受け取り、その対象ボーンの末端を探って、末端のボーンidを返す関数

    Args:
        chain_name (str): チェーンの名前
        bone_id (int): ボーンの参照インデックス

    Returns:
        int: 末尾として発見したボーンの参照インデックス
    """

    for child_id in bone_hierarchy[bone_id].children_id:#子ノードは複数ありえるためループ
        child_bone_id = find_bone(chain_name, bone_hierarchy[child_id], WIDTH_FIRST_SEARCH_FLAG)
        
        if child_bone_id != -1:#発見時
            return find_chain_tail(chain_name, child_bone_id)#最終的に発見した末端のidが返っていく。
        
    #何も見つからなかった = 入力ボーン(bone_idのボーン)が末端でもある場合
    return bone_id


def get_left_right_sign_index(bone_node:Node) -> int:
    """左右を示すサインの規則を解読
    
    左右それぞれ1回ずつ実行する想定で実装
    
    Args:
        bone_node(Node): 検証対象のボーンのnode。
    
    Returns:
        sign: 今回のボーン階層構造で使われる左右を示す文字列。"-1"は存在しなかった場合に返す。
    """
    #ToDo: 動作確認
    
    bone_name_lower = str(bone_node.bone_name).lower()
    
    #今回のノードでの検証
    #左のサインの辞書から探索
    for sign_index, sign in enumerate(SIGNS_FOR_LEFT):
        if sign in bone_name_lower:
            return sign_index #見つかったら、そのサインのインデックスを返す。
    
    #左でなければ、右である可能性がある。
    for sign_index, sign in enumerate(SIGNS_FOR_RIGHT):
        if sign in bone_name_lower:
            return sign_index
    
     
    #ノードの末端まで行って、サインが見つからない時には -1 を返す。
    if not bone_node.children_id:
        return -1
    
    #子ノードに対して再帰的に調べる
    for child_id in bone_node.children_id:
        sign_index =  get_left_right_sign_index(bone_hierarchy[child_id])
        
        #子ノードで対応してるボーンから左右のサインを取り出せたら、それを返す。
        if sign_index != -1:
            return sign_index

    #子ノードまで遡ってなかったら、最終結果として-1を返す。
    return -1
        
    
def get_chain_bone_head_to_tail(chain_name:str, chain_value:list[str]) -> list[int, int]:
    """チェーンマッピングに対応するボーンを先頭から末尾まで取得する関数。

    Args:
        chain_name (_type_): IK_MANNEQUIN_CHAIN_LISTのKeyの部分を想定。Left, Right等もついている。
        source_chain_list (_type_): IK_MANNEQUIN_CHAIN_LISTにあたる部分を想定。
        
        #以下不要？
        left_right_sign（string）:Leftか"Rightが入る。mirrored_flagがFalseなら、処理で使われない。それ以外は、エラーとして処理。
        mirrored_flag (bool, optional): このチェーンのボーンがミラーとして存在しているかのフラグ.

    Returns:
        list[int, int]: 発見した先頭と末尾のボーンの参照インデックス。
    """
    
    if 'Left' in chain_name or 'Right' in chain_name:#左や右の概念が存在するチェーンの場合はこのリストが渡される
        #以下のネストでの方針：親のチェーンを既存チェーン済みリストから取得 -> 
        # （成功したら）tailのボーンid取得 ->
        # （失敗したら）Left, Rightが付かないチェーンが親なので、Left, Right付いてないparent_chain_nameで探索。
        
        parent_chain_name = chain_value[0] #優先探索ボーンパスを取得
                  
        #左か右かの特定。親のチェーン名にLeft, Rightを付与する。
        if 'Left' in chain_name:
            left_right_sign = 'Left'
        else:
            left_right_sign = 'Right'
            
        
        for chained_data_parent in chain_map:#既にchainとして登録されているデータから、親チェーンデータを参照。
            
#               if chained_data_parent[0] == parent_chain_name_left_right:
            parent_chain_name_left_right = left_right_sign + parent_chain_name
            
            #if chained_data_parent[0] == parent_chain_name:##親のチェーンがSpineなど、左右が付かない場合はこちら
            
            if parent_chain_name_left_right:
                parent_chain_tail_bone_id = get_bone_id_from_name(chained_data_parent[2]) #chained_data[2]は、chainのtailにあたるボーンの名前(str型)。ボーン名からidを取得。
                break
            #logging.error("左右のサインの入力に不正があります！")
        
    else:
        #左や右の概念がないチェーンの場合
        #チェーンにあたるボーンを探索(優先パスから潜って探索)
        parent_chain_name = IK_MANNEQUIN_CHAIN_LIST[chain_name][0] #優先探索ボーンパスを取得, Todo: IK_MANNEQUIN_CHAIN_LIST -> source_chain_list で修正
        parent_chain_tail_bone_id = chain_tail_maps[parent_chain_name]
        

    for child_id in bone_hierarchy[parent_chain_tail_bone_id].children_id:
        target_bone_id = find_bone(chain_name, bone_hierarchy[child_id], WIDTH_FIRST_SEARCH_FLAG)
        if target_bone_id != -1:#チェーンの頭のボーン見つかった時
            head_bone_id = target_bone_id
            tail_bone_id = find_chain_tail(chain_name, bone_hierarchy[target_bone_id].bone_id) #チェーンのしっぽのボーンを見つける。
            return head_bone_id, tail_bone_id #頭としっぽのボーンidを返す。

    return -1, -1#チェーンにあたるボーンが存在しない時

    
def map_chains():
    """チェーンの名前に対応するボーンを取得し、チェーンマッピングデータに格納する。
    """
    
    #左右のないボーンに対するチェーンマッピング
    for chain_name, chain_value in IK_MANNEQUIN_CHAIN_LIST.items():
        head_bone_id, tail_bone_id = get_chain_bone_head_to_tail(chain_name, chain_value)

        explain = "chain name: " + chain_name + ", head bone id: " + str(head_bone_id) + ", tail bone id: " + str(tail_bone_id)
        logging.info(explain)
        
        if head_bone_id != -1 and tail_bone_id != -1:
            chain_data = [str(chain_name), str(bone_hierarchy[head_bone_id].bone_name), str(bone_hierarchy[tail_bone_id].bone_name), ""]
            chain_map.append(chain_data)

    #以降は左右のあるボーンのチェーンマッピング

    #Left, Rightを示すサインを検出する処理。
    #sign_indexは、検出された命名が格納されているSIGNS_FOR_RIGHT, SIGNS_FOR_LEFTでのインデックス番号
    sign_index = get_left_right_sign_index(bone_hierarchy[0]) #ルートボーンにしたのは、find_boneの前に実施したいため。
    set_left_right_sign(sign_index)
    
    
    for chain_name, chain_value in IK_MANNEQUIN_CHAIN_MIRROR_LIST.items():
        #チェーンの1つのセットからボーン名のキーワードを抽出し、該当ボーンを探す。
        left_chain_name = "Left" + chain_name
        right_chain_name = "Right" + chain_name
        left_head_bone_id, left_tail_bone_id = get_chain_bone_head_to_tail(left_chain_name, chain_value)
        right_head_bone_id, right_tail_bone_id = get_chain_bone_head_to_tail(right_chain_name, chain_value)
        
        #左のパートの処理
        explain_left = "chain name: " + left_chain_name + ", head bone id: " + str(left_head_bone_id) + ", tail bone id: " + str(left_tail_bone_id)
        logging.info(explain_left)
        
        if left_head_bone_id != -1 and left_tail_bone_id != -1:
            chain_data = [str(left_chain_name), str(bone_hierarchy[left_head_bone_id].bone_name), str(bone_hierarchy[left_tail_bone_id].bone_name), ""]
            chain_map.append(chain_data)
            
        
        #右のパートの処理
        explain_right = "chain name: " + right_chain_name + ", head bone id: " + str(right_head_bone_id) + ", tail bone id: " + str(right_tail_bone_id)
        logging.info(explain_right)
        
        if right_head_bone_id != -1 and right_tail_bone_id != -1:
            chain_data = [str(right_chain_name), str(bone_hierarchy[right_head_bone_id].bone_name), str(bone_hierarchy[right_tail_bone_id].bone_name), ""]
            chain_map.append(chain_data)
        
    

#多分要らない
def convert_ue_path_to_sys_pth(ue_path):
    """UEでのコンテンツパスからシステムパスに変換する処理（未実装）

    Args:
        ue_path (string): UE内でのアセットパス
    """
    
    logging.info(unreal.Paths.get_project_file_path())
    logging.info(unreal.Paths.game_source_dir())


def load_selected_assets_by_class(class_name:str):
    """クラス名から選択しているアセットを絞ってリストとして返す関数。

    Args:
        class_name (str): 選択したいアセットのクラス名

    Returns:
        list[object]: 選択したアセットのリスト
    """
    
    target_assets = []

    for asset in unreal.EditorUtilityLibrary.get_selected_assets():
        if asset.get_class().get_name() == class_name:
            target_assets.append(asset)
            
    return target_assets


def create_retarget_asset(asset:object):
    """リターゲット用のIK Retargeter アセット

    Args:
        asset (object): スケルトンのアセット

    Returns:
        object: IK Retargeter アセット
        object: IK Retargeter アセットのコントローラー
    """

    #アセット情報取得
    rtg_name = "RTG_" + asset.get_name()
    asset_path = asset.get_path_name()

    #IK Retargeter を生成
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    rtg = asset_tools.create_asset(asset_name=rtg_name, package_path=asset_path, asset_class=unreal.IKRetargeter, factory=unreal.IKRetargetFactory())

    #コントローラーを生成(create_ik_assetと同様)
    rtg_controller = unreal.IKRetargeterController.get_controller(rtg)

    return rtg, rtg_controller


def create_ik_asset(asset:object):
    """IK Rigアセットを生成

    Args:
        asset (object): skeleton

    Returns:
        object: ik rig アセット
        object: ik rig アセットのコントローラー
    """
        
    #アセット情報取得
    ik_name = "IK_" + asset.get_name()
    asset_path = asset.get_path_name()

    #IKリグ生成
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ik_rig = asset_tools.create_asset(asset_name=ik_name, package_path=asset_path, asset_class=unreal.IKRigDefinition, factory=unreal.IKRigDefinitionFactory())

    #IKリグを操作するオブジェクト生成
    ik_rig_controller = unreal.IKRigController.get_controller(ik_rig)

    return ik_rig, ik_rig_controller
    

def initialize_ik_asset(ik_rig_controller: object, mesh: object):
    """IK Rig アセットの初期化処理を行う

    Args:
        ik_rig_controller (object): IK Rig のコントローラー
        mesh (object): IK Rigアセットのメッシュ
    """
    
    ik_rig_controller.set_skeletal_mesh(mesh)


def initialize_skeleton_modifier(mesh:object) -> object:
    """メッシュからスケルトンを取得する処理

    Args:
        mesh (object): ターゲットのスケルタルメッシュ

    Returns:
        object: メッシュに対応するスケルタルメッシュ
    """
    
    if mesh.get_class().get_name() == "SkeletalMesh":
        skeleton_modifier = unreal.SkeletonModifier()
        skeleton_modifier.set_skeletal_mesh(mesh)
        return skeleton_modifier
    

def setup_ik_asset(ik_rig_controller:object):
    """IK Rig アセットにチェーンを登録する。

    Args:
        ik_rig_controller(object): リターゲットのターゲットにあたるIK Rig
    """
    
    for chain in chain_map:
        ik_rig_controller.add_retarget_chain(chain[0], chain[1], chain[2], chain[3])


def setup_retarget_asset(rtg_controller:object, source_ik_rig:object, target_ik_rig:object, source_mesh:object, target_mesh:object):
    """IK RetargeterにIK Rigとメッシュの情報をセットする関数。

    Args:
        rtg_controller (object): IK Retargeterのコントローラー
        source_ik_rig (object): モーションの元のIK rig
        target_ik_rig (object): モーション移す先のIK Rig
        source_mesh (object): リターゲットのソースにあたるメッシュ
        target_mesh (object): リターゲットしたいメッシュ
    
    """
    
    #RTGアセットにIKリグのセットアップを行う
    rtg_controller.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_ik_rig)
    rtg_controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_ik_rig)

    #プレビュー用のメッシュをセット
    rtg_controller.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, source_mesh)
    rtg_controller.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)


def create_bone_hierarchy(skeleton_modifier:object, parent_bone_id:int, bone_name:str, depth:int) -> int:
    """キャラモデルのボーン情報を読み込み、ボーン構造を木構造で内部に構築。

    Args:
        skeleton_modifier (object): メッシュから取得した操作用のスケルトンアセット
        parent_bone_id (int): 親ボーンのボーンリスト内での参照インデックス
        bone_name (str): 今回木構造に生成するボーンの名前
        depth (int): 今回生成しているボーンの木構造での深さ

    Returns:
        int: 今回生成したボーンのボーンリスト内でのデータを格納しているインデックス。
    """
    
    #ノードのidを返す
    #ボーン用のノードを作成
    node = Node()
    node.create_and_append_node(parent_bone_id, bone_name, depth)

    #子ボーンの取得。
    node.children = skeleton_modifier.get_children_names(
        bone_name,
        recursive=False
    )

    #for child_name in bone_hierarchy[parent_bone_id].children:
    for child_name in node.children:

        child_bone_id = create_bone_hierarchy(skeleton_modifier, node.bone_id, child_name, depth+1)
        node.children_id.append(child_bone_id)#子ノードのリストでの位置を格納

    return node.bone_id #ノードのリストでの位置を返す


def show_node():
    """読み込んだボーンの構造をログでツリー状に記録する処理
    """
    
    for node in bone_hierarchy:
        logging.info(str(node.bone_name) + ": " + str(node.bone_id))


def show_bone_tree():
    """ボーンヒエラルキーをテキストに書き出し
    """
    
    for bone_node in bone_hierarchy:
        space = ""
        for _ in range(bone_node.depth):
            space += "  "
            logging.info(str(bone_node.bone_name))


if __name__ == '__main__':
    main()
