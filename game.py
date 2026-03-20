"""
================================================================================
Shadow Abyss - 暗黑类ARPG游戏
================================================================================
核心特性：
- 地牢随机生成（房间 + 走廊）
- 流场寻路系统（360度任意方向）
- 方向感系统（敌人每隔1格重新寻路）
- 碰撞反弹（沿法线方向）
- 中心点碰撞检测

操作说明：
- WASD / 方向键：移动
- 鼠标左键：选择目标
- 1-4：使用技能（火球、冰霜、冲锋、治疗）
- ESC：暂停
- R：游戏结束后重新开始
"""

# ===== 导入模块 =====
import pygame       # Pygame游戏框架
import random       # 随机数生成
import math         # 数学运算（距离计算、三角函数等）
from collections import deque  # 双端队列（用于BFS寻路）
import os           # 文件路径处理

# ===== Pygame初始化 =====
pygame.init()

# ================================================================================
# 全局常量定义
# ================================================================================

# 屏幕尺寸
SCREEN_W, SCREEN_H = 1280, 720   # 宽度1280，高度720像素

# 瓦片尺寸（每个格子32x32像素）
TILE = 32

# ===== 精灵图加载 =====
RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res')

def load_sprite_sheet(path, rows, cols):
    """加载并切割精灵图"""
    sheet = pygame.image.load(path)
    frame_w, frame_h = sheet.get_width() // cols, sheet.get_height() // rows
    frames = []
    for row in range(rows):
        row_frames = []
        for col in range(cols):
            frame = sheet.subsurface((col * frame_w, row * frame_h, frame_w, frame_h))
            row_frames.append(pygame.transform.scale(frame, (TILE, TILE)))
        frames.append(row_frames)
    return frames

# 玩家：4行3列，敌人：4行4列
PLAYER_FRAMES = load_sprite_sheet(os.path.join(RES_DIR, 'player.png'), 4, 3)
ENEMY_FRAMES = load_sprite_sheet(os.path.join(RES_DIR, 'enemy.png'), 4, 4)

# 技能图标加载（4个技能）
SKILL_ICONS = []
for i in range(1, 5):
    icon_path = os.path.join(RES_DIR, f'skill{i}.png')
    if os.path.exists(icon_path):
        icon = pygame.image.load(icon_path)
        SKILL_ICONS.append(pygame.transform.scale(icon, (40, 40)))
    else:
        SKILL_ICONS.append(None)

# 动画计时
PLAYER_ANIM_SPEED = 0.15  # 每帧持续时间（秒）

# 游戏帧率（每秒30帧）
FPS = 30

# ================================================================================
# 颜色定义 (RGB格式)
# ================================================================================
C = {
    'bg': (15, 15, 20),          # 背景色（深灰偏黑）
    'floor': (50, 50, 60),        # 地板色1（棋盘格）
    'floor2': (45, 45, 55),       # 地板色2（棋盘格交替）
    'wall': (25, 25, 35),         # 墙壁色（深色）
    'wall_top': (35, 35, 50),     # 墙壁顶部（稍亮，用于立体感）
    'player': (52, 152, 219),     # 玩家颜色（蓝色）
    'enemy': (231, 76, 60),       # 敌人颜色（红色）
    'gold': (241, 196, 15),       # 金币颜色（金黄色）
    'hp': (231, 76, 60),          # 生命值颜色（红色）
    'mp': (52, 152, 219),         # 法力值颜色（蓝色）
    'xp': (241, 196, 15),          # 经验值颜色（金黄）
    'exit': (68, 170, 136),       # 出口颜色（绿色）
    'white': (255, 255, 255),     # 白色
    'gray': (150, 150, 150),      # 灰色
    'flow': (100, 200, 100),      # 流场方向颜色（绿色）
}

# ================================================================================
# 游戏配置参数
# ================================================================================
CFG = {
    'dungeon_w': 50,              # 地牢宽度（50格）
    'dungeon_h': 40,              # 地牢高度（40格）
    'rooms_min': 10,               # 最少房间数
    'rooms_max': 15,               # 最多房间数
    'room_min': 6,                 # 房间最小尺寸
    'room_max': 12,                # 房间最大尺寸
    'player_speed': 4.0,           # 玩家移动速度（格/秒）
    'enemy_speed': 3.0,            # 敌人移动速度（格/秒）
    'aggro_range': 10,             # 敌人感知玩家距离（格）
}


