import pymunk
print(f"Pymunk version: {pymunk.version}")
try:
    space = pymunk.Space()
    if hasattr(space, 'add_default_collision_handler'):
        print("add_default_collision_handler exists")
        h = space.add_default_collision_handler()
        print("Handler created")
    else:
        print("add_default_collision_handler DOES NOT EXIST")
        print(f"Space attributes: {dir(space)}")
except Exception as e:
    print(f"Error: {e}")
