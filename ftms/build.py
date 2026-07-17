import os
import subprocess

def build(app_path):
    # This is a bit of a hack, but it's the only way to get the app name
    app_name = os.path.basename(app_path)
    frontend_dir = os.path.join(app_path, '..', f'{app_name}-frontend')

    if not os.path.exists(frontend_dir):
        print(f'Frontend directory not found: {frontend_dir}')
        return

    print('Building frontend...')
    # Run yarn build
    subprocess.run(['npm', 'install'], cwd=frontend_dir)
    subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir)

    # Copy the build to the app's public directory
    dist_dir = os.path.join(frontend_dir, 'dist')
    public_dir = os.path.join(app_path, 'public')

    if os.path.exists(public_dir):
        # remove the old build
        for file in os.listdir(public_dir):
            os.remove(os.path.join(public_dir, file))
    else:
        os.makedirs(public_dir)

    # Copy the new build
    for file in os.listdir(dist_dir):
        # copy the file to the public directory
        os.rename(os.path.join(dist_dir, file), os.path.join(public_dir, file))
