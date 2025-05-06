import os
import shutil
from filelock import FileLock

# Move a file with locking
 
def move_file_with_lock(src, dst):
    with FileLock(src + '.lock'):
        shutil.move(src, dst) 