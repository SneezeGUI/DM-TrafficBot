import os
import shutil
import subprocess
import sys
import glob
import time
import stat


def handle_remove_readonly(func, path, exc):
    import stat

    excvalue = exc[1]
    if excvalue.errno == 5:  # Access Denied
        os.chmod(path, stat.S_IWRITE)
        try:
            func(path)
        except Exception:
            # If it still fails, it might be a process lock or a nested issue
            pass
    else:
        raise


def archive_old_builds():
    releases_dir = "releases"
    archive_dir = os.path.join(releases_dir, "archive")

    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)
        print(f"Created archive directory: {archive_dir}")

    # Also check root for any stray zips to migrate them
    for file_path in glob.glob("DarkMatterBot_v*.zip"):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            new_name = f"{name}_{timestamp}{ext}"
            destination = os.path.join(archive_dir, new_name)

            shutil.move(file_path, destination)
            print(f"Migrated and archived: {file_path} -> {destination}")
        except Exception as e:
            print(f"Failed to archive {file_path}: {e}")

    # Archive any previous zips already in releases (but not in archive subfolder)
    for file_path in glob.glob(os.path.join(releases_dir, "DarkMatterBot_v*.zip")):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            new_name = f"{name}_{timestamp}{ext}"
            destination = os.path.join(archive_dir, new_name)

            shutil.move(file_path, destination)
            print(f"Archived previous release: {file_path} -> {destination}")
        except Exception as e:
            print(f"Failed to archive {file_path}: {e}")


def install_pyinstaller():
    try:
        import PyInstaller

        print("PyInstaller is already installed.")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_executable():
    print("Archiving old builds...")
    archive_old_builds()

    print("Cleaning up previous builds...")
    if os.path.exists("build"):
        shutil.rmtree("build", ignore_errors=False, onerror=handle_remove_readonly)
    if os.path.exists("dist"):
        shutil.rmtree("dist", ignore_errors=False, onerror=handle_remove_readonly)

    print("Building executable...")

    # Define the PyInstaller command
    # --noconfirm: overwrite output directory
    # --onefile: package into a single exe
    # --windowed: no console window
    # --icon: set the application icon
    # --add-data: include the resources directory
    # --name: name of the executable

    sep = ";" if os.name == "nt" else ":"

    command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",  # Package into a single exe
        "--windowed",
        "--icon=resources/favicon.ico",
        f"--add-data=resources{sep}resources",
        f"--add-data=ui{sep}ui",
        "--hidden-import=customtkinter",
        "--hidden-import=curl_cffi",
        "--name=DarkMatterBot",
        "main.py",
    ]

    try:
        subprocess.check_call(command)
        print("\nBuild successful! Executable is in the 'dist' directory.")

        # Create a zip file for distribution
        print("Creating distribution archive...")
        import zipfile

        releases_dir = "releases"
        if not os.path.exists(releases_dir):
            os.makedirs(releases_dir)

        zip_name = "DarkMatterBot_v3.6.0.zip"
        zip_path = os.path.join(releases_dir, zip_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write("dist/DarkMatterBot.exe", "DarkMatterBot.exe")

        print(f"Archive created: {zip_path}")

    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")


if __name__ == "__main__":
    # Ensure we are running in the venv
    venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    if os.path.exists(venv_path):
        # Check if sys.executable is inside the venv
        if not sys.executable.startswith(os.path.abspath(venv_path)):
            print("Not running in venv. Relaunching via venv...")
            if os.name == "nt":
                python_executable = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                python_executable = os.path.join(venv_path, "bin", "python")

            if os.path.exists(python_executable):
                subprocess.check_call([python_executable] + sys.argv)
                sys.exit(0)
            else:
                print(
                    "Warning: .venv found but python executable not found. Continuing..."
                )

    install_pyinstaller()
    build_executable()
