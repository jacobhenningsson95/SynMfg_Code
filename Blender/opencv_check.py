import subprocess
import sys
import bpy

try:
    import cv2

    print(f"OpenCV Version: {cv2.__version__}")
except ImportError:
    print("OpenCV is not installed. Installing now...")

    python_exe = sys.executable

    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "opencv-python"])
        print("Successfully installed OpenCV. Please restart Blender.")

    except subprocess.CalledProcessError as e:
        print(f"Failed to install OpenCV: {str(e)}")

bpy.ops.wm.quit_blender()