from ursina import *
import random
import math

app = Ursina()
Sky()

# --- UNITY 6 RIGIDBODY & COLLISION MANTIĞIYLA ÇALIŞAN ÖZEL OYUNCU SİSTEMİ ---
class VoxelPlayer(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scale = (1, 1, 1)
        self.player_height = 1.8  
        self.player_radius = 0.3  
       
        # Fizik Değerleri
        self.speed = 6
        self.jump_height = 7
        self.gravity = 22
        self.velocity = Vec3(0, 0, 0)
        self.grounded = False
       
        # Kamera Ayarları
        camera.parent = self
        camera.position = (0, 1.5, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = 80
        mouse.locked = True
       
    def update(self):
        self.rotation_y += mouse.velocity[0] * 40
        camera.rotation_x -= mouse.velocity[1] * 40
        camera.rotation_x = clamp(camera.rotation_x, -85, 85)
       
        move_dir = (self.forward * (held_keys['w'] - held_keys['s']) +
                    self.right * (held_keys['d'] - held_keys['a']))
        move_dir.y = 0
        if move_dir.length() > 0:
            move_dir = move_dir.normalized()
       
        self.velocity.x = move_dir.x * self.speed
        self.velocity.z = move_dir.z * self.speed
       
        if not self.grounded:
            self.velocity.y -= self.gravity * time.dt
           
        if self.grounded and held_keys['space']:
            self.velocity.y = self.jump_height
            self.grounded = False
           
        # --- DİKEY ÇARPIŞMA VE SIKIŞMA ÖNLEME SİSTEMİ (GÜNCELLENDİ) ---
        # 1. Adım: Blok içine gömülmeyi engellemek için ayak hizasının biraz yukarısından (0.2) aşağıya tarama yapıyoruz
        ray_distance = abs(self.velocity.y * time.dt) + 0.2
        ray_down = raycast(self.position + Vec3(0, 0.2, 0), Vec3(0, -1, 0),
                           distance=ray_distance, ignore=(self,))
       
        if ray_down.hit and self.velocity.y <= 0:
            self.grounded = True
            self.velocity.y = 0
            # Karakteri tam olarak bloğun üst yüzeyine kilitliyoruz
            self.y = ray_down.world_point.y
        else:
            self.grounded = False

        # 2. Adım: Sıkışma Koruması (Anti-Clip)
        # Eğer karakter bir şekilde bir bloğun içine düşerse, anında en yakın üst yüzeye ışınlanır
        if not self.grounded:
            inside_check = raycast(self.position + Vec3(0, 0.5, 0), Vec3(0, -1, 0), distance=0.51, ignore=(self,))
            # Sadece düşerken veya gerçekten blok içine gömüldüğümüzde yere hizala (zıplama iptali olmasın)
            if inside_check.hit and self.velocity.y <= 0:
                self.grounded = True
                self.velocity.y = 0
                self.y = inside_check.world_point.y
               
        # Tavan çarpışma kontrolü
        if self.velocity.y > 0:
            hit_ceiling = False
            offsets = [Vec3(0,0,0), Vec3(0.2,0,0), Vec3(-0.2,0,0), Vec3(0,0,0.2), Vec3(0,0,-0.2)]
            for offset in offsets:
                ray_up = raycast(self.position + Vec3(0, self.player_height - 0.1, 0) + offset, Vec3(0, 1, 0),
                                 distance=self.velocity.y * time.dt + 0.1, ignore=(self,))
                if ray_up.hit:
                    hit_ceiling = True
                    break
            if hit_ceiling:
                self.velocity.y = 0  
               
        self.y += self.velocity.y * time.dt
       
        # --- YATAY ÇARPIŞMA SİSTEMİ ---
        if self.velocity.x != 0:
            dir_x = 1 if self.velocity.x > 0 else -1
            hit_x = False
            for y_off in (0.3, 1.2):
                ray_x = raycast(self.position + Vec3(0, y_off, 0), Vec3(dir_x, 0, 0),
                                distance=self.player_radius + abs(self.velocity.x * time.dt), ignore=(self,))
                if ray_x.hit:
                    hit_x = True
                    break
            if not hit_x:
                self.x += self.velocity.x * time.dt
               
        if self.velocity.z != 0:
            dir_z = 1 if self.velocity.z > 0 else -1
            hit_z = False
            for y_off in (0.3, 1.2):
                ray_z = raycast(self.position + Vec3(0, y_off, 0), Vec3(0, 0, dir_z),
                                distance=self.player_radius + abs(self.velocity.z * time.dt), ignore=(self,))
                if ray_z.hit:
                    hit_z = True
                    break
            if not hit_z:
                self.z += self.velocity.z * time.dt

# Oyuncuyu başlat
player = VoxelPlayer(position=(5, 20, 5))
window.fullscreen = True
camera.clip_plane_far = 150

# --- DOKULAR VE BLOK VERİLERİ ---
grass_texture = load_texture('textures/grass.png')
dirt_texture = load_texture('textures/dirt.png')
stone_texture = load_texture('textures/stone.png')
log_texture = load_texture('textures/log.png')
wood_texture = load_texture('textures/wood.png')
leaves_texture = load_texture('textures/leaves.png')

BLOCK_TEXTURES = {
    1: grass_texture, 2: dirt_texture, 3: stone_texture,
    4: log_texture, 5: wood_texture, 6: leaves_texture
}

# --- SURVIVAL VERİ YAPILARI (HOTBAR VE ENVANTER MANTIĞI) ---
hotbar_data = [{'id': 0, 'count': 0} for _ in range(9)]
hotbar_data[0] = {'id': 1, 'count': 20}
hotbar_data[1] = {'id': 2, 'count': 20}
hotbar_data[2] = {'id': 3, 'count': 20}

active_slot = 0
hotbar_slots_ui = []
hotbar_cubes_ui = []
hotbar_texts_ui = []

# --- 3 BOYUTLU VE VEKTÖREL HIZLI (FIRLATILABİLİR) EŞYA SINIFI ---
class DroppedItem(Entity):
    def __init__(self, block_id, initial_velocity=Vec3(0,0,0), **kwargs):
        super().__init__(
            model='cube',
            texture=BLOCK_TEXTURES[block_id],
            scale=0.25,
            collider='box',
            **kwargs
        )
        self.block_id = block_id
        self.spawn_time = time.time()
       
        # Fizik Değişkenleri
        self.gravity = 16          
        self.velocity = initial_velocity
        self.grounded = False      
        self.base_y = self.y      

    def update(self):
        self.rotation_y += time.dt * 70
       
        if not self.grounded:
            self.velocity.y -= self.gravity * time.dt
            move_amount = self.velocity * time.dt
           
            ray = raycast(self.position, Vec3(0, -1, 0), distance=abs(move_amount.y) + 0.125, ignore=(self,))
           
            if ray.hit and self.velocity.y <= 0:
                self.grounded = True
                self.velocity = Vec3(0, 0, 0)
                self.base_y = ray.world_point.y + 0.15
                self.y = self.base_y
                self.spawn_time = time.time()
            else:
                self.position += move_amount
               
                if move_amount.length() > 0:
                    wall_ray = raycast(self.position, move_amount.normalized(), distance=move_amount.length() + 0.15, ignore=(self,))
                    if wall_ray.hit:
                        self.velocity.x = 0
                        self.velocity.z = 0
        else:
            check_ray = raycast(self.position, Vec3(0, -1, 0), distance=0.25, ignore=(self,))
            if not check_ray.hit:
                self.grounded = False
            else:
                self.y = self.base_y + math.sin((time.time() - self.spawn_time) * 4) * 0.05
       
        dist = distance(self.position, player.position + Vec3(0, 1, 0))
        if dist < 2.0 and (time.time() - self.spawn_time > 0.8):
            if add_to_inventory(self.block_id):
                destroy(self)

def add_to_inventory(block_id):
    for slot in hotbar_data:
        if slot['id'] == block_id and slot['count'] < 64:
            slot['count'] += 1
            update_hotbar_ui()
            return True
    for slot in hotbar_data:
        if slot['count'] == 0:
            slot['id'] = block_id
            slot['count'] = 1
            update_hotbar_ui()
            return True
    return False

# --- MINECRAFT TARZI HOTBAR UI OLUŞTURUCU ---
y_start = window.bottom.y + 0.06
x_start = -0.245
spacing = 0.061

hotbar_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(0,0,0,0.5), scale=(0.58, 0.075), position=(0, y_start, 2))
hotbar_selector = Entity(parent=camera.ui, model='quad', color=color.rgba(255,255,255,0.3), scale=(0.062, 0.072), position=(x_start, y_start, 1))

def setup_hotbar_ui():
    for i in range(9):
        x_pos = x_start + (i * spacing)
        slot = Entity(parent=camera.ui, model='quad', color=color.rgba(50,50,50,0.7), scale=(0.054, 0.064), position=(x_pos, y_start, 1.5))
        hotbar_slots_ui.append(slot)
       
        cube = Entity(parent=camera.ui, model='cube', scale=(0.026, 0.026, 0.026), position=(x_pos, y_start, 0), rotation=(20, 45, 0), enabled=False)
        hotbar_cubes_ui.append(cube)
       
        txt = Text(text='', parent=camera.ui, position=(x_pos - 0.02, y_start - 0.012), scale=0.9, color=color.white)
        hotbar_texts_ui.append(txt)

def update_hotbar_ui():
    hotbar_selector.x = x_start + (active_slot * spacing)
    for i in range(9):
        data = hotbar_data[i]
        if data['count'] > 0:
            hotbar_cubes_ui[i].texture = BLOCK_TEXTURES[data['id']]
            hotbar_cubes_ui[i].enable()
            hotbar_texts_ui[i].text = str(data['count'])
        else:
            hotbar_cubes_ui[i].disable()
            hotbar_texts_ui[i].text = ''

setup_hotbar_ui()
update_hotbar_ui()

# --- SEÇİM SEKTÖRÜ (OUTLINE) ---
selector = Entity(model='cube', texture='textures/corner.png', scale=1.01, color=color.white, enabled=False)
crosshair = Entity(parent=camera.ui, model='quad', texture='textures/cross.png', scale=0.03, position=(0, 0))

# --- 10x10 CHUNK VE MOTOR AYARLARI ---
CHUNK_SIZE = 10      
VIEW_DISTANCE = 3  
world_data = {}      
chunk_entities = {}  

# El Modeli
arm = Entity(parent=camera.ui, model='cube', color=color.blue, position=(0.75, -0.6), rotation=(150, -10, 6), scale=(0.2, 0.2, 1.5))

def update():
    global active_slot
   
    for i in range(9):
        if hotbar_cubes_ui[i].enabled:
            hotbar_cubes_ui[i].rotation_y += time.dt * 35
   
    if held_keys['left mouse'] or held_keys['right mouse']:
        arm.position = (0.6, -0.5)
    else:
        arm.position = (0.75, -0.6)

    # 🌟 GÜNCELLENDİ: İmleç bir nesneye bakıyorsa VE bu nesne "DroppedItem" DEĞİLSE siyah çizgileri göster
    if mouse.hovered_entity and not isinstance(mouse.hovered_entity, DroppedItem):
        hit_pos = mouse.world_point
        ray_dir = hit_pos - camera.world_position
       
        diff_x = abs(hit_pos.x - round(hit_pos.x))
        diff_y = abs(hit_pos.y - round(hit_pos.y))
        diff_z = abs(hit_pos.z - round(hit_pos.z))
        min_diff = min(diff_x, diff_y, diff_z)
       
        if min_diff == diff_x: clean_normal = Vec3(1 if ray_dir.x < 0 else -1, 0, 0)
        elif min_diff == diff_y: clean_normal = Vec3(0, 1 if ray_dir.y < 0 else -1, 0)
        else: clean_normal = Vec3(0, 0, 1 if ray_dir.z < 0 else -1)

        bx = int(floor(hit_pos.x - clean_normal.x * 0.5))
        by = int(floor(hit_pos.y - clean_normal.y * 0.5))
        bz = int(floor(hit_pos.z - clean_normal.z * 0.5))
       
        selector.position = Vec3(bx + 0.5, by + 0.5, bz + 0.5)
        selector.enabled = True
    else:
        selector.enabled = False

    manage_chunks()

FACE_VERTICES = {
    'top':    ((0,1,0), (1,1,0), (1,1,1), (0,1,1)),
    'bottom': ((0,0,1), (1,0,1), (1,0,0), (0,0,0)),
    'left':   ((0,0,0), (0,0,1), (0,1,1), (0,1,0)),
    'right':  ((1,0,1), (1,0,0), (1,1,0), (1,1,1)),
    'front':  ((0,0,1), (1,0,1), (1,1,1), (0,1,1)),
    'back':   ((1,0,0), (0,0,0), (0,1,0), (1,1,0))
}

def build_chunk_mesh(cx, cz):
    if (cx, cz) in chunk_entities:
        for ent in chunk_entities[(cx, cz)]: destroy(ent)
           
    chunk_entities[(cx, cz)] = []
    start_x, start_z = cx * CHUNK_SIZE, cz * CHUNK_SIZE
    mesh_data = {bid: {'vertices': [], 'triangles': [], 'uvs': [], 'v_count': 0} for bid in BLOCK_TEXTURES.keys()}

    for x in range(start_x, start_x + CHUNK_SIZE):
        for z in range(start_z, start_z + CHUNK_SIZE):
            for y in range(-5, 25):
                if (x, y, z) not in world_data: continue
                bid = world_data[(x, y, z)]
               
                neighbors = {
                    'top':    (x, y + 1, z) in world_data,
                    'bottom': (x, y - 1, z) in world_data,
                    'left':   (x - 1, y, z) in world_data,
                    'right':  (x + 1, y, z) in world_data,
                    'front':  (x, y, z + 1) in world_data,
                    'back':   (x, y, z - 1) in world_data
                }

                for face, is_covered in neighbors.items():
                    if not is_covered or bid == 6:
                        md = mesh_data[bid]
                        for vertex in FACE_VERTICES[face]:
                            md['vertices'].append((x + vertex[0], y + vertex[1], z + vertex[2]))
                        vc = md['v_count']
                        md['triangles'].append((vc, vc + 1, vc + 2))
                        md['triangles'].append((vc, vc + 2, vc + 3))
                        md['uvs'].extend([(0,0), (1,0), (1,1), (0,1)])
                        md['v_count'] += 4

    for bid, data in mesh_data.items():
        if data['v_count'] > 0:
            m = Mesh(vertices=data['vertices'], triangles=data['triangles'], uvs=data['uvs'])
            ent = Entity(model=m, texture=BLOCK_TEXTURES[bid], collider='mesh', color=color.white, double_sided=True)
            chunk_entities[(cx, cz)].append(ent)

def pre_generate_chunk_data(cx, cz):
    start_x, start_z = cx * CHUNK_SIZE, cz * CHUNK_SIZE
    if (start_x, -5, start_z) in world_data: return

    for x in range(start_x, start_x + CHUNK_SIZE):
        for z in range(start_z, start_z + CHUNK_SIZE):
            base_wave = math.sin(x * 0.04) * math.cos(z * 0.04) * 11
            detail_wave = math.sin(x * 0.12) * math.sin(z * 0.12) * 3
            height = int(base_wave + detail_wave)
           
            for y in range(-5, height + 1):
                if y == height:
                    if y > 6: world_data[(x, y, z)] = 3  
                    else: world_data[(x, y, z)] = 1  
                elif y > height - 3: world_data[(x, y, z)] = 2      
                else: world_data[(x, y, z)] = 3      

            if height <= 6 and random.random() < 0.02:
                for h in range(1, 5): world_data[(x, height + h, z)] = 4
                for lx in range(-1, 2):
                    for lz in range(-1, 2):
                        for ly in range(2):
                            tx, ty, tz = x + lx, height + 4 + ly, z + lz
                            if (tx, ty, tz) not in world_data: world_data[(tx, ty, tz)] = 6

def manage_chunks():
    player_cx = int(player.x // CHUNK_SIZE)
    player_cz = int(player.z // CHUNK_SIZE)
    active_chunks = set()

    for dx in range(-VIEW_DISTANCE, VIEW_DISTANCE + 1):
        for dz in range(-VIEW_DISTANCE, VIEW_DISTANCE + 1):
            cx = player_cx + dx
            cz = player_cz + dz
            active_chunks.add((cx, cz))
            if (cx, cz) not in chunk_entities:
                pre_generate_chunk_data(cx, cz)
                build_chunk_mesh(cx, cz)
            else:
                for ent in chunk_entities[(cx, cz)]: ent.enable()

    for coord, entities in chunk_entities.items():
        if coord not in active_chunks:
            for ent in entities: ent.disable()

def update_chunks_at(bx, bz):
    cx = bx // CHUNK_SIZE
    cz = bz // CHUNK_SIZE
    build_chunk_mesh(cx, cz)
    if (bx - 1) // CHUNK_SIZE != cx: build_chunk_mesh((bx - 1) // CHUNK_SIZE, cz)
    if (bx + 1) // CHUNK_SIZE != cx: build_chunk_mesh((bx + 1) // CHUNK_SIZE, cz)
    if (bz - 1) // CHUNK_SIZE != cz: build_chunk_mesh(cx, (bz - 1) // CHUNK_SIZE)
    if (bz + 1) // CHUNK_SIZE != cz: build_chunk_mesh(cx, (bz + 1) // CHUNK_SIZE)

# --- MATEMATİKSEL YÜZEY INPUT VE KONTROL SİSTEMİ ---
def input(key):
    global active_slot
   
    if key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
        active_slot = int(key) - 1
        update_hotbar_ui()
       
    if key == 'scroll up':
        active_slot = (active_slot + 1) % 9
        update_hotbar_ui()
    if key == 'scroll down':
        active_slot = (active_slot - 1) % 9
        update_hotbar_ui()

    if key == 'q':
        slot_item = hotbar_data[active_slot]
        if slot_item['count'] > 0:
            thrown_id = slot_item['id']
           
            slot_item['count'] -= 1
            if slot_item['count'] <= 0:
                slot_item['id'] = 0
            update_hotbar_ui()
           
            spawn_pos = camera.world_position + camera.forward * 0.8
            throw_velocity = camera.forward * 7 + Vec3(0, 2.5, 0)
           
            DroppedItem(block_id=thrown_id, position=spawn_pos, initial_velocity=throw_velocity)

    # 🌟 GÜNCELLENDİ: Tıklama yapıldığında da yerdeki eşyalar (DroppedItem) filtrelenir
    if mouse.hovered_entity and not isinstance(mouse.hovered_entity, DroppedItem):
        hit_pos = mouse.world_point
        ray_dir = hit_pos - camera.world_position
       
        diff_x = abs(hit_pos.x - round(hit_pos.x))
        diff_y = abs(hit_pos.y - round(hit_pos.y))
        diff_z = abs(hit_pos.z - round(hit_pos.z))
        min_diff = min(diff_x, diff_y, diff_z)
       
        if min_diff == diff_x: clean_normal = Vec3(1 if ray_dir.x < 0 else -1, 0, 0)
        elif min_diff == diff_y: clean_normal = Vec3(0, 1 if ray_dir.y < 0 else -1, 0)
        else: clean_normal = Vec3(0, 0, 1 if ray_dir.z < 0 else -1)

        # SOL TIK: Blok Kırma
        if key == 'left mouse down':
            bx = int(floor(hit_pos.x - clean_normal.x * 0.5))
            by = int(floor(hit_pos.y - clean_normal.y * 0.5))
            bz = int(floor(hit_pos.z - clean_normal.z * 0.5))
            if (bx, by, bz) in world_data:
                broken_block_id = world_data[(bx, by, bz)]
               
                del world_data[(bx, by, bz)]
                update_chunks_at(bx, bz)
               
                DroppedItem(block_id=broken_block_id, position=Vec3(bx + 0.5, by + 0.5, bz + 0.5))

        # SAĞ TIK: Blok Koyma
        if key == 'right mouse down':
            slot_item = hotbar_data[active_slot]
            if slot_item['count'] > 0:
                bx = int(floor(hit_pos.x + clean_normal.x * 0.5))
                by = int(floor(hit_pos.y + clean_normal.y * 0.5))
                bz = int(floor(hit_pos.z + clean_normal.z * 0.5))
                if (bx, by, bz) not in world_data:
                    world_data[(bx, by, bz)] = slot_item['id']
                   
                    slot_item['count'] -= 1
                    if slot_item['count'] <= 0:
                        slot_item['id'] = 0
                       
                    update_hotbar_ui()
                    update_chunks_at(bx, bz)

app.run()
