"""
Shadow Abyss - Diablo-like ARPG
重构版本：简化代码，核心功能保留
"""
import pygame
import random
import math
from collections import deque

pygame.init()

# 常量
SCREEN_W, SCREEN_H = 1280, 720
TILE = 32
FPS = 30

# 颜色
C = {
    'bg': (15, 15, 20),
    'floor': (50, 50, 60),
    'floor2': (45, 45, 55),
    'wall': (25, 25, 35),
    'wall_top': (35, 35, 50),
    'player': (52, 152, 219),
    'enemy': (231, 76, 60),
    'gold': (241, 196, 15),
    'hp': (231, 76, 60),
    'mp': (52, 152, 219),
    'xp': (241, 196, 15),
    'exit': (68, 170, 136),
    'white': (255, 255, 255),
    'gray': (150, 150, 150),
    'flow': (100, 200, 100),
}

# 配置
CFG = {
    'dungeon_w': 50,
    'dungeon_h': 40,
    'rooms_min': 10,
    'rooms_max': 15,
    'room_min': 6,
    'room_max': 12,
    'player_speed': 4.0,
    'enemy_speed': 3.0,
    'aggro_range': 10,
}


class Dungeon:
    """地牢生成"""
    def __init__(self):
        self.w = CFG['dungeon_w']
        self.h = CFG['dungeon_h']
        self.tiles = [[1] * self.w for _ in range(self.h)]
        self.rooms = []
        self.generate()
    
    def generate(self):
        # 生成房间
        for _ in range(random.randint(CFG['rooms_min'], CFG['rooms_max'])):
            rw = random.randint(CFG['room_min'], CFG['room_max'])
            rh = random.randint(CFG['room_min'], CFG['room_max'])
            rx = random.randint(1, self.w - rw - 1)
            ry = random.randint(1, self.h - rh - 1)
            
            # 检查重叠
            overlap = any(
                rx < r['x'] + r['w'] + 1 and rx + rw + 1 > r['x'] and
                ry < r['y'] + r['h'] + 1 and ry + rh + 1 > r['y']
                for r in self.rooms
            )
            
            if not overlap:
                for y in range(ry, ry + rh):
                    for x in range(rx, rx + rw):
                        self.tiles[y][x] = 0
                self.rooms.append({'x': rx, 'y': ry, 'w': rw, 'h': rh})
        
        # 连接房间
        for i in range(1, len(self.rooms)):
            self._connect(self.rooms[i-1], self.rooms[i])
        
        # 出生点和出口
        self.spawn = self._center(self.rooms[0]) if self.rooms else (2, 2)
        self.exit = self._center(self.rooms[-1]) if len(self.rooms) > 1 else (self.w - 3, self.h - 3)
    
    def _center(self, r):
        return (r['x'] + r['w'] // 2, r['y'] + r['h'] // 2)
    
    def _connect(self, a, b):
        ax, ay = self._center(a)
        bx, by = self._center(b)
        
        # 水平走廊
        for x in range(min(ax, bx), max(ax, bx) + 1):
            if 0 <= ay < self.h:
                self.tiles[ay][x] = 0
        # 垂直走廊
        for y in range(min(ay, by), max(ay, by) + 1):
            if 0 <= bx < self.w:
                self.tiles[y][bx] = 0
    
    def walkable(self, x, y):
        """检查坐标是否可行走"""
        tx, ty = int(math.floor(x)), int(math.floor(y))
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return self.tiles[ty][tx] == 0
        return False


class FlowField:
    """
    流场系统（360度任意方向版）
    每个格子存储指向目标的单位向量（任意角度）
    """
    def __init__(self, dungeon):
        self.dungeon = dungeon
        # 8方向用于BFS距离计算
        self.DIRS8 = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
        self.field = [[None] * dungeon.w for _ in range(dungeon.h)]
        self.dist = [[float('inf')] * dungeon.w for _ in range(dungeon.h)]
        self.target_x = 0
        self.target_y = 0
    
    def update(self, target_x, target_y):
        """从目标点计算360度流场"""
        self.target_x = target_x
        self.target_y = target_y
        tx, ty = int(target_x), int(target_y)
        
        # 重置
        self.dist = [[float('inf')] * self.dungeon.w for _ in range(self.dungeon.h)]
        self.field = [[None] * self.dungeon.w for _ in range(self.dungeon.h)]
        
        # BFS计算距离
        queue = deque()
        if 0 <= tx < self.dungeon.w and 0 <= ty < self.dungeon.h:
            if self.dungeon.tiles[ty][tx] == 0:
                self.dist[ty][tx] = 0
                queue.append((tx, ty))
        
        while queue:
            x, y = queue.popleft()
            d = self.dist[y][x]
            
            for dx, dy in self.DIRS8:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.dungeon.w and 0 <= ny < self.dungeon.h:
                    if self.dungeon.tiles[ny][nx] == 0:
                        if d + 1 < self.dist[ny][nx]:
                            self.dist[ny][nx] = d + 1
                            queue.append((nx, ny))
        
        # 计算流向：每个格子指向距离目标最近的可通行格子
        for y in range(self.dungeon.h):
            for x in range(self.dungeon.w):
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
                    
                    if best_dir and best_dist < self.dist[y][x]:
                        # 归一化为单位向量（360度任意方向）
                        length = math.sqrt(best_dir[0]**2 + best_dir[1]**2)
                        self.field[y][x] = (best_dir[0]/length, best_dir[1]/length)
    
    def get(self, x, y):
        """获取流场方向（任意角度的单位向量）"""
        tx, ty = int(x), int(y)
        if 0 <= tx < self.dungeon.w and 0 <= ty < self.dungeon.h:
            return self.field[ty][tx]
        return None


class Player:
    """玩家"""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 0.25
        self.speed = CFG['player_speed']
        self.level = 1
        self.xp, self.xp_to = 0, 100
        self.hp, self.max_hp = 100, 100
        self.mp, self.max_mp = 50, 50
        self.dmg = 10
        self.gold = 0
        self.atk_cd = 0
        self.target = None
        
        # 技能
        self.skills = [
            {'name': '火球', 'cost': 15, 'dmg': 30, 'cd': 2, 'timer': 0},
            {'name': '冰霜', 'cost': 20, 'dmg': 20, 'cd': 4, 'timer': 0, 'radius': 4},
            {'name': '冲锋', 'cost': 10, 'cd': 3, 'timer': 0, 'dist': 6},
            {'name': '治疗', 'cost': 25, 'heal': 50, 'cd': 5, 'timer': 0},
        ]
    
    def update(self, dt, dungeon, keys):
        # 回复
        self.hp = min(self.max_hp, self.hp + 0.5 * dt)
        self.mp = min(self.max_mp, self.mp + 0.3 * dt)
        
        # 移动
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        
        if dx or dy:
            length = math.sqrt(dx*dx + dy*dy)
            dx, dy = dx/length, dy/length
            new_x = self.x + dx * self.speed * dt
            new_y = self.y + dy * self.speed * dt
            
            if self._can_move(new_x, self.y, dungeon):
                self.x = new_x
            if self._can_move(self.x, new_y, dungeon):
                self.y = new_y
        
        # 攻击冷却
        if self.atk_cd > 0:
            self.atk_cd -= dt
        
        # 技能冷却
        for sk in self.skills:
            if sk['timer'] > 0:
                sk['timer'] -= dt
        
        # 自动攻击目标
        if self.target and self.target.hp > 0 and self.atk_cd <= 0:
            dist = math.sqrt((self.x - self.target.x)**2 + (self.y - self.target.y)**2)
            if dist <= 1.5:
                dmg = self.dmg
                crit = random.random() < 0.05
                if crit:
                    dmg = int(dmg * 1.5)
                self.target.hp -= dmg
                self.atk_cd = 0.67
    
    def _can_move(self, x, y, dungeon):
        """碰撞检测：只检查中心点是否可行走"""
        return dungeon.walkable(x, y)
    
    def use_skill(self, idx, tx, ty, game):
        if idx >= len(self.skills):
            return
        sk = self.skills[idx]
        if sk['timer'] > 0 or self.mp < sk['cost']:
            return
        
        self.mp -= sk['cost']
        sk['timer'] = sk['cd']
        
        if sk['name'] == '火球':
            game.projs.append({'x': self.x, 'y': self.y, 'tx': tx, 'ty': ty, 'dmg': sk['dmg'], 'spd': 12})
        elif sk['name'] == '冰霜':
            for e in game.enemies:
                if math.sqrt((self.x-e.x)**2 + (self.y-e.y)**2) <= sk['radius']:
                    e.hp -= sk['dmg']
        elif sk['name'] == '冲锋':
            dx, dy = tx - self.x, ty - self.y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0:
                d = min(dist, sk['dist'])
                nx, ny = self.x + dx/dist*d, self.y + dy/dist*d
                if game.dungeon.walkable(nx, ny):
                    self.x, self.y = nx, ny
        elif sk['name'] == '治疗':
            self.hp = min(self.max_hp, self.hp + sk['heal'])


class Enemy:
    """敌人"""
    TYPES = {
        'skeleton': {'hp': 1.0, 'dmg': 1.0, 'spd': 1.0, 'xp': 1.0},
        'goblin': {'hp': 0.8, 'dmg': 1.2, 'spd': 1.3, 'xp': 1.2},
        'orc': {'hp': 1.5, 'dmg': 1.3, 'spd': 0.8, 'xp': 1.5},
        'demon': {'hp': 2.0, 'dmg': 1.5, 'spd': 1.0, 'xp': 2.0},
        'boss': {'hp': 8.0, 'dmg': 2.5, 'spd': 0.6, 'xp': 10.0},
    }
    
    def __init__(self, x, y, etype, floor):
        self.x, self.y = x + 0.5, y + 0.5  # 初始化在格子中心
        self.etype = etype
        t = self.TYPES[etype]
        
        self.radius = 0.5 if etype == 'boss' else 0.35
        self.max_hp = int(30 * (1 + floor * 0.2) * t['hp'])
        self.hp = self.max_hp
        self.dmg = int(5 * (1 + floor * 0.15) * t['dmg'])
        self.speed = CFG['enemy_speed'] * t['spd']
        self.xp = int(20 * (1 + floor * 0.1) * t['xp'])
        self.atk_cd = 0
        
        # 方向感
        self.dir_x, self.dir_y = 0, 0
        self.sense = 0  # 初始为0，需要先获取方向
        self.start_x, self.start_y = self.x, self.y
    
    def update(self, dt, player, dungeon, flow, game):
        """
        敌人AI更新 - 任意方向追踪
        
        核心逻辑：
        1. 方向感系统：每次获取方向后，可以朝任意方向移动1格距离
        2. 方向感耗尽后，重新朝玩家方向获取新方向
        3. 如果不在格子中心，先回到中心再继续追踪
        
        参数：
        dt: 时间增量（秒）
        player: 玩家对象
        dungeon: 地牢对象
        flow: 流场对象（现在返回任意方向，不再是4方向）
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
            # 1. 已移动距离 >= 1.0 格（方向感耗尽，需要重新定向）
            # 2. 当前没有方向（初始化时）
            # 3. 不在格子中心（需要先回到中心）
            need_dir = (moved >= 1.0) or (self.dir_x == 0 and self.dir_y == 0) or (not in_center)
            
            if need_dir:
                # ===== 获取任意方向 =====
                # 流场现在直接返回从敌人到玩家的单位向量（任意方向）
                flow_dir = flow.get(self.x, self.y)
                
                if flow_dir:
                    # 使用流场返回的任意方向（可能是绕过墙壁的路径方向）
                    self.dir_x, self.dir_y = flow_dir
                else:
                    # 没有流场（如目标不可达），直接朝玩家任意角度移动
                    dx = player.x - self.x
                    dy = player.y - self.y
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        self.dir_x, self.dir_y = dx/length, dy/length
                
                # 记录当前位置作为新起点，重置方向感
                self.start_x, self.start_y = self.x, self.y
                self.sense = 1.0  # 方向感满分，可以走1格
            
            # ----- 3.4 更新方向感（消耗） -----
            # 方向感 = 1.0 - 已移动距离，最小为0
            self.sense = max(0, 1.0 - moved)
            
            # ----- 3.5 按当前任意方向移动 -----
            new_x = self.x + self.dir_x * self.speed * dt
            new_y = self.y + self.dir_y * self.speed * dt
            
            # 分别检测X和Y轴的碰撞（允许斜着走）
            if self._can_move(new_x, self.y, dungeon):
                self.x = new_x
            else:
                # 沿碰撞面法线方向反弹：检测上下左右哪个方向有墙
                self._bounce_off_wall(dungeon)
            
            if self._can_move(self.x, new_y, dungeon):
                self.y = new_y
            else:
                # 沿碰撞面法线方向反弹
                self._bounce_off_wall(dungeon)
            
            # ----- 3.6 攻击玩家 -----
            if dist <= 1 and self.atk_cd <= 0:
                player.hp -= max(1, self.dmg - 5)
                self.atk_cd = 1.0
    
    def _bounce_off_wall(self, dungeon):
        """沿碰撞面法线方向反弹"""
        # 检测四个方向哪个有墙
        can_up = dungeon.walkable(self.x, self.y - 0.1)
        can_down = dungeon.walkable(self.x, self.y + 0.1)
        can_left = dungeon.walkable(self.x - 0.1, self.y)
        can_right = dungeon.walkable(self.x + 0.1, self.y)
        
        # 如果能往某个方向走，说明那边没有墙
        # 优先选择垂直于当前移动方向的法线
        
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
                    self._on_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._on_click(event.button, event.pos)
            
            if not self.game_over and not self.paused:
                self._update(dt)
            
            self._render()
            pygame.display.flip()
        
        pygame.quit()
    
    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.paused = not self.paused
        elif key == pygame.K_r and self.game_over:
            self.game_over = False
            self.floor = 1
            self.player = None
            self.init_floor()
        elif key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]:
            mx, my = pygame.mouse.get_pos()
            wx = (mx + self.cam_x) / TILE
            wy = (my + self.cam_y) / TILE
            self.player.use_skill(key - pygame.K_1, wx, wy, self)
    
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
        self.player.update(dt, self.dungeon, keys)
        
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
        
        # 检查出口
        if math.sqrt((self.player.x - self.dungeon.exit[0])**2 + (self.player.y - self.dungeon.exit[1])**2) < 1:
            self.floor += 1
            self.init_floor()
        
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
        
        # 出口
        ex = self.dungeon.exit[0] * TILE - self.cam_x
        ey = self.dungeon.exit[1] * TILE - self.cam_y
        pygame.draw.rect(self.screen, C['exit'], (ex + 4, ey + 4, TILE - 8, TILE - 8))
        
        # 战利品
        for lt in self.loot:
            px = lt['x'] * TILE - self.cam_x
            py = lt['y'] * TILE - self.cam_y
            pygame.draw.circle(self.screen, C['gold'], (int(px), int(py)), 6)
        
        # 敌人
        for e in self.enemies:
            px = e.x * TILE - self.cam_x
            py = e.y * TILE - self.cam_y
            r = int(e.radius * TILE)
            pygame.draw.circle(self.screen, C['enemy'], (int(px), int(py)), r)
            
            # 血条
            if e.hp < e.max_hp:
                pygame.draw.rect(self.screen, (50, 50, 50), (px - 16, py - r - 8, 32, 4))
                pygame.draw.rect(self.screen, C['hp'], (px - 16, py - r - 8, 32 * e.hp / e.max_hp, 4))
        
        # 玩家
        px = self.player.x * TILE - self.cam_x
        py = self.player.y * TILE - self.cam_y
        r = int(self.player.radius * TILE)
        pygame.draw.circle(self.screen, C['player'], (int(px), int(py)), r)
        
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
            pygame.draw.rect(self.screen, (20, 20, 30), (x, y, 50, 50), border_radius=8)
            
            if sk['timer'] > 0:
                cd = self.font.render(f"{sk['timer']:.1f}", True, C['white'])
                self.screen.blit(cd, (x + 15, y + 18))
            else:
                k = self.font.render(str(i + 1), True, C['white'])
                self.screen.blit(k, (x + 18, y + 18))
        
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