# ================================================================================
# 地牢类 - 地图生成与管理
# ================================================================================
class Dungeon:
    """
    地牢地图生成器
    
    工作原理：
    1. 在地图上随机生成多个矩形房间（不重叠）
    2. 用走廊连接相邻的房间
    3. 0表示地板（可通行），1表示墙壁（不可通行）
    
    坐标系统：
    - 使用整数坐标 (x, y)，原点在左上角
    - x向右增加，y向下增加
    """
    
    def __init__(self):
        """初始化地牢尺寸，创建空地图"""
        self.w = CFG['dungeon_w']      # 地牢宽度（格数）
        self.h = CFG['dungeon_h']      # 地牢高度（格数）
        self.tiles = [[1] * self.w for _ in range(self.h)]  # 1=墙壁，0=地板
        self.rooms = []                  # 存储房间信息列表
        self.generate()                  # 开始生成
    
    def generate(self):
        """
        生成地牢地图的主要方法
        
        步骤：
        1. 随机生成若干个房间（10-15个）
        2. 检查房间是否重叠
        3. 将房间区域设为地板（tiles=0）
        4. 用走廊连接相邻房间
        5. 设置出生点和出口
        """
        # ----- 步骤1：生成房间 -----
        for _ in range(random.randint(CFG['rooms_min'], CFG['rooms_max'])):
            # 随机房间尺寸
            rw = random.randint(CFG['room_min'], CFG['room_max'])  # 房间宽度
            rh = random.randint(CFG['room_min'], CFG['room_max'])  # 房间高度
            
            # 随机房间位置（避开边界）
            rx = random.randint(1, self.w - rw - 1)
            ry = random.randint(1, self.h - rh - 1)
            
            # ----- 步骤2：检查重叠 -----
            # 与已有房间进行比较，看是否重叠
            overlap = any(
                rx < r['x'] + r['w'] + 1 and rx + rw + 1 > r['x'] and
                ry < r['y'] + r['h'] + 1 and ry + rh + 1 > r['y']
                for r in self.rooms
            )
            
            # ----- 步骤3：设置地板 -----
            if not overlap:
                # 将房间区域设为地板（0表示可通行）
                for y in range(ry, ry + rh):
                    for x in range(rx, rx + rw):
                        self.tiles[y][x] = 0
                # 保存房间信息
                self.rooms.append({'x': rx, 'y': ry, 'w': rw, 'h': rh})
        
        # ----- 步骤4：连接房间 -----
        # 依次连接相邻的两个房间
        for i in range(1, len(self.rooms)):
            self._connect(self.rooms[i-1], self.rooms[i])
        
        # ----- 步骤5：设置出生点和出口 -----
        # 第一个房间中心=出生点，最后一个房间中心=出口
        self.spawn = self._center(self.rooms[0]) if self.rooms else (2, 2)
        self.exit = self._center(self.rooms[-1]) if len(self.rooms) > 1 else (self.w - 3, self.h - 3)
    
    def _center(self, r):
        """
        计算房间中心坐标
        
        参数：r - 房间字典 {'x', 'y', 'w', 'h'}
        返回：(center_x, center_y) 中心点坐标
        """
        return (r['x'] + r['w'] // 2, r['y'] + r['h'] // 2)
    
    def _connect(self, a, b):
        """
        连接两个房间（创建L形走廊）
        
        原理：
        - 从房间A中心水平移动到房间B同一列
        - 然后垂直移动到房间B中心
        - 将路径上的格子设为地板（0）
        
        参数：
        a, b - 两个房间的字典
        """
        ax, ay = self._center(a)  # 房间A中心
        bx, by = self._center(b)  # 房间B中心
        
        # ----- 水平走廊 -----
        # 从ax到bx，固定y=ay
        for x in range(min(ax, bx), max(ax, bx) + 1):
            if 0 <= ay < self.h:  # 边界检查
                self.tiles[ay][x] = 0
        
        # ----- 垂直走廊 -----
        # 从ay到by，固定x=bx
        for y in range(min(ay, by), max(ay, by) + 1):
            if 0 <= bx < self.w:  # 边界检查
                self.tiles[y][bx] = 0
    
    def walkable(self, x, y):
        """
        检查坐标是否可行走（碰撞检测用）
        
        参数：
        x, y - 浮点数坐标
        
        返回：
        True - 可以行走（地板）
        False - 不能行走（墙壁或边界外）
        
        原理：
        - 将浮点坐标转为整数格子坐标
        - 检查该格子是否为地板（tiles值为0）
        """
        tx, ty = int(math.floor(x)), int(math.floor(y))  # 向下取整得到格子坐标
        if 0 <= tx < self.w and 0 <= ty < self.h:       # 边界检查
            return self.tiles[ty][tx] == 0              # 0=地板，1=墙壁
        return False


# ================================================================================
# 流场类 - 360度任意方向寻路系统
# ================================================================================
class FlowField:
    """
    流场寻路系统（360度任意方向版）
    
    核心思想：
    - 使用BFS（广度优先搜索）计算每个格子到目标的距离
    - 每个格子存储一个指向最近格子的单位向量
    - 可以是任意角度的方向，不限于4个或8个方向
    
    优势：
    - 比A*更适合动态目标（玩家移动时只更新目标点）
    - 可以生成任意角度的平滑路径
    
    缺点：
    - 不保证最短路径
    - 内存占用较大
    """
    
    def __init__(self, dungeon):
        """初始化流场"""
        self.dungeon = dungeon                     # 地牢引用
        
        # 8方向用于BFS距离计算（上、右上、右、右下、下、左下、左、左上）
        self.DIRS8 = [(0, -1), (1, -1), (1, 0), (1, 1), 
                      (0, 1), (-1, 1), (-1, 0), (-1, -1)]
        
        self.field = [[None] * dungeon.w for _ in range(dungeon.h)]  # 流场方向
        self.dist = [[float('inf')] * dungeon.w for _ in range(dungeon.h)]  # 距离
        self.target_x = 0
        self.target_y = 0
    
    def update(self, target_x, target_y):
        """
        从目标点计算360度流场
        
        步骤：
        1. BFS计算所有格子到目标的距离
        2. 对每个格子，选择距离目标最近的可通行邻居
        3. 将方向归一化为单位向量
        
        参数：
        target_x, target_y - 目标点坐标（通常是玩家位置）
        """
        self.target_x = target_x
        self.target_y = target_y
        tx, ty = int(target_x), int(target_y)
        
        # 重置距离和流场
        self.dist = [[float('inf')] * self.dungeon.w for _ in range(self.dungeon.h)]
        self.field = [[None] * self.dungeon.w for _ in range(self.dungeon.h)]
        
        # ----- BFS计算距离 -----
        queue = deque()
        
        # 只从可行的目标点开始
        if 0 <= tx < self.dungeon.w and 0 <= ty < self.dungeon.h:
            if self.dungeon.tiles[ty][tx] == 0:  # 目标是地板
                self.dist[ty][tx] = 0
                queue.append((tx, ty))
        
        # BFS主循环
        while queue:
            x, y = queue.popleft()
            d = self.dist[y][x]
            
            # 检查8个邻居
            for dx, dy in self.DIRS8:
                nx, ny = x + dx, y + dy
                # 边界检查 + 可通行检查
                if 0 <= nx < self.dungeon.w and 0 <= ny < self.dungeon.h:
                    if self.dungeon.tiles[ny][nx] == 0:  # 是地板
                        if d + 1 < self.dist[ny][nx]:     # 找到更短路径
                            self.dist[ny][nx] = d + 1
                            queue.append((nx, ny))
        
        # ----- 计算流向 -----
        # 对每个格子，选择指向更近格子的方向
        for y in range(self.dungeon.h):
            for x in range(self.dungeon.w):
                # 只处理可通行的格子
                if self.dungeon.tiles[y][x] == 0 and self.dist[y][x] < float('inf'):
                    best_dir = None
                    best_dist = self.dist[y][x]
                    
                    # 检查8个方向
                    for dx, dy in self.DIRS8:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.dungeon.w and 0 <= ny < self.dungeon.h:
                            if self.dungeon.tiles[ny][nx] == 0:
                                if self.dist[ny][nx] < best_dist:
                                    best_dist = self.dist[ny][nx]
                                    best_dir = (dx, dy)
                    
                    # 归一化为单位向量（任意角度）
                    if best_dir and best_dist < self.dist[y][x]:
                        length = math.sqrt(best_dir[0]**2 + best_dir[1]**2)
                        self.field[y][x] = (best_dir[0]/length, best_dir[1]/length)
    
    def get(self, x, y):
        """
        获取流场方向
        
        参数：x, y - 查询位置的坐标
        
        返回：
        (dx, dy) - 归一化的单位向量，指向距离目标更近的格子
        None - 如果该格子不可通行或无法到达
        """
        tx, ty = int(x), int(y)
        if 0 <= tx < self.dungeon.w and 0 <= ty < self.dungeon.h:
            return self.field[ty][tx]
        return None


# ================================================================================
# 玩家类 - 角色控制
# ================================================================================
class Player:
    """
    玩家角色类
    
    属性说明：
    - self.x, self.y: 浮点数坐标，0.5表示格子中心
    - self.radius: 碰撞半径（0.25格 = 8像素）
    - self.speed: 移动速度（格/秒）
    - self.hp/max_hp: 当前/最大生命值
    - self.mp/max_mp: 当前/最大法力值
    - self.xp/xp_to: 当前经验/升级所需经验
    - self.dmg: 基础伤害
    - self.atk_cd: 攻击冷却计时器
    - self.target: 当前选中的敌人
    - self.skills: 技能列表（4个主动技能）
    """
    
    def __init__(self, x, y):
        """初始化玩家属性"""
        self.x, self.y = x, y                    # 位置（浮点数坐标）
        self.radius = 0.25                       # 碰撞半径
        self.speed = CFG['player_speed']         # 移动速度
        
        # 等级系统
        self.level = 1                           # 当前等级
        self.xp = 0                              # 当前经验
        self.xp_to = 100                         # 升级所需经验
        
        # 属性
        self.hp, self.max_hp = 100, 100          # 生命值
        self.mp, self.max_mp = 50, 50            # 法力值
        self.dmg = 10                            # 基础伤害
        self.gold = 0                            # 金币
        
        self.atk_cd = 0                         # 攻击冷却
        self.target = None                       # 当前选中的敌人
        
        # 动画系统
        self.anim_dir = 0    # 当前方向索引（0=下, 1=左, 2=右, 3=上）
        self.anim_frame = 0  # 当前动画帧
        self.anim_timer = 0  # 动画计时器
        
        # 技能列表
        # 每个技能包含：
        # - name: 技能名称
        # - cost: 法力消耗
        # - cd: 冷却时间（秒）
        # - timer: 当前冷却计时
        # - dmg/heal/radius/dist: 技能效果参数
        self.skills = [
            {'name': '火球', 'cost': 15, 'dmg': 30, 'cd': 2, 'timer': 0},
            {'name': '冰霜', 'cost': 20, 'dmg': 20, 'cd': 4, 'timer': 0, 'radius': 4},
            {'name': '冲锋', 'cost': 10, 'cd': 3, 'timer': 0, 'dist': 6},
            {'name': '治疗', 'cost': 25, 'heal': 50, 'cd': 5, 'timer': 0},
        ]
    
    def update(self, dt, dungeon, keys):
        """
        更新玩家状态（每帧调用）
        
        参数：
        dt: 时间增量（秒）
        dungeon: 地牢对象（用于碰撞检测）
        keys: 键盘按键状态
        
        处理：
        1. 自然回复（HP/MP）
        2. 键盘移动
        3. 冷却计时
        4. 自动攻击
        """
        # ----- 1. 自然回复 -----
        # HP每秒回复0.5，MP每秒回复0.3
        self.hp = min(self.max_hp, self.hp + 0.5 * dt)
        self.mp = min(self.max_mp, self.mp + 0.3 * dt)
        
        # ----- 2. 键盘移动 -----
        # 计算移动方向：D右-A左，W上-S下
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        
        if dx or dy:
            # 归一化方向向量（保证斜向移动速度一致）
            length = math.sqrt(dx*dx + dy*dy)
            dx, dy = dx/length, dy/length
            
            # 计算新位置：位置 += 方向 * 速度 * 时间
            new_x = self.x + dx * self.speed * dt
            new_y = self.y + dy * self.speed * dt
            
            # 分别检测X和Y轴碰撞（允许斜着走）
            if self._can_move(new_x, self.y, dungeon):
                self.x = new_x
            if self._can_move(self.x, new_y, dungeon):
                self.y = new_y
            
            # 更新方向：0=下, 1=左, 2=右, 3=上
            if abs(dy) > abs(dx):
                self.anim_dir = 0 if dy > 0 else 3  # 下 or 上
            else:
                self.anim_dir = 1 if dx < 0 else 2  # 左 or 右
            
            # 更新动画
            self.anim_timer += dt
            if self.anim_timer >= PLAYER_ANIM_SPEED:
                self.anim_timer = 0
                self.anim_frame = (self.anim_frame + 1) % 3
        else:
            # 静止时回到 idle 帧
            self.anim_frame = 0
    
    def face_towards(self, target_x, target_y, cam_x, cam_y, dt):
        """面向目标位置（用于站立时朝向鼠标）"""
        # 将屏幕坐标转换为世界坐标
        world_x = (target_x + cam_x) / TILE
        world_y = (target_y + cam_y) / TILE
        
        dx = world_x - self.x
        dy = world_y - self.y
        
        if abs(dy) > abs(dx):
            self.anim_dir = 0 if dy > 0 else 3  # 下 or 上
        else:
            self.anim_dir = 1 if dx < 0 else 2  # 左 or 右
        
        # ----- 3. 冷却计时 -----
        if self.atk_cd > 0:
            self.atk_cd -= dt
        
        # 技能冷却
        for sk in self.skills:
            if sk['timer'] > 0:
                sk['timer'] -= dt
        
        # ----- 4. 自动攻击 -----
        # 如果有选中的目标，且目标存活，且冷却完毕
        if self.target and self.target.hp > 0 and self.atk_cd <= 0:
            # 计算距离
            dist = math.sqrt((self.x - self.target.x)**2 + (self.y - self.target.y)**2)
            # 距离小于1.5格时攻击
            if dist <= 1.5:
                dmg = self.dmg
                # 5%暴击几率
                crit = random.random() < 0.05
                if crit:
                    dmg = int(dmg * 1.5)  # 暴击伤害150%
                self.target.hp -= dmg
                self.atk_cd = 0.67  # 攻击间隔约0.67秒
    
    def _can_move(self, x, y, dungeon):
        """碰撞检测：只检查中心点是否可行走"""
        return dungeon.walkable(x, y)
    
    def use_skill(self, idx, tx, ty, game):
        """
        使用技能
        
        参数：
        idx: 技能索引（0-3）
        tx, ty: 技能目标位置（屏幕坐标转化的世界坐标）
        game: 游戏对象（用于创建投射物等）
        
        技能效果：
        - 火球：向目标发射投射物
        - 冰霜：对范围内敌人造成伤害
        - 冲锋：瞬间移动到目标位置
        - 治疗：恢复自身生命
        """
        if idx >= len(self.skills):
            return
        
        sk = self.skills[idx]
        
        # 检查冷却和法力
        if sk['timer'] > 0 or self.mp < sk['cost']:
            return
        
        # 消耗法力，开始冷却
        self.mp -= sk['cost']
        sk['timer'] = sk['cd']
        
        if sk['name'] == '火球':
            # 火球：创建投射物
            game.projs.append({'x': self.x, 'y': self.y, 'tx': tx, 'ty': ty, 'dmg': sk['dmg'], 'spd': 12})
        elif sk['name'] == '冰霜':
            # 冰霜：范围伤害
            for e in game.enemies:
                if math.sqrt((self.x-e.x)**2 + (self.y-e.y)**2) <= sk['radius']:
                    e.hp -= sk['dmg']
        elif sk['name'] == '冲锋':
            # 冲锋：瞬间移动
            dx, dy = tx - self.x, ty - self.y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0:
                d = min(dist, sk['dist'])  # 最大移动距离
                nx, ny = self.x + dx/dist*d, self.y + dy/dist*d
                if game.dungeon.walkable(nx, ny):  # 目标点可行走
                    self.x, self.y = nx, ny
        elif sk['name'] == '治疗':
            # 治疗：恢复生命
            self.hp = min(self.max_hp, self.hp + sk['heal'])


# ================================================================================
# 敌人类 - AI追踪与行为
# ================================================================================
class Enemy:
    """
    敌人AI类
    
    核心特性：
    1. 方向感系统：每隔1格重新获取方向（模拟"看不清"）
    2. 360度任意方向移动（使用流场）
    3. 碰撞反弹：遇到墙壁时沿法线方向转向
    4. 中心点碰撞检测：只检查位置点是否可行走
    
    敌人类型（属性倍率）：
    - skeleton: 骷髅（基础）
    - goblin: 哥布林（高攻高速）
    - orc: 兽人（高血量）
    - demon: 恶魔（全面增强）
    - boss: Boss（超高属性）
    """
    
    # 敌人类型属性表
    # hp/dmg/spd/xp 是倍率，乘以基础值
    TYPES = {
        'skeleton': {'hp': 1.0, 'dmg': 1.0, 'spd': 1.0, 'xp': 1.0},  # 骷髅
        'goblin': {'hp': 0.8, 'dmg': 1.2, 'spd': 1.3, 'xp': 1.2},   # 哥布林
        'orc': {'hp': 1.5, 'dmg': 1.3, 'spd': 0.8, 'xp': 1.5},     # 兽人
        'demon': {'hp': 2.0, 'dmg': 1.5, 'spd': 1.0, 'xp': 2.0},   # 恶魔
        'boss': {'hp': 8.0, 'dmg': 2.5, 'spd': 0.6, 'xp': 10.0},    # Boss
    }
    
    def __init__(self, x, y, etype, floor):
        """
        初始化敌人
        
        参数：
        x, y: 格子坐标
        etype: 敌人类型字符串
        floor: 当前楼层（影响属性成长）
        """
        # 位置：加上0.5使敌人位于格子中心
        self.x, self.y = x + 0.5, y + 0.5
        self.etype = etype
        t = self.TYPES[etype]  # 获取类型属性
        
        # ----- 属性计算 -----
        # 基础公式：base * (1 + floor * 成长系数) * 类型倍率
        self.radius = 0.5 if etype == 'boss' else 0.35  # Boss体积更大
        self.max_hp = int(30 * (1 + floor * 0.2) * t['hp'])
        self.hp = self.max_hp
        self.dmg = int(5 * (1 + floor * 0.15) * t['dmg'])
        self.speed = CFG['enemy_speed'] * t['spd']
        self.xp = int(20 * (1 + floor * 0.1) * t['xp'])
        self.atk_cd = 0
        
        # ----- 方向感系统 -----
        self.dir_x, self.dir_y = 0, 0    # 当前移动方向（单位向量）
        self.sense = 0                   # 方向感（0-1，1为满分）
        self.start_x, self.start_y = self.x, self.y  # 上次获取方向的位置
    
    def update(self, dt, player, dungeon, flow, game):
        """
        敌人AI更新 - 任意方向追踪
        
        ===========================================
        方向感系统工作原理：
        ===========================================
        1. 敌人获取一个方向后，可以朝该方向移动1格距离
        2. 移动1格后（方向感耗尽），需要重新获取方向
        3. 这样模拟了敌人"看不清远处"的特性
        4. 如果不在格子中心，会先回到中心再追踪
        
        参数：
        dt: 时间增量（秒）
        player: 玩家对象
        dungeon: 地牢对象
        flow: 流场对象
        game: 游戏主对象
        """
        # ===== 1. 冷却处理 =====
        if self.atk_cd > 0:
            self.atk_cd -= dt
        
        # ===== 2. 计算与玩家的距离 =====
        dist = math.sqrt((self.x - player.x)**2 + (self.y - player.y)**2)
        
        # ===== 3. 如果在感知范围内，开始追踪 =====
        if dist <= CFG['aggro_range']:
            
            # ----- 3.1 计算已移动距离 -----
            # 从上次获取方向到现在移动的距离
            moved = math.sqrt((self.x - self.start_x)**2 + (self.y - self.start_y)**2)
            
            # ----- 3.2 检查是否在格子中心 -----
            # 格子中心 = 当前格子索引 + 0.5
            cx, cy = int(self.x) + 0.5, int(self.y) + 0.5
            # 允许一定误差范围（0.15格，约5像素）
            in_center = abs(self.x - cx) < 0.15 and abs(self.y - cy) < 0.15
            
            # ----- 3.3 判断是否需要获取新方向 -----
            # 需要获取新方向的情况：
            # 1. 已移动距离 >= 1.0 格（方向感耗尽）
            # 2. 当前没有方向（初始化时）
            # 3. 不在格子中心（需要先回到中心）
            need_dir = (moved >= 1.0) or (self.dir_x == 0 and self.dir_y == 0) or (not in_center)
            
            if need_dir:
                # ===== 获取方向 =====
                # 从流场获取方向（360度任意方向）
                flow_dir = flow.get(self.x, self.y)
                
                if flow_dir:
                    # 使用流场方向
                    self.dir_x, self.dir_y = flow_dir
                else:
                    # 没有流场，直接朝玩家移动
                    dx = player.x - self.x
                    dy = player.y - self.y
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        self.dir_x, self.dir_y = dx/length, dy/length
                
                # 记录当前位置作为新起点，重置方向感
                self.start_x, self.start_y = self.x, self.y
                self.sense = 1.0  # 方向感满分
            
            # ----- 3.4 更新方向感（消耗） -----
            self.sense = max(0, 1.0 - moved)
            
            # ----- 3.5 按当前方向移动 -----
            new_x = self.x + self.dir_x * self.speed * dt
            new_y = self.y + self.dir_y * self.speed * dt
            
            # X轴移动 + 碰撞检测
            if self._can_move(new_x, self.y, dungeon):
                self.x = new_x
            else:
                # 碰撞反弹
                self._bounce_off_wall(dungeon)
            
            # Y轴移动 + 碰撞检测
            if self._can_move(self.x, new_y, dungeon):
                self.y = new_y
            else:
                # 碰撞反弹
                self._bounce_off_wall(dungeon)
            
            # ----- 3.6 攻击玩家 -----
            if dist <= 1 and self.atk_cd <= 0:
                player.hp -= max(1, self.dmg - 5)
                self.atk_cd = 1.0
    
    def _bounce_off_wall(self, dungeon):
        """
        沿碰撞面法线方向反弹
        
        原理：
        - 检测上下左右四个方向哪个可行走
        - 选择一个可行走的方向作为新的移动方向
        - 这样比简单反转更自然
        
        例如：
        - 如果右边有墙，但上方能走 → 向上反弹
        - 如果上方有墙，但右边能走 → 向右反弹
        """
        # 检测四个方向哪个可行走（向该方向移动0.1格测试）
        can_up = dungeon.walkable(self.x, self.y - 0.1)
        can_down = dungeon.walkable(self.x, self.y + 0.1)
        can_left = dungeon.walkable(self.x - 0.1, self.y)
        can_right = dungeon.walkable(self.x + 0.1, self.y)
        
        # 根据墙壁位置选择反弹方向
        # 规则：优先选择不违背当前移动趋势的方向
        
        if not can_right and can_up:
            # 右边有墙，上面能走 → 向上反弹
            self.dir_x, self.dir_y = 0, -1
        elif not can_right and can_down:
            # 右边有墙，下面能走 → 向下反弹
            self.dir_x, self.dir_y = 0, 1
        elif not can_left and can_up:
            # 左边有墙，上面能走 → 向上反弹
            self.dir_x, self.dir_y = 0, -1
        elif not can_left and can_down:
            # 左边有墙，下面能走 → 向下反弹
            self.dir_x, self.dir_y = 0, 1
        elif not can_up and can_right:
            # 上边有墙，右边能走 → 向右反弹
            self.dir_x, self.dir_y = 1, 0
        elif not can_up and can_left:
            # 上边有墙，左边能走 → 向左反弹
            self.dir_x, self.dir_y = -1, 0
        elif not can_down and can_right:
            # 下边有墙，右边能走 → 向右反弹
            self.dir_x, self.dir_y = 1, 0
        elif not can_down and can_left:
            # 下边有墙，左边能走 → 向左反弹
            self.dir_x, self.dir_y = -1, 0
        else:
            # 没有找到有效方向，简单反转
            if self.dir_x != 0:
                self.dir_x *= -1
            if self.dir_y != 0:
                self.dir_y *= -1
        
        # 重置方向感
        self.start_x = self.x
        self.start_y = self.y
        self.sense = 1.0
    
    def _can_move(self, x, y, dungeon):
        """碰撞检测：只检查中心点"""
        return dungeon.walkable(x, y)


class Game:
    """游戏主类"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Shadow Abyss")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_big = pygame.font.Font(None, 36)
        
        self.floor = 1
        self.paused = False
        self.game_over = False
        self.dist_to_exit = 999  # 玩家到入口的距离
        self.mouse_x, self.mouse_y = 0, 0  # 鼠标位置
        
        self.dungeon = None
        self.flow = None
        self.player = None
        self.enemies = []
        self.loot = []
        self.projs = []
        self.msgs = []
        
        self.cam_x, self.cam_y = 0, 0
        self.flow_update_x, self.flow_update_y = 0, 0
        
        self.init_floor()
    
    def init_floor(self):
        """初始化楼层"""
        self.dungeon = Dungeon()
        self.flow = FlowField(self.dungeon)
        
        if not self.player:
            self.player = Player(self.dungeon.spawn[0] + 0.5, self.dungeon.spawn[1] + 0.5)
        else:
            self.player.x = self.dungeon.spawn[0] + 0.5
            self.player.y = self.dungeon.spawn[1] + 0.5
        
        self.enemies = []
        self.loot = []
        self.projs = []
        
        # 生成敌人
        floor_tiles = sum(row.count(0) for row in self.dungeon.tiles)
        n_enemies = int(floor_tiles * 0.012)
        
        types = ['skeleton', 'goblin', 'orc', 'demon']
        weights = [40, 30, 20, 10]
        
        for _ in range(n_enemies):
            room = random.choice(self.dungeon.rooms)
            x = room['x'] + random.randint(1, room['w'] - 2)
            y = room['y'] + random.randint(1, room['h'] - 2)
            self.enemies.append(Enemy(x, y, random.choices(types, weights)[0], self.floor))
        
        # Boss
        if self.floor % 5 == 0:
            ex, ey = self.dungeon.exit
            self.enemies.append(Enemy(ex - 2, ey, 'boss', self.floor))
        
        self.flow.update(self.player.x, self.player.y)
        self.flow_update_x, self.flow_update_y = self.player.x, self.player.y
        self.msgs.append({'text': f"Floor {self.floor}", 't': 2})
    
    def run(self):
        """游戏主循环"""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._on_key(event.key, event.unicode, event.scancode)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._on_click(event.button, event.pos)
            
            if not self.game_over and not self.paused:
                self._update(dt)
            
            self._render()
            pygame.display.flip()
        
        pygame.quit()
    
    def _on_key(self, key, unicode_char, scancode):
        # 调试
        print(f"Key: key={key}, unicode='{unicode_char}', scancode={scancode}")
        
        # 使用 unicode 字符检测
        if unicode_char == '\x1b':  # ESC
            self.paused = not self.paused
        elif unicode_char == 'r' and self.game_over:
            self.game_over = False
            self.floor = 1
            self.player = None
            self.init_floor()
        elif unicode_char == 'e' or unicode_char == 'E':
            # 按E进入下一层（需在入口附近）
            dist = math.sqrt((self.player.x - self.dungeon.exit[0])**2 + (self.player.y - self.dungeon.exit[1])**2)
            print(f"E pressed! dist={dist}")
            if dist < 1.5:
                print("Going to next floor!")
                self.floor += 1
                self.init_floor()
        elif unicode_char in ['1', '2', '3', '4']:
            mx, my = pygame.mouse.get_pos()
            wx = (mx + self.cam_x) / TILE
            wy = (my + self.cam_y) / TILE
            self.player.use_skill(int(unicode_char) - 1, wx, wy, self)
    
    def _on_click(self, btn, pos):
        if self.game_over or self.paused:
            return
        
        wx = (pos[0] + self.cam_x) / TILE
        wy = (pos[1] + self.cam_y) / TILE
        
        if btn == 1:
            self.player.target = None
            for e in self.enemies:
                if math.sqrt((wx - e.x)**2 + (wy - e.y)**2) < 0.6:
                    self.player.target = e
                    break
    
    def _update(self, dt):
        # 玩家
        keys = pygame.key.get_pressed()
        
        # 记录移动状态
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        is_moving = (dx != 0 or dy != 0)
        
        self.player.update(dt, self.dungeon, keys)
        
        # 如果不移动，面向鼠标
        if not is_moving:
            mx, my = pygame.mouse.get_pos()
            self.player.face_towards(mx, my, self.cam_x, self.cam_y, dt)
        
        # 流场更新
        if abs(self.player.x - self.flow_update_x) > 0.5 or abs(self.player.y - self.flow_update_y) > 0.5:
            self.flow.update(self.player.x, self.player.y)
            self.flow_update_x, self.flow_update_y = self.player.x, self.player.y
        
        # 敌人
        for e in self.enemies:
            e.update(dt, self.player, self.dungeon, self.flow, self)
        
        # 移除死亡敌人
        for e in self.enemies[:]:
            if e.hp <= 0:
                self.loot.append({'type': 'gold', 'x': e.x, 'y': e.y, 'amt': random.randint(5, 50)})
                if random.random() < 0.2:
                    self.loot.append({'type': 'item', 'x': e.x, 'y': e.y})
                self.player.xp += e.xp
                # 升级
                while self.player.xp >= self.player.xp_to:
                    self.player.xp -= self.player.xp_to
                    self.player.level += 1
                    self.player.xp_to = int(100 * 1.5 ** (self.player.level - 1))
                    self.player.max_hp += 20
                    self.player.hp = self.player.max_hp
                self.enemies.remove(e)
        
        # 投射物
        for p in self.projs[:]:
            dx, dy = p['tx'] - p['x'], p['ty'] - p['y']
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < 0.3:
                self.projs.remove(p)
                continue
            p['x'] += dx/dist * p['spd'] * dt
            p['y'] += dy/dist * p['spd'] * dt
            
            for e in self.enemies:
                if math.sqrt((p['x']-e.x)**2 + (p['y']-e.y)**2) < 0.5:
                    e.hp -= p['dmg']
                    if p in self.projs:
                        self.projs.remove(p)
                    break
        
        # 拾取
        for lt in self.loot[:]:
            if math.sqrt((self.player.x - lt['x'])**2 + (self.player.y - lt['y'])**2) < 1:
                if lt['type'] == 'gold':
                    self.player.gold += lt['amt']
                self.loot.remove(lt)
        
        # 检查是否在入口旁（用于提示）
        self.dist_to_exit = math.sqrt((self.player.x - self.dungeon.exit[0])**2 + (self.player.y - self.dungeon.exit[1])**2)
        
        # 死亡
        if self.player.hp <= 0:
            self.game_over = True
        
        # 摄像机
        self.cam_x = self.player.x * TILE - SCREEN_W // 2
        self.cam_y = self.player.y * TILE - SCREEN_H // 2
        
        # 消息
        for m in self.msgs[:]:
            m['t'] -= dt
            if m['t'] <= 0:
                self.msgs.remove(m)
    
    def _render(self):
        self.screen.fill(C['bg'])
        
        # 地牢
        sx = max(0, int(self.cam_x / TILE) - 1)
        sy = max(0, int(self.cam_y / TILE) - 1)
        ex = min(self.dungeon.w, int(sx + SCREEN_W / TILE) + 3)
        ey = min(self.dungeon.h, int(sy + SCREEN_H / TILE) + 3)
        
        for y in range(sy, ey):
            for x in range(sx, ex):
                px = x * TILE - self.cam_x
                py = y * TILE - self.cam_y
                
                if self.dungeon.tiles[y][x] == 0:
                    c = C['floor'] if (x + y) % 2 == 0 else C['floor2']
                    pygame.draw.rect(self.screen, c, (px, py, TILE, TILE))
                else:
                    pygame.draw.rect(self.screen, C['wall'], (px, py, TILE, TILE))
                    pygame.draw.rect(self.screen, C['wall_top'], (px, py, TILE, TILE // 2))
        
        # ===== 流场可视化：显示每个格子的4方向箭头 =====
        for y in range(sy, ey):
            for x in range(sx, ex):
                if self.dungeon.tiles[y][x] == 0:
                    flow = self.flow.field[y][x]
                    if flow:
                        cx = x * TILE - self.cam_x + TILE // 2
                        cy = y * TILE - self.cam_y + TILE // 2
                        # 根据方向画箭头
                        fx = cx + flow[0] * 12
                        fy = cy + flow[1] * 12
                        pygame.draw.line(self.screen, C['flow'], (cx, cy), (fx, fy), 2)
        
        # 出口/入口
        ex = self.dungeon.exit[0] * TILE - self.cam_x
        ey = self.dungeon.exit[1] * TILE - self.cam_y
        
        # 绘制传送门效果（旋转动画）
        portal_offset = int(pygame.time.get_ticks() / 100) % 4
        portal_colors = [(68, 170, 136), (100, 200, 180), (68, 170, 136), (50, 140, 110)]
        pygame.draw.circle(self.screen, portal_colors[portal_offset], (int(ex + TILE/2), int(ey + TILE/2)), TILE//2 + portal_offset)
        pygame.draw.circle(self.screen, (40, 40, 50), (int(ex + TILE/2), int(ey + TILE/2)), TILE//3)
        
        # 提示按E进入
        if self.dist_to_exit < 2:
            hint = self.font.render("Press E", True, C['white'])
            self.screen.blit(hint, (ex, ey - 20))
        
        # 战利品
        for lt in self.loot:
            px = lt['x'] * TILE - self.cam_x
            py = lt['y'] * TILE - self.cam_y
            pygame.draw.circle(self.screen, C['gold'], (int(px), int(py)), 6)
        
        # 敌人（使用精灵图）
        for e in self.enemies:
            px = e.x * TILE - self.cam_x
            py = e.y * TILE - self.cam_y
            r = int(e.radius * TILE)
            
            # 敌人动画（简单的帧循环）
            e_anim_frame = int(pygame.time.get_ticks() / 200) % 4  # 4列动画
            
            # Boss体型更大
            if e.etype == 'boss':
                boss_sprite = pygame.transform.scale(ENEMY_FRAMES[0][e_anim_frame], (TILE * 2, TILE * 2))
                sprite_rect = boss_sprite.get_rect(center=(int(px), int(py)))
                self.screen.blit(boss_sprite, sprite_rect)
            else:
                sprite_rect = ENEMY_FRAMES[0][e_anim_frame].get_rect(center=(int(px), int(py)))
                self.screen.blit(ENEMY_FRAMES[0][e_anim_frame], sprite_rect)
            
            # 血条
            if e.hp < e.max_hp:
                pygame.draw.rect(self.screen, (50, 50, 50), (px - 16, py - r - 8, 32, 4))
                pygame.draw.rect(self.screen, C['hp'], (px - 16, py - r - 8, 32 * e.hp / e.max_hp, 4))
        
        # 玩家（使用精灵图）
        px = self.player.x * TILE - self.cam_x
        py = self.player.y * TILE - self.cam_y
        player_frame = PLAYER_FRAMES[self.player.anim_dir][self.player.anim_frame]
        sprite_rect = player_frame.get_rect(center=(int(px), int(py)))
        self.screen.blit(player_frame, sprite_rect)
        
        # 投射物
        for p in self.projs:
            px = p['x'] * TILE - self.cam_x
            py = p['y'] * TILE - self.cam_y
            pygame.draw.circle(self.screen, C['hp'], (int(px), int(py)), 8)
        
        # UI
        self._render_ui()
    
    def _render_ui(self):
        # 血条
        pygame.draw.rect(self.screen, (30, 30, 40), (15, 15, 210, 75))
        pygame.draw.rect(self.screen, C['hp'], (20, 20, 200 * self.player.hp / self.player.max_hp, 20))
        pygame.draw.rect(self.screen, C['mp'], (20, 45, 200 * self.player.mp / self.player.max_mp, 20))
        pygame.draw.rect(self.screen, C['xp'], (20, 70, 200 * self.player.xp / self.player.xp_to, 20))
        
        hp_t = self.font.render(f"HP: {int(self.player.hp)}/{self.player.max_hp}", True, C['white'])
        mp_t = self.font.render(f"MP: {int(self.player.mp)}/{self.player.max_mp}", True, C['white'])
        xp_t = self.font.render(f"Lv.{self.player.level}", True, C['white'])
        self.screen.blit(hp_t, (25, 22))
        self.screen.blit(mp_t, (25, 47))
        self.screen.blit(xp_t, (25, 72))
        
        info = self.font.render(f"Floor: {self.floor}  Gold: {self.player.gold}", True, C['gray'])
        self.screen.blit(info, (20, 100))
        
        # 技能
        for i, sk in enumerate(self.player.skills):
            x = SCREEN_W // 2 - 120 + i * 60
            y = SCREEN_H - 70
            
            # 技能图标背景
            pygame.draw.rect(self.screen, (20, 20, 30), (x, y, 50, 50), border_radius=8)
            
            # 绘制技能图标（如果有）
            if SKILL_ICONS[i]:
                icon = SKILL_ICONS[i]
                self.screen.blit(icon, (x + 5, y + 5))
            else:
                # 无图标时显示颜色方块+数字
                colors = [(255, 100, 0), (100, 200, 255), (255, 200, 0), (100, 255, 100)]
                pygame.draw.rect(self.screen, colors[i], (x + 5, y + 5, 40, 40), border_radius=4)
                k = self.font.render(str(i + 1), True, C['white'])
                self.screen.blit(k, (x + 18, y + 18))
            
            # 冷却显示
            if sk['timer'] > 0:
                # 半透明遮罩
                overlay = pygame.Surface((50, 50), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (x, y))
                cd = self.font.render(f"{sk['timer']:.1f}", True, C['white'])
                self.screen.blit(cd, (x + 15, y + 18))
        
        # 消息
        for i, m in enumerate(self.msgs):
            t = self.font_big.render(m['text'], True, C['xp'])
            x = SCREEN_W // 2 - t.get_width() // 2
            self.screen.blit(t, (x, SCREEN_H // 2 - 50 + i * 40))
        
        # 暂停/死亡
        if self.paused:
            t = self.font_big.render("PAUSED", True, C['xp'])
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2))
        elif self.game_over:
            t = self.font_big.render("GAME OVER - Press R", True, C['hp'])
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2))


if __name__ == '__main__':
    Game().run()
